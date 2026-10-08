"""指标台账导入与模板草稿校验。"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.performance import PerformanceImportBatch, PerformanceMetricFact, PerformanceTemplate
from app.models.user import User
from app.services.performance_rule_engine import blocking, validate_definition
from app.services.performance_template import item_evaluator


def template_item_evaluator(item: object) -> str:
    """模板指标的评分人（列优先，兼容写在 rule_config_json 里的）。

    委托给 performance_template.item_evaluator，保持单一实现。
    """
    return item_evaluator(item)


def validate_template(db: Session, template_id: int) -> dict:
    row = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    if (row.scoring_mode or "legacy_weighted") == "legacy_weighted":
        return {"ok": True, "engine_version": "legacy", "issues": []}
    issues = blocking(validate_definition(json.loads(row.definition_json or "{}")))
    return {"ok": not issues, "engine_version": row.engine_version, "issues": issues}


def preview_import(db: Session, user: User, text: str, *, users_by_name: dict[str, int]) -> dict:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    rows = []
    errors = []
    seen = set()
    for index, raw in enumerate(reader, start=2):
        name = (raw.get("employee") or "").strip()
        metric = (raw.get("metric_key") or "").strip()
        source_id = (raw.get("source_record_id") or "").strip()
        value_raw = (raw.get("value") or "").strip()
        if name not in users_by_name:
            errors.append({"row": index, "column": "employee", "message": "未知员工"})
            continue
        if not metric or not source_id:
            errors.append({"row": index, "column": "metric_key", "message": "缺少指标或来源编号"})
            continue
        key = (metric, users_by_name[name], source_id)
        duplicate = key in seen or db.query(PerformanceMetricFact).filter(
            PerformanceMetricFact.metric_key == metric,
            PerformanceMetricFact.owner_id == users_by_name[name],
            PerformanceMetricFact.source_record_id == source_id,
        ).first()
        seen.add(key)
        value = None if value_raw == "" else Decimal(value_raw)
        rows.append({
            "employee": name,
            "owner_id": users_by_name[name],
            "metric_key": metric,
            "source_record_id": source_id,
            "value": None if value is None else str(value),
            "data_state": "missing" if value is None else "pending",
            "duplicate": bool(duplicate),
            "project_ref": (raw.get("project_ref") or "").strip() or None,
        })
    batch = PerformanceImportBatch(
        file_hash=digest,
        status="preview",
        rows_json=json.dumps(rows, ensure_ascii=False),
        errors_json=json.dumps(errors, ensure_ascii=False),
        created_by=user.id,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return {"id": batch.id, "rows": rows, "errors": errors, "can_confirm": not errors}


def confirm_import(db: Session, user: User, batch_id: int) -> dict:
    batch = db.query(PerformanceImportBatch).filter(PerformanceImportBatch.id == batch_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="导入批次不存在")
    if batch.created_by != user.id:
        raise HTTPException(status_code=403, detail="不能确认他人的导入")
    errors = json.loads(batch.errors_json or "[]")
    if errors:
        raise HTTPException(status_code=400, detail="存在错误行，整批不写入")
    if batch.status == "confirmed":
        return {"id": batch.id, "written": 0, "idempotent": True}
    written = 0
    for row in json.loads(batch.rows_json or "[]"):
        if row.get("duplicate"):
            continue
        exists = db.query(PerformanceMetricFact).filter(
            PerformanceMetricFact.metric_key == row["metric_key"],
            PerformanceMetricFact.owner_id == row["owner_id"],
            PerformanceMetricFact.source_record_id == row["source_record_id"],
        ).first()
        if exists:
            continue
        db.add(PerformanceMetricFact(
            metric_key=row["metric_key"],
            owner_id=row["owner_id"],
            value=None if row["value"] is None else Decimal(row["value"]),
            source_record_id=row["source_record_id"],
            project_ref=row.get("project_ref"),
            status="pending",
        ))
        written += 1
    batch.status = "confirmed"
    db.commit()
    return {"id": batch.id, "written": written, "idempotent": False}


METRIC_SOURCES = [
    {"ref": "ledger.manual", "unit": "count", "auto": False, "note": "审核台账，首期默认"},
    {"ref": "contract.signed_customer_count", "unit": "customer", "auto": False, "note": "签约去重口径待确认，先走台账"},
]


def _template(db: Session, template_id: int) -> PerformanceTemplate:
    row = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    return row


def revise_template(db: Session, template_id: int) -> dict:
    from app.models.performance import PerformanceTemplateItem, PerformanceTemplateScope

    row = _template(db, template_id)
    family = row.family_code or row.code
    version = int(row.version or 1) + 1
    code = f"{family}_V{version}"
    if db.query(PerformanceTemplate).filter(PerformanceTemplate.code == code).first():
        raise HTTPException(status_code=409, detail="该版本已存在")
    nxt = PerformanceTemplate(
        name=row.name,
        code=code,
        status="draft",
        family_code=family,
        version=version,
        supersedes_id=row.id,
        engine_version=row.engine_version,
        assessment_kind=row.assessment_kind,
        scoring_mode=row.scoring_mode,
        nominal_total=row.nominal_total,
        definition_json=row.definition_json,
        blocking_issues_json=row.blocking_issues_json,
        cycle_type=row.cycle_type,
        remark=row.remark,
    )
    db.add(nxt)
    db.flush()
    # 拷贝适用范围
    for scope in (
        db.query(PerformanceTemplateScope)
        .filter(PerformanceTemplateScope.template_id == row.id)
        .all()
    ):
        db.add(
            PerformanceTemplateScope(
                template_id=nxt.id,
                department_id=scope.department_id,
                job_title=scope.job_title,
            )
        )
    # 拷贝指标项快照
    for item in (
        db.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == row.id)
        .order_by(PerformanceTemplateItem.order_no.asc(), PerformanceTemplateItem.id.asc())
        .all()
    ):
        db.add(
            PerformanceTemplateItem(
                template_id=nxt.id,
                order_no=item.order_no,
                name=item.name,
                weight=item.weight,
                data_source=item.data_source,
                source_ref=item.source_ref,
                target_value=item.target_value,
                score_rule=item.score_rule,
                hint=item.hint,
                metric_key=item.metric_key,
                max_points=item.max_points,
                # 双评分：评分人随版本一起复制
                evaluator=item_evaluator(item),
                rule_config_json=item.rule_config_json,
                indicator_definition_id=item.indicator_definition_id,
                scoring_type=item.scoring_type,
                unit=item.unit,
                handling_mode=item.handling_mode,
                evidence_policy_json=item.evidence_policy_json,
            )
        )
    db.commit()
    db.refresh(nxt)
    return {"id": nxt.id, "code": nxt.code, "version": nxt.version, "status": nxt.status}


def preview_template(db: Session, template_id: int, actuals: dict) -> dict:
    from app.services.performance_rule_engine import score_definition

    row = _template(db, template_id)
    if (row.scoring_mode or "legacy_weighted") == "legacy_weighted":
        raise HTTPException(status_code=400, detail="不支持该考核模式")
    result = score_definition(json.loads(row.definition_json or "{}"), actuals)
    result["engine_version"] = row.engine_version
    result["scoring_mode"] = row.scoring_mode
    return _public_score(result)


def list_assignments(db: Session) -> list:
    from app.models.performance import PerformanceTemplateAssignment

    rows = db.query(PerformanceTemplateAssignment).order_by(PerformanceTemplateAssignment.id.asc()).all()
    return [_assignment_out(x) for x in rows]


def create_assignment(db: Session, payload: dict) -> dict:
    from app.models.performance import PerformanceTemplateAssignment

    _template(db, int(payload["template_id"]))
    user_id = payload.get("user_id")
    department_id = payload.get("department_id")
    job_title = payload.get("job_title")
    if user_id:
        priority = 40
    elif department_id and job_title:
        priority = 30
    elif department_id:
        priority = 20
    else:
        priority = 10
    kind = payload.get("assessment_kind") or "monthly"
    q = db.query(PerformanceTemplateAssignment).filter(
        PerformanceTemplateAssignment.priority == priority,
        PerformanceTemplateAssignment.assessment_kind == kind,
    )
    if user_id:
        q = q.filter(PerformanceTemplateAssignment.user_id == user_id)
    elif department_id and job_title:
        q = q.filter(
            PerformanceTemplateAssignment.department_id == department_id,
            PerformanceTemplateAssignment.job_title == job_title,
        )
    elif department_id:
        q = q.filter(
            PerformanceTemplateAssignment.department_id == department_id,
            PerformanceTemplateAssignment.job_title.is_(None),
            PerformanceTemplateAssignment.user_id.is_(None),
        )
    else:
        q = q.filter(
            PerformanceTemplateAssignment.user_id.is_(None),
            PerformanceTemplateAssignment.department_id.is_(None),
        )
    if q.first():
        raise HTTPException(status_code=409, detail="同一优先级已有分配")
    row = PerformanceTemplateAssignment(
        template_id=int(payload["template_id"]),
        user_id=user_id,
        department_id=department_id,
        job_title=job_title,
        assessment_kind=kind,
        priority=priority,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _assignment_out(row)


def _assignment_out(row) -> dict:
    return {
        "id": row.id,
        "template_id": row.template_id,
        "user_id": row.user_id,
        "department_id": row.department_id,
        "job_title": row.job_title,
        "assessment_kind": row.assessment_kind,
        "priority": row.priority,
    }


def list_facts(db: Session, user: User, *, manage: bool) -> list:
    q = db.query(PerformanceMetricFact)
    if not manage:
        q = q.filter(PerformanceMetricFact.owner_id == user.id)
    return [
        {
            "id": row.id,
            "metric_key": row.metric_key,
            "owner_id": row.owner_id,
            "value": None if row.value is None else str(row.value),
            "status": row.status,
            "source_record_id": row.source_record_id,
            "project_ref": row.project_ref,
        }
        for row in q.order_by(PerformanceMetricFact.id.asc()).all()
    ]


def review_fact(db: Session, fact_id: int, status: str) -> dict:
    if status not in {"confirmed", "rejected"}:
        raise HTTPException(status_code=400, detail="status 仅支持 confirmed 或 rejected")
    row = db.query(PerformanceMetricFact).filter(PerformanceMetricFact.id == fact_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="事实不存在")
    row.status = status
    db.commit()
    return {"id": row.id, "status": row.status}


def _assessment(db: Session, assessment_id: int):
    from app.models.performance import PerformanceAssessment

    row = db.query(PerformanceAssessment).filter(PerformanceAssessment.id == assessment_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="考核单不存在")
    return row


def confirm_assessment(db: Session, user: User, assessment_id: int, *, manage: bool) -> dict:
    row = _assessment(db, assessment_id)
    if row.status == "archived":
        raise HTTPException(status_code=409, detail="已归档，不能确认")
    if not manage and row.user_id != user.id:
        raise HTTPException(status_code=403, detail="只能确认自己的考核")
    row.confirmed_revision = row.revision
    db.commit()
    return {"id": row.id, "revision": row.revision, "confirmed_revision": row.confirmed_revision}


def refresh_assessment(db: Session, assessment_id: int) -> dict:
    from app.models.performance import PerformanceAssessmentItem
    from app.services import performance_materials as mats

    row = _assessment(db, assessment_id)
    if row.status == "archived":
        raise HTTPException(status_code=409, detail="已归档，不能刷新")
    mats.apply_system_scores(db, assessment_id)
    items = (
        db.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == assessment_id)
        .all()
    )
    # 没有指标明细的历史考核保留已记录总分，避免刷新覆盖奖金依据。
    if items:
        row.total_points = (
            None if any(i.awarded_points is None for i in items)
            else sum((i.awarded_points for i in items), Decimal("0"))
        )
    row.revision = int(row.revision or 1) + 1
    db.commit()
    return {
        "id": row.id,
        "revision": row.revision,
        "confirmed_revision": row.confirmed_revision,
        "needs_confirm": row.confirmed_revision != row.revision,
        "total_points": None if row.total_points is None else str(row.total_points),
    }


def archive_assessment(db: Session, assessment_id: int, *, fraud: bool = False) -> dict:
    from app.services.performance_rule_engine import brand_payroll, market_payroll

    row = _assessment(db, assessment_id)
    if row.status == "archived":
        return {"id": row.id, "status": row.status, "bonus_amount": None if row.bonus_amount is None else str(row.bonus_amount), "idempotent": True}
    if row.confirmed_revision != row.revision:
        raise HTTPException(status_code=400, detail="确认的不是当前版本，请重新确认")
    if row.total_points is None:
        raise HTTPException(status_code=400, detail="存在待补数据，不能归档")
    if not row.payroll_eligible:
        row.bonus_amount = None
        if (row.assessment_kind or "") == "onboarding" and not row.grade_label:
            from app.services.performance_assessment_flow import _apply_onboarding_grade

            _apply_onboarding_grade(row)
        row.status = "archived"
        db.commit()
        return {
            "id": row.id,
            "status": "archived",
            "payroll_eligible": False,
            "bonus_amount": None,
            "grade_label": row.grade_label,
        }
    if row.performance_base_snapshot is None:
        raise HTTPException(status_code=400, detail="缺少绩效基数，不能生成工资金额")
    tpl = _template(db, row.template_id) if row.template_id else None
    family = (tpl.family_code if tpl else "") or ""
    if family.startswith("BRAND"):
        pay = brand_payroll(row.total_points, row.performance_base_snapshot, fraud=fraud)
    else:
        pay = market_payroll(row.total_points, row.performance_base_snapshot)
    row.grade_label = pay["grade_label"]
    row.coefficient = pay["coefficient"]
    row.bonus_amount = pay["amount"]
    row.status = "archived"
    db.commit()
    return {
        "id": row.id,
        "status": row.status,
        "grade_label": row.grade_label,
        "bonus_amount": None if row.bonus_amount is None else str(row.bonus_amount),
        "payroll_eligible": True,
    }


ONBOARD_STAGE_MILESTONES = {"D5": 5, "M1": 30, "M3": 90}
ONBOARD_STAGE_LABELS = {"D5": "第5天(融入期)", "M1": "第1个月(成长期)", "M3": "第3个月(产出期)"}
ONBOARD_ROLE_LABELS = {"SALES": "业务岗", "FUNCTION": "职能岗"}
ONBOARD_ROLE_KINDS = ("SALES", "FUNCTION")
ONBOARD_STAGES = ("D5", "M1", "M3")


def _onboard_family_code(stage: str, role_kind: str) -> str:
    return f"ONBOARD_{(role_kind or '').upper()}_{(stage or '').upper()}"


def _resolve_onboard_template(db: Session, stage: str, role_kind: str):
    """按「阶段 + 岗类」找到对应的入职考核模板(必须已发布)。"""
    stage = (stage or "").upper()
    role_kind = (role_kind or "").upper()
    if stage not in ONBOARD_STAGES:
        raise HTTPException(status_code=422, detail={"code": "KPI_ONBOARDING_STAGE_INVALID",
                                                     "message": f"阶段必须是 {'/'.join(ONBOARD_STAGES)} 之一"})
    if role_kind not in ONBOARD_ROLE_KINDS:
        raise HTTPException(status_code=422, detail={"code": "KPI_ONBOARDING_ROLE_INVALID",
                                                     "message": f"岗类必须是 SALES(业务岗)/FUNCTION(职能岗) 之一"})
    family = _onboard_family_code(stage, role_kind)
    row = (
        db.query(PerformanceTemplate)
        .filter(PerformanceTemplate.family_code == family)
        .order_by(PerformanceTemplate.version.desc(), PerformanceTemplate.id.desc())
        .first()
    )
    if row is None:
        raise HTTPException(status_code=422, detail={
            "code": "KPI_ONBOARDING_TEMPLATE_MISSING",
            "message": f"未找到「{ONBOARD_ROLE_LABELS[role_kind]}·{ONBOARD_STAGE_LABELS[stage]}」的入职考核模板({family})，请先在模板管理中创建",
        })
    if (row.status or "") != "published":
        raise HTTPException(status_code=409, detail={
            "code": "KPI_ONBOARDING_TEMPLATE_NOT_PUBLISHED",
            "message": f"入职考核模板「{row.name}」尚未发布(当前状态 {row.status})，请先走审批并发布",
        })
    return row


def _resolve_onboard_cycle(db: Session, payload: dict, template):
    """周期：优先用传入的 cycle_id，否则用当月周期(不存在则创建)。"""
    from app.models.performance import PerformanceCycle

    cid = payload.get("cycle_id")
    if cid:
        row = db.query(PerformanceCycle).filter(PerformanceCycle.id == int(cid)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="考核周期不存在")
        return row
    from datetime import date as _date

    today = _date.today()
    label = f"{today.year}年{today.month}月"
    row = db.query(PerformanceCycle).filter(PerformanceCycle.period_label == label).first()
    if row is None:
        row = PerformanceCycle(period_label=label, cycle_type="monthly", default_template_id=template.id)
        db.add(row)
        db.flush()
    return row


def open_stage_case(db: Session, payload: dict) -> dict:
    """开立入职阶段考核：按「阶段 + 岗类」关联入职模板，并生成带指标的考核单。"""
    import json as _json
    from datetime import date as _date
    from datetime import timedelta

    from app.models.performance import (
        ASSESS_EMPLOYEE_PENDING,
        PerformanceActionLog,
        PerformanceAssessment,
        PerformanceAssessmentItem,
        PerformanceStageCase,
        PerformanceTemplateItem,
    )

    user_id = int(payload["user_id"])
    stage = (payload.get("stage") or "").upper()
    role_kind = (payload.get("role_kind") or "").upper()
    template = _resolve_onboard_template(db, stage, role_kind)

    employee = db.query(User).filter(User.id == user_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="员工不存在")
    if not employee.manager_id:
        raise HTTPException(status_code=422, detail={
            "code": "KPI_ONBOARDING_MANAGER_REQUIRED",
            "message": f"{employee.real_name} 未配置直属主管，无法生成评分流程；请先在员工档案里补上直属主管",
        })

    cycle = _resolve_onboard_cycle(db, payload, template)
    hire_id = int(payload.get("hire_event_id") or 0)
    instance_key = f"onboarding_{user_id}_{stage}_{cycle.id}"

    existing = (
        db.query(PerformanceAssessment)
        .filter(PerformanceAssessment.instance_key == instance_key)
        .first()
    )
    if existing is not None:
        case = (
            db.query(PerformanceStageCase)
            .filter(PerformanceStageCase.assessment_id == existing.id)
            .first()
        )
        return {"id": case.id if case else None, "instance_key": instance_key,
                "assessment_id": existing.id, "idempotent": True}

    items = (
        db.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == template.id)
        .order_by(PerformanceTemplateItem.order_no.asc(), PerformanceTemplateItem.id.asc())
        .all()
    )
    if not items:
        raise HTTPException(status_code=422, detail={
            "code": "KPI_ONBOARDING_TEMPLATE_EMPTY",
            "message": f"入职考核模板「{template.name}」没有配置指标，无法开案",
        })

    manager = db.query(User).filter(User.id == employee.manager_id).first() if employee.manager_id else None
    department = None
    if employee.department_id:
        from app.models.department import Department

        department = db.query(Department).filter(Department.id == employee.department_id).first()

    due_at = payload.get("due_at") or (_date.today() + timedelta(days=7)).isoformat()
    person_snapshot = {
        "user_id": employee.id,
        "name": employee.real_name,
        "department_id": employee.department_id,
        "department_name": department.name if department else None,
        "job_title": employee.job_title,
        "manager_id": employee.manager_id,
        "manager_name": manager.real_name if manager else None,
        "employment_type": employee.employment_status,
        "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
        "onboarding_stage": stage,
        "role_kind": role_kind,
    }
    template_snapshot = {
        "id": template.id,
        "name": template.name,
        "code": template.code,
        "version": template.version,
        "family_code": template.family_code,
        "definition_json": template.definition_json,
        "scoring_mode": template.scoring_mode,
        "engine_version": template.engine_version,
        "assessment_kind": template.assessment_kind,
    }
    workflow = {
        "hr_review_required": True,
        "employee_due_at": due_at,
        "manager_due_at": None,
        "hr_review_due_at": None,
        "confirm_due_at": None,
        "onboarding": {"stage": stage, "role_kind": role_kind, "hire_event_id": hire_id},
    }

    assessment = PerformanceAssessment(
        cycle_id=cycle.id,
        user_id=employee.id,
        department_id=employee.department_id,
        template_id=template.id,
        manager_id=employee.manager_id,
        current_handler_type="employee",
        current_handler_id=employee.id,
        person_snapshot_json=_json.dumps(person_snapshot, ensure_ascii=False),
        workflow_config_json=_json.dumps(workflow, ensure_ascii=False),
        template_snapshot_json=_json.dumps(template_snapshot, ensure_ascii=False),
        status=ASSESS_EMPLOYEE_PENDING,
        assessment_kind="onboarding",
        instance_key=instance_key,
        engine_version=template.engine_version or "kpi-v2",
        revision=1,
        evidence_status="待补充",
        payroll_eligible=False,
    )
    db.add(assessment)
    db.flush()

    for it in items:
        db.add(
            PerformanceAssessmentItem(
                assessment_id=assessment.id,
                template_item_id=it.id,
                order_no=it.order_no,
                name=it.name,
                weight=it.weight or Decimal("0"),
                data_source=it.data_source,
                source_ref=it.source_ref,
                target_value=it.target_value,
                score_rule=it.score_rule,
                metric_key=it.metric_key,
                max_points=it.max_points,
                data_state="pending",
                # 评分人从模板带过来（列优先，兼容写在 rule 里的）
                evaluator=template_item_evaluator(it),
            )
        )

    case = PerformanceStageCase(
        user_id=employee.id,
        hire_event_id=hire_id,
        stage=stage,
        role_kind=role_kind,
        due_at=due_at,
        assessment_id=assessment.id,
    )
    db.add(case)
    db.add(
        PerformanceActionLog(
            assessment_id=assessment.id,
            action="onboarding_open",
            from_status=None,
            to_status=ASSESS_EMPLOYEE_PENDING,
            note=f"入职考核开案：{ONBOARD_ROLE_LABELS[role_kind]}·{ONBOARD_STAGE_LABELS[stage]}",
            actor_id=None,
        )
    )
    db.commit()
    db.refresh(case)
    return {"id": case.id, "instance_key": instance_key, "assessment_id": assessment.id,
            "template_id": template.id, "template_name": template.name,
            "item_count": len(items), "idempotent": False}


def list_onboarding_candidates(db: Session, *, within_days: int = 180, grace_days: int = 30) -> list:
    """待开案候选：近 within_days 天入职的在职员工 + 各阶段到期情况。

    state:
      opened   已开案
      due      已到期待开案(到期日 <= 今天 <= 到期日 + grace_days)
      missed   已超期未开(超过宽限期，不再提示补开)
      upcoming 未到期
    """
    from datetime import date as _date
    from datetime import timedelta

    from app.models.department import Department
    from app.models.performance import PerformanceStageCase

    today = _date.today()
    users = (
        db.query(User)
        .filter(User.is_active.is_(True), User.hire_date.isnot(None))
        .all()
    )
    cases = db.query(PerformanceStageCase).all()
    case_map = {(c.user_id, c.stage): c for c in cases}
    dept_names = {d.id: d.name for d in db.query(Department).all()}
    mgr_names = {u.id: u.real_name for u in db.query(User).filter(User.is_active.is_(True)).all()}

    out = []
    for u in users:
        days = (today - u.hire_date).days
        if days < 0 or days > within_days:
            continue
        stages = []
        for stage in ONBOARD_STAGES:
            due = u.hire_date + timedelta(days=ONBOARD_STAGE_MILESTONES[stage])
            case = case_map.get((u.id, stage))
            if case is not None:
                state = "opened"
            elif today < due:
                state = "upcoming"
            elif today <= due + timedelta(days=grace_days):
                state = "due"
            else:
                state = "missed"
            stages.append(
                {
                    "stage": stage,
                    "stage_label": ONBOARD_STAGE_LABELS[stage],
                    "due_date": due.isoformat(),
                    "state": state,
                    "case_id": case.id if case else None,
                    "assessment_id": case.assessment_id if case else None,
                }
            )
        out.append(
            {
                "user_id": u.id,
                "name": u.real_name,
                "department_id": u.department_id,
                "department_name": dept_names.get(u.department_id),
                "job_title": u.job_title,
                "manager_name": mgr_names.get(u.manager_id),
                "hire_date": u.hire_date.isoformat(),
                "days_since_hire": days,
                "stages": stages,
                "due_count": sum(1 for s in stages if s["state"] == "due"),
                "missed_count": sum(1 for s in stages if s["state"] == "missed"),
            }
        )
    out.sort(key=lambda r: (r["due_count"] == 0, -r["days_since_hire"]))
    return out


def open_observation(db: Session, payload: dict) -> dict:
    from decimal import Decimal as Dec

    from app.models.performance import PerformanceObservationCase
    from app.services.performance_rule_engine import observation_release

    row = PerformanceObservationCase(
        user_id=int(payload["user_id"]),
        status="open",
        retriggered=bool(payload.get("retriggered")),
        end_score=None if payload.get("end_score") in (None, "") else Dec(str(payload["end_score"])),
    )
    decision = observation_release(end_score=row.end_score, retriggered=row.retriggered)
    if decision == "release":
        row.status = "released"
    elif decision == "hr_todo":
        row.status = "hr_todo"
        row.hr_todo = "不自动解除，生成人事待办，不改基本工资"
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "status": row.status, "hr_todo": row.hr_todo}


def create_feedback(db: Session, payload: dict) -> dict:
    from app.models.performance import PerformanceFeedbackRecord

    row = PerformanceFeedbackRecord(
        form_type=payload["form_type"],
        subject_user_id=int(payload["subject_user_id"]),
        reviewer_user_id=payload.get("reviewer_user_id"),
        anonymous=bool(payload.get("anonymous")),
        score=None if payload.get("score") in (None, "") else Decimal(str(payload["score"])),
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _feedback_out(row, see_identity=True)


def list_feedback(db: Session, *, see_identity: bool) -> list:
    from app.models.performance import PerformanceFeedbackRecord

    rows = db.query(PerformanceFeedbackRecord).order_by(PerformanceFeedbackRecord.id.asc()).all()
    return [_feedback_out(row, see_identity=see_identity) for row in rows]


def preview_assessment(db: Session, assessment_id: int, actuals: dict) -> dict:
    from app.services.performance_rule_engine import score_definition

    row = _assessment(db, assessment_id)
    if row.status == "archived":
        raise HTTPException(status_code=409, detail="已归档，不能试算")
    if row.template_snapshot_json:
        defn = json.loads(row.template_snapshot_json)
    elif row.template_id:
        defn = json.loads(_template(db, row.template_id).definition_json or "{}")
    else:
        defn = {}
    return _public_score(score_definition(defn, actuals))


def lecturer_status(db: Session, user_id: int) -> dict:
    from app.models.performance import PerformanceFeedbackRecord
    from app.services.performance_rule_engine import lecturer_incompetent

    count = (
        db.query(PerformanceFeedbackRecord)
        .filter(
            PerformanceFeedbackRecord.subject_user_id == user_id,
            PerformanceFeedbackRecord.form_type == "complaint",
            PerformanceFeedbackRecord.status == "confirmed",
        )
        .count()
    )
    return {"user_id": user_id, "valid_complaints": count, "incompetent": lecturer_incompetent(count)}


def list_stage_cases(db: Session) -> list:
    from app.models.performance import PerformanceAssessment, PerformanceStageCase

    rows = db.query(PerformanceStageCase).order_by(PerformanceStageCase.id.desc()).all()
    user_names = {u.id: u.real_name for u in db.query(User).all()}
    assess_status = {
        a.id: a.status
        for a in db.query(PerformanceAssessment).all()
    }
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "user_name": user_names.get(row.user_id),
            "hire_event_id": row.hire_event_id,
            "stage": row.stage,
            "stage_label": ONBOARD_STAGE_LABELS.get(row.stage, row.stage),
            "role_kind": row.role_kind,
            "role_label": ONBOARD_ROLE_LABELS.get(row.role_kind, row.role_kind),
            "due_at": row.due_at,
            "assessment_id": row.assessment_id,
            "assessment_status": assess_status.get(row.assessment_id) if row.assessment_id else None,
        }
        for row in rows
    ]


def list_onboarding_candidates_api(db: Session, *, within_days: int = 180) -> dict:
    """待开案候选 + 统计(供前端「入职考核」页面使用)。"""
    rows = list_onboarding_candidates(db, within_days=within_days)
    return {
        "within_days": within_days,
        "candidates": rows,
        "due_total": sum(r["due_count"] for r in rows),
    }


def list_observations(db: Session) -> list:
    from app.models.performance import PerformanceObservationCase

    rows = db.query(PerformanceObservationCase).order_by(PerformanceObservationCase.id.asc()).all()
    return [
        {"id": row.id, "user_id": row.user_id, "status": row.status, "hr_todo": row.hr_todo}
        for row in rows
    ]


def _public_score(result: dict) -> dict:
    lines = []
    for line in result["lines"]:
        lines.append({
            **line,
            "max_points": None if line.get("max_points") is None else str(line["max_points"]),
            "awarded_points": None if line.get("awarded_points") is None else str(line["awarded_points"]),
        })
    total = result.get("total_points")
    return {
        "lines": lines,
        "total_points": None if total is None else str(total),
        "formal": result.get("formal"),
        "engine_version": result.get("engine_version"),
        "scoring_mode": result.get("scoring_mode"),
    }


def _feedback_out(row, *, see_identity: bool) -> dict:
    reviewer = row.reviewer_user_id
    if row.anonymous and not see_identity:
        reviewer = None
    return {
        "id": row.id,
        "form_type": row.form_type,
        "subject_user_id": row.subject_user_id,
        "reviewer_user_id": reviewer,
        "anonymous": row.anonymous,
        "score": None if row.score is None else str(row.score),
        "status": row.status,
    }

