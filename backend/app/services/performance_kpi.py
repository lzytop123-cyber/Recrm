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
        row.status = "archived"
        db.commit()
        return {"id": row.id, "status": "archived", "payroll_eligible": False, "bonus_amount": None}
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


def open_stage_case(db: Session, payload: dict) -> dict:
    from app.models.performance import PerformanceAssessment, PerformanceStageCase

    stage = payload["stage"]
    hire_id = int(payload["hire_event_id"])
    key = f"onboarding:{hire_id}:{stage}"
    case = (
        db.query(PerformanceStageCase)
        .filter(
            PerformanceStageCase.user_id == int(payload["user_id"]),
            PerformanceStageCase.hire_event_id == hire_id,
            PerformanceStageCase.stage == stage,
        )
        .first()
    )
    if case:
        return {"id": case.id, "instance_key": key, "assessment_id": case.assessment_id, "idempotent": True}
    assessment_id = None
    if payload.get("cycle_id"):
        assessment = PerformanceAssessment(
            cycle_id=int(payload["cycle_id"]),
            user_id=int(payload["user_id"]),
            instance_key=key,
            assessment_kind="onboarding",
            engine_version="kpi-v2",
            payroll_eligible=False,
            status="pending_self",
        )
        db.add(assessment)
        db.flush()
        assessment_id = assessment.id
    case = PerformanceStageCase(
        user_id=int(payload["user_id"]),
        hire_event_id=hire_id,
        stage=stage,
        role_kind=payload["role_kind"],
        due_at=payload.get("due_at"),
        assessment_id=assessment_id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return {"id": case.id, "instance_key": key, "assessment_id": assessment_id, "idempotent": False}


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
    from app.models.performance import PerformanceStageCase

    rows = db.query(PerformanceStageCase).order_by(PerformanceStageCase.id.asc()).all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "hire_event_id": row.hire_event_id,
            "stage": row.stage,
            "role_kind": row.role_kind,
            "assessment_id": row.assessment_id,
        }
        for row in rows
    ]


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

