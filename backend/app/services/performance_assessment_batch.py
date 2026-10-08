"""批量发起考核：幂等、事务、人员/模板快照；支持多模板一次发起与进度看板。"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.performance import (
    ASSESS_APPEAL_PENDING,
    ASSESS_COMPLETED,
    ASSESS_EMPLOYEE_CONFIRM_PENDING,
    ASSESS_EMPLOYEE_PENDING,
    ASSESS_HR_REVIEW_PENDING,
    ASSESS_MANAGER_PENDING,
    BATCH_STATUS_LAUNCHED,
    PerformanceActionLog,
    PerformanceAssessment,
    PerformanceAssessmentBatch,
    PerformanceAssessmentItem,
    PerformanceCycle,
    PerformanceTemplate,
    PerformanceTemplateItem,
    PerformanceTemplateScope,
)
from app.core.rbac import collect_permission_codes
from app.models.user import User
from app.services.performance_personnel_matcher import match_personnel
from app.services.performance_template import require_published_for_launch

_BLOCKED_HINTS = {
    "duplicate_assessment": "本周期已存在相同模板（或同系列）考核，不能重复发起",
    "missing_manager": "缺少直属主管，无法生成考核单",
}

# 离职/停用：即使前端勾选并填写原因，也不允许纳入考核
_RESIGNED_EMPLOYMENT_STATUSES = frozenset({"离职", "resigned", "inactive"})


def _is_resigned_or_disabled(user: User) -> bool:
    if not user.is_active:
        return True
    status = (user.employment_status or "").strip()
    if status in _RESIGNED_EMPLOYMENT_STATUSES:
        return True
    return status.lower() in _RESIGNED_EMPLOYMENT_STATUSES


def _assert_not_resigned_for_include(
    db: Session, *, user_id: int, person_name: str, field: str
) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "KPI_PERSON_NOT_FOUND",
                "message": f"用户 {user_id} 不存在",
                "field": field,
            },
        )
    if not _is_resigned_or_disabled(user):
        return
    name = person_name or user.real_name or user.username or f"用户{user_id}"
    raise HTTPException(
        status_code=422,
        detail={
            "code": "KPI_PERSON_RESIGNED",
            "message": f"{name}已离职或停用，不可纳入考核",
            "field": field,
            "details": {
                "user_id": user_id,
                "name": name,
                "is_active": user.is_active,
                "employment_status": user.employment_status,
                "how_to_fix": "请取消勾选该人员后再发起",
            },
        },
    )


def _assert_no_launched_batch_for_template(
    db: Session, *, cycle_id: int, template_id: int
) -> None:
    existing = (
        db.query(PerformanceAssessmentBatch)
        .filter(
            PerformanceAssessmentBatch.cycle_id == cycle_id,
            PerformanceAssessmentBatch.template_id == template_id,
            PerformanceAssessmentBatch.status == BATCH_STATUS_LAUNCHED,
        )
        .order_by(PerformanceAssessmentBatch.id.asc())
        .first()
    )
    if existing is None:
        return
    tpl = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    tpl_name = (tpl.name if tpl else None) or f"模板{template_id}"
    raise HTTPException(
        status_code=409,
        detail={
            "code": "KPI_TEMPLATE_BATCH_EXISTS",
            "message": f"本周期「{tpl_name}」已发起考核，不能重复发起",
            "details": {
                "cycle_id": cycle_id,
                "template_id": template_id,
                "existing_batch_id": existing.id,
                "how_to_fix": "请在本期已有批次中继续处理，或先取消原批次后再重新发起",
            },
        },
    )


def _blocked_http_detail(
    *,
    person: dict[str, Any],
    field: str,
    code: str,
) -> dict[str, Any]:
    """把 blocked 原因拆清楚，方便前端直接展示。"""
    name = person.get("name") or f"用户{person.get('user_id')}"
    reason_code = person.get("reason_code") or "blocked"
    reason = person.get("reason") or _BLOCKED_HINTS.get(reason_code) or "该人员当前不可发起考核"
    hint = _BLOCKED_HINTS.get(reason_code)
    message = f"{name}无法发起：{reason}"
    if hint and hint not in reason:
        message = f"{name}无法发起：{hint}"
    return {
        "code": code,
        "message": message,
        "field": field,
        "details": {
            "user_id": person.get("user_id"),
            "name": name,
            "match_status": person.get("match_status"),
            "reason_code": reason_code,
            "reason": reason,
            "existing_assessment_id": person.get("existing_assessment_id"),
            "how_to_fix": (
                "请从名单中取消勾选该人员，或先处理已有考核单后再发起"
                if reason_code == "duplicate_assessment"
                else "请先在组织人事中为该员工配置直属主管，再重新匹配并发起"
                if reason_code == "missing_manager"
                else "请根据 reason 处理后重新匹配人员"
            ),
        },
    }


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "+00:00")
    # 兼容 "2026-10-01 18:00:00" / "2026-10-01T18:00:00"
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    return datetime.fromisoformat(text)


def _validate_deadlines(payload: dict[str, Any]) -> None:
    manager = _parse_dt(payload.get("manager_due_at"))
    confirm = _parse_dt(payload.get("confirm_due_at"))
    chain = [manager, confirm]
    prev = None
    for item in chain:
        if item is None:
            raise HTTPException(
                status_code=422,
                detail={"code": "KPI_DEADLINE_ORDER_INVALID", "message": "截止时间不完整"},
            )
        if prev is not None and item <= prev:
            raise HTTPException(
                status_code=422,
                detail={"code": "KPI_DEADLINE_ORDER_INVALID", "message": "截止时间必须按顺序递增"},
            )
        prev = item


def _index_match(result: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(p["user_id"]): p for p in result["people"]}


def _group_key_prefix(idempotency_key: str) -> str:
    return f"{idempotency_key}|"


def _child_idempotency_key(group_key: str, index: int, template_id: int) -> str:
    return f"{group_key}|{index}|t{template_id}"


def _find_group_batches(db: Session, group_key: str) -> list[PerformanceAssessmentBatch]:
    prefix = _group_key_prefix(group_key)
    return (
        db.query(PerformanceAssessmentBatch)
        .filter(PerformanceAssessmentBatch.idempotency_key.like(prefix + "%"))
        .order_by(PerformanceAssessmentBatch.id.asc())
        .all()
    )


def _launch_one_batch(
    db: Session,
    user: User,
    payload: dict[str, Any],
    *,
    idempotency_key: str,
) -> tuple[PerformanceAssessmentBatch, list[int]]:
    """创建单个模板批次（不 commit）；调用方负责事务边界。"""
    cycle_id = int(payload["cycle_id"])
    template_id = int(payload["template_id"])
    people_in = payload.get("people") or []
    if not people_in:
        raise HTTPException(status_code=422, detail="people 不能为空")

    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
    if cycle is None:
        raise HTTPException(status_code=404, detail="考核周期不存在")
    require_published_for_launch(db, template_id, cycle=cycle)
    template = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=404, detail="考核模板不存在")

    _assert_no_launched_batch_for_template(db, cycle_id=cycle_id, template_id=template_id)
    _validate_deadlines(payload)
    match_result = match_personnel(db, cycle_id=cycle_id, template_id=template_id)
    by_id = _index_match(match_result)

    selected_ids: list[int] = []
    for idx, row in enumerate(people_in):
        uid = int(row["user_id"])
        selected = bool(row.get("selected"))
        reason = (row.get("adjustment_reason") or "").strip() or None
        matched = by_id.get(uid)
        if matched is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "KPI_PERSON_OUT_OF_SCOPE",
                    "message": f"用户 {uid} 不在本次模板匹配范围（部门/岗位不符），请先调用 match-personnel 核对名单",
                    "field": f"people[{idx}].user_id",
                    "details": {
                        "user_id": uid,
                        "how_to_fix": "只提交 match-personnel 返回的 people 中的用户",
                    },
                },
            )
        if selected:
            _assert_not_resigned_for_include(
                db,
                user_id=uid,
                person_name=str(matched.get("name") or ""),
                field=f"people[{idx}].user_id",
            )
        if matched["match_status"] == "blocked" and selected:
            raise HTTPException(
                status_code=409,
                detail=_blocked_http_detail(
                    person={**matched, "user_id": uid},
                    field=f"people[{idx}].user_id",
                    code="KPI_PERSON_BLOCKED",
                ),
            )
        if matched["match_status"] == "matched" and not selected and not reason:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "KPI_PERSON_EXCLUDED_REASON_REQUIRED",
                    "message": f"排除自动匹配人员{matched['name']}时必须填写原因",
                    "field": f"people[{idx}].adjustment_reason",
                },
            )
        if matched["match_status"] == "excluded" and selected and not reason:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "KPI_PERSON_EXCLUDED_REASON_REQUIRED",
                    "message": f"手动纳入{matched['name']}时必须填写原因",
                    "field": f"people[{idx}].adjustment_reason",
                },
            )
        if selected:
            selected_ids.append(uid)

    if not selected_ids:
        raise HTTPException(status_code=422, detail="至少选择1人")

    for uid in selected_ids:
        again = match_personnel(db, cycle_id=cycle_id, template_id=template_id)
        person = _index_match(again).get(uid)
        if person and person["match_status"] == "blocked":
            raise HTTPException(
                status_code=409,
                detail=_blocked_http_detail(
                    person={**person, "user_id": uid},
                    field="people",
                    code="KPI_BATCH_DUPLICATE",
                ),
            )

    batch = PerformanceAssessmentBatch(
        cycle_id=cycle_id,
        template_id=template_id,
        status=BATCH_STATUS_LAUNCHED,
        employee_due_at=_parse_dt(payload.get("employee_due_at")),
        manager_due_at=_parse_dt(payload.get("manager_due_at")),
        hr_review_due_at=_parse_dt(payload.get("hr_review_due_at")),
        confirm_due_at=_parse_dt(payload.get("confirm_due_at")),
        hr_review_required=bool(payload.get("hr_review_required")),
        idempotency_key=idempotency_key,
        created_by=user.id,
    )
    db.add(batch)
    db.flush()

    items = (
        db.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == template_id)
        .order_by(PerformanceTemplateItem.order_no.asc(), PerformanceTemplateItem.id.asc())
        .all()
    )
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
        "hr_review_required": bool(payload.get("hr_review_required")),
        "employee_due_at": payload.get("employee_due_at"),
        "manager_due_at": payload.get("manager_due_at"),
        "hr_review_due_at": payload.get("hr_review_due_at"),
        "confirm_due_at": payload.get("confirm_due_at"),
    }

    created_ids: list[int] = []
    people_by_request = {int(p["user_id"]): p for p in people_in}
    for uid in selected_ids:
        matched = by_id[uid]
        req = people_by_request[uid]
        reason = (req.get("adjustment_reason") or "").strip() or None
        adjustment_type = "automatic"
        if matched["match_status"] == "excluded":
            adjustment_type = "manual_include"
        elif matched["match_status"] == "matched" and reason:
            adjustment_type = "manual_note"

        person_snapshot = {
            "user_id": matched["user_id"],
            "name": matched["name"],
            "department_id": matched["department_id"],
            "department_name": matched["department_name"],
            "job_title": matched["job_title"],
            "manager_id": matched["manager_id"],
            "manager_name": matched["manager_name"],
            "employment_type": matched["employment_type"],
            "employment_status": matched.get("employment_status"),
            "days_in_period": matched["days_in_period"],
            "match_status": matched["match_status"],
            "match_reason": matched["reason"],
            "reason_code": matched["reason_code"],
            "adjustment_type": adjustment_type,
            "adjustment_reason": reason,
            "template_version": template.version,
        }
        assessment = PerformanceAssessment(
            cycle_id=cycle_id,
            user_id=uid,
            department_id=matched["department_id"],
            template_id=template_id,
            batch_id=batch.id,
            manager_id=matched["manager_id"],
            current_handler_type="employee",
            current_handler_id=uid,
            person_snapshot_json=json.dumps(person_snapshot, ensure_ascii=False),
            workflow_config_json=json.dumps(workflow, ensure_ascii=False),
            template_snapshot_json=json.dumps(template_snapshot, ensure_ascii=False),
            status=ASSESS_EMPLOYEE_PENDING,
            assessment_kind=template.assessment_kind or "monthly",
            instance_key=f"batch_{batch.id}_{uid}",
            engine_version=template.engine_version or "kpi-v2",
            revision=1,
            evidence_status="待补充",
        )
        db.add(assessment)
        db.flush()
        created_ids.append(assessment.id)
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
                    evaluator=getattr(it, "evaluator", None),
                )
            )
        db.add(
            PerformanceActionLog(
                assessment_id=assessment.id,
                action="batch_launch",
                from_status=None,
                to_status=ASSESS_EMPLOYEE_PENDING,
                actor_id=user.id,
                note="批量发起",
                payload_json=json.dumps({"batch_id": batch.id}, ensure_ascii=False),
            )
        )

    db.flush()
    from app.services import performance_materials as materials

    for aid in created_ids:
        materials.generate_material_tasks(db, aid)

    return batch, created_ids


def create_assessment_batch(
    db: Session,
    user: User,
    payload: dict[str, Any],
    *,
    idempotency_key: str,
) -> dict[str, Any]:
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="缺少 Idempotency-Key")
    existing = (
        db.query(PerformanceAssessmentBatch)
        .filter(PerformanceAssessmentBatch.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return batch_out(db, existing, idempotent=True)

    batch, created_ids = _launch_one_batch(db, user, payload, idempotency_key=idempotency_key)
    db.commit()
    db.refresh(batch)
    return batch_out(db, batch, idempotent=False, assessment_ids=created_ids)


def create_multi_assessment_batches(
    db: Session,
    user: User,
    payload: dict[str, Any],
    *,
    idempotency_key: str,
) -> dict[str, Any]:
    """同一周期下一次发起多个部门模板批次；整组幂等、同事务。"""
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="缺少 Idempotency-Key")

    existing = _find_group_batches(db, idempotency_key)
    if existing:
        return multi_batch_out(db, existing, group_key=idempotency_key, idempotent=True)

    cycle_id = int(payload["cycle_id"])
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
    if cycle is None:
        raise HTTPException(status_code=404, detail="考核周期不存在")

    batches_in = payload.get("batches") or []
    if not isinstance(batches_in, list) or not batches_in:
        raise HTTPException(status_code=422, detail="batches 不能为空")

    shared = {
        "cycle_id": cycle_id,
        "employee_due_at": payload.get("employee_due_at"),
        "manager_due_at": payload.get("manager_due_at"),
        "hr_review_required": bool(payload.get("hr_review_required")),
        "hr_review_due_at": payload.get("hr_review_due_at"),
        "confirm_due_at": payload.get("confirm_due_at"),
    }
    _validate_deadlines(shared)

    template_ids = [int(b["template_id"]) for b in batches_in]
    if len(template_ids) != len(set(template_ids)):
        raise HTTPException(
            status_code=422,
            detail={"code": "KPI_MULTI_TEMPLATE_DUPLICATE", "message": "同一请求中不能重复同一模板"},
        )

    seen_users: set[int] = set()
    launched: list[tuple[PerformanceAssessmentBatch, list[int]]] = []
    try:
        for index, row in enumerate(batches_in):
            people = row.get("people") or []
            for p in people:
                if not bool(p.get("selected", True)):
                    continue
                uid = int(p["user_id"])
                if uid in seen_users:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "code": "KPI_MULTI_PERSON_DUPLICATE",
                            "message": f"用户 {uid} 不能同时出现在多个考核批次中",
                            "field": f"batches[{index}].people",
                        },
                    )
                seen_users.add(uid)

            one = {
                **shared,
                "template_id": int(row["template_id"]),
                "people": people,
            }
            child_key = _child_idempotency_key(idempotency_key, index, int(row["template_id"]))
            batch, ids = _launch_one_batch(db, user, one, idempotency_key=child_key)
            launched.append((batch, ids))
        db.commit()
    except Exception:
        db.rollback()
        raise

    for batch, _ in launched:
        db.refresh(batch)
    return multi_batch_out(
        db,
        [b for b, _ in launched],
        group_key=idempotency_key,
        idempotent=False,
        assessment_ids_by_batch={b.id: ids for b, ids in launched},
    )


def match_personnel_multi(db: Session, *, cycle_id: int, template_ids: list[int]) -> dict[str, Any]:
    if not template_ids:
        raise HTTPException(status_code=422, detail="template_ids 不能为空")
    if len(template_ids) != len(set(template_ids)):
        raise HTTPException(status_code=422, detail="template_ids 不能重复")
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
    if cycle is None:
        raise HTTPException(status_code=404, detail="考核周期不存在")
    results = []
    for tid in template_ids:
        require_published_for_launch(db, tid, cycle=cycle)
        results.append(match_personnel(db, cycle_id=cycle_id, template_id=tid))
    return {"cycle_id": cycle_id, "results": results}


def _status_counts(rows: list[PerformanceAssessment]) -> dict[str, int]:
    counts = {
        "total": len(rows),
        "pending_employee": 0,
        "pending_manager": 0,
        "pending_hr_review": 0,
        "pending_confirm": 0,
        "appealing": 0,
        "completed": 0,
        "other": 0,
    }
    for r in rows:
        s = r.status
        if s == ASSESS_EMPLOYEE_PENDING:
            counts["pending_employee"] += 1
        elif s == ASSESS_MANAGER_PENDING:
            counts["pending_manager"] += 1
        elif s == ASSESS_HR_REVIEW_PENDING:
            counts["pending_hr_review"] += 1
        elif s == ASSESS_EMPLOYEE_CONFIRM_PENDING:
            counts["pending_confirm"] += 1
        elif s == ASSESS_APPEAL_PENDING:
            counts["appealing"] += 1
        elif s == ASSESS_COMPLETED:
            counts["completed"] += 1
        else:
            counts["other"] += 1
    return counts


def _template_scope_label(db: Session, template_id: int) -> dict[str, Any]:
    scope = (
        db.query(PerformanceTemplateScope)
        .filter(PerformanceTemplateScope.template_id == template_id)
        .order_by(PerformanceTemplateScope.id.asc())
        .first()
    )
    if not scope:
        return {"department_id": None, "department_name": None, "job_title": None}
    dept = db.query(Department).filter(Department.id == scope.department_id).first()
    return {
        "department_id": scope.department_id,
        "department_name": dept.name if dept else None,
        "job_title": scope.job_title,
    }


def _person_snapshot(assessment: PerformanceAssessment) -> dict[str, Any]:
    try:
        data = json.loads(assessment.person_snapshot_json or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _people_out(db: Session, assessments: list[PerformanceAssessment]) -> list[dict[str, Any]]:
    """批次人员，含发起时的直属主管。"""
    people = []
    for assessment in assessments:
        snap = _person_snapshot(assessment)
        manager_id = assessment.manager_id or snap.get("manager_id")
        manager_name = snap.get("manager_name")
        if manager_id and not manager_name:
            manager = db.query(User).filter(User.id == manager_id).first()
            if manager:
                manager_name = manager.real_name or manager.username
        people.append(
            {
                "assessment_id": assessment.id,
                "user_id": assessment.user_id,
                "name": snap.get("name"),
                "department_name": snap.get("department_name"),
                "job_title": snap.get("job_title"),
                "manager_id": manager_id,
                "manager_name": manager_name,
                "status": "hr_review" if assessment.status == ASSESS_HR_REVIEW_PENDING else assessment.status,
                "current_handler_type": assessment.current_handler_type,
                "current_handler_id": assessment.current_handler_id,
            }
        )
    return people


def batch_progress_out(db: Session, batch: PerformanceAssessmentBatch) -> dict[str, Any]:
    assessments = (
        db.query(PerformanceAssessment)
        .filter(PerformanceAssessment.batch_id == batch.id)
        .order_by(PerformanceAssessment.id.asc())
        .all()
    )
    tpl = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == batch.template_id).first()
    scope = _template_scope_label(db, batch.template_id)
    # 若范围缺失，回退人员快照部门
    if not scope["department_name"] and assessments:
        try:
            snap = json.loads(assessments[0].person_snapshot_json or "{}")
            scope = {
                "department_id": snap.get("department_id"),
                "department_name": snap.get("department_name"),
                "job_title": snap.get("job_title"),
            }
        except json.JSONDecodeError:
            pass
    counts = _status_counts(assessments)
    people = _people_out(db, assessments)
    manager_ids = {p["manager_id"] for p in people if p["manager_id"]}
    manager_id = next(iter(manager_ids)) if len(manager_ids) == 1 else None
    manager_name = next((p["manager_name"] for p in people if p["manager_id"] == manager_id), None) if manager_id else None
    base = batch_out(db, batch, assessment_ids=[a.id for a in assessments])
    base.update(
        {
            "template_name": tpl.name if tpl else None,
            "template_version": tpl.version if tpl else None,
            "department_id": scope["department_id"],
            "department_name": scope["department_name"],
            "job_title": scope["job_title"],
            "manager_id": manager_id,
            "manager_name": manager_name,
            "people": people,
            **counts,
        }
    )
    return base


def current_month_cycle_id(db: Session) -> Optional[int]:
    """当前自然月对应的周期。同月有多条时取 id 最大的一条。"""
    from app.services.performance_data_source import _parse_year_month

    today = date.today()
    target = (today.year, today.month)
    rows = db.query(PerformanceCycle).order_by(PerformanceCycle.id.desc()).all()
    for row in rows:
        if _parse_year_month(row.period_label or "") == target:
            return row.id
    return None


def resolve_list_cycle_id(db: Session, cycle_id: Optional[int] = None) -> Optional[int]:
    """列表默认周期：优先本月；没有本月时回退到最近一条。"""
    if cycle_id is not None:
        return cycle_id
    return current_month_cycle_id(db) or (
        db.query(PerformanceCycle.id).order_by(PerformanceCycle.id.desc()).limit(1).scalar()
    )


def _sees_all_batches(user: User) -> bool:
    if "admin" in {r.code for r in (user.roles or [])}:
        return True
    codes = collect_permission_codes(user)
    return "*" in codes or "kpi:template:manage" in codes


def _visible_batch_ids(db: Session, user: User, cycle_id: Optional[int] = None) -> Optional[set[int]]:
    """模板管理员看全部；其他人只看本人或直属下属所在批次。"""
    if _sees_all_batches(user):
        return None
    subordinate_ids = db.query(User.id).filter(User.manager_id == user.id)
    q = db.query(PerformanceAssessment.batch_id).filter(
        PerformanceAssessment.batch_id.isnot(None),
        (PerformanceAssessment.user_id == user.id) | (PerformanceAssessment.user_id.in_(subordinate_ids)),
    )
    if cycle_id is not None:
        q = q.filter(PerformanceAssessment.cycle_id == cycle_id)
    return {row[0] for row in q.all() if row[0] is not None}


def list_cycle_batch_progress(db: Session, cycle_id: int, user: Optional[User] = None) -> dict[str, Any]:
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
    if cycle is None:
        raise HTTPException(status_code=404, detail="考核周期不存在")
    batches = (
        db.query(PerformanceAssessmentBatch)
        .filter(PerformanceAssessmentBatch.cycle_id == cycle_id)
        .order_by(PerformanceAssessmentBatch.id.asc())
        .all()
    )
    if user is not None:
        visible = _visible_batch_ids(db, user, cycle_id)
        if visible is not None:
            batches = [b for b in batches if b.id in visible]
    rows = [batch_progress_out(db, b) for b in batches]
    totals = {
        "batch_count": len(rows),
        "total": sum(r["total"] for r in rows),
        "pending_employee": sum(r["pending_employee"] for r in rows),
        "pending_manager": sum(r["pending_manager"] for r in rows),
        "pending_hr_review": sum(r["pending_hr_review"] for r in rows),
        "pending_confirm": sum(r["pending_confirm"] for r in rows),
        "appealing": sum(r["appealing"] for r in rows),
        "completed": sum(r["completed"] for r in rows),
    }
    # 按部门名聚合（同名多模板 / 多 department_id 合并成一行）
    by_dept: dict[str, dict[str, Any]] = {}
    for r in rows:
        name = (r.get("department_name") or "").strip() or "未分组"
        key = name
        if key not in by_dept:
            by_dept[key] = {
                "department_id": r.get("department_id"),
                "department_name": name,
                "batch_ids": [],
                "template_names": [],
                "total": 0,
                "pending_employee": 0,
                "pending_manager": 0,
                "pending_hr_review": 0,
                "pending_confirm": 0,
                "appealing": 0,
                "completed": 0,
            }
        d = by_dept[key]
        if d.get("department_id") is None and r.get("department_id") is not None:
            d["department_id"] = r.get("department_id")
        d["batch_ids"].append(r["id"])
        if r.get("template_name"):
            d["template_names"].append(r["template_name"])
        for k in (
            "total",
            "pending_employee",
            "pending_manager",
            "pending_hr_review",
            "pending_confirm",
            "appealing",
            "completed",
        ):
            d[k] += r[k]
    return {
        "cycle_id": cycle_id,
        "period_label": cycle.period_label,
        "hr_review_required": all(bool(r.get("hr_review_required")) for r in rows) if rows else False,
        "batches": rows,
        "departments": list(by_dept.values()),
        "totals": totals,
    }


def _history_score(assessment: PerformanceAssessment) -> Optional[Decimal]:
    if assessment.total_points is not None:
        return Decimal(assessment.total_points)
    if assessment.final_score is not None:
        return Decimal(assessment.final_score)
    return None


def _history_person(assessment: PerformanceAssessment) -> dict[str, Any]:
    try:
        data = json.loads(assessment.person_snapshot_json or "{}")
    except json.JSONDecodeError:
        data = {}
    return data if isinstance(data, dict) else {}


def list_assessment_history(
    db: Session,
    user: User,
    *,
    cycle_id: Optional[int] = None,
    department: Optional[str] = None,
    q: Optional[str] = None,
    sort: str = "default",
) -> dict[str, Any]:
    """往期考核名单：只含已完成考核单。HR 看全部；其他人看自己以及自己当考核主管的下属。"""
    from app.services.performance_data_source import _parse_year_month

    query = db.query(PerformanceAssessment).filter(
        PerformanceAssessment.status == ASSESS_COMPLETED
    )
    if not _sees_all_batches(user):
        query = query.filter(
            (PerformanceAssessment.user_id == user.id)
            | (PerformanceAssessment.manager_id == user.id)
        )
    visible = query.all()
    if _sees_all_batches(user):
        scope = "all"
    elif any(row.manager_id == user.id and row.user_id != user.id for row in visible):
        scope = "manager"
    else:
        scope = "self"

    cycle_ids = list({row.cycle_id for row in visible})
    cycles = {
        row.id: row
        for row in db.query(PerformanceCycle).filter(PerformanceCycle.id.in_(cycle_ids or [0])).all()
    }

    def _cycle_sort_key(cid: int) -> tuple:
        label = cycles[cid].period_label if cid in cycles else ""
        ym = _parse_year_month(label or "")
        # 新→旧；解析不出的排后面，再用 id 兜底
        return (0 if ym else 1, -(ym[0] if ym else 0), -(ym[1] if ym else 0), -cid)

    cycle_ids.sort(key=_cycle_sort_key)
    periods = [
        {"cycle_id": cid, "period_label": cycles[cid].period_label if cid in cycles else None}
        for cid in cycle_ids
    ]
    selected = cycle_id if cycle_id is not None else (cycle_ids[0] if cycle_ids else None)
    if selected is not None and selected not in cycles and cycle_id is not None:
        found = db.query(PerformanceCycle).filter(PerformanceCycle.id == selected).first()
        if found is None:
            raise HTTPException(status_code=404, detail="考核周期不存在")
        cycles[selected] = found
    in_cycle = [row for row in visible if row.cycle_id == selected]
    departments = sorted({
        (_history_person(row).get("department_name") or "")
        for row in in_cycle
        if _history_person(row).get("department_name")
    })
    needle = (q or "").strip().lower()
    dept = (department or "").strip()
    filtered = []
    for row in in_cycle:
        person = _history_person(row)
        name = person.get("name") or ""
        job = person.get("job_title") or ""
        manager = person.get("manager_name") or ""
        department_name = person.get("department_name") or ""
        if dept and department_name != dept:
            continue
        if needle and needle not in f"{name} {job} {manager}".lower():
            continue
        filtered.append(row)

    # periods 已按新→旧排；当前项的下一条即上期
    previous_id = None
    if selected in cycle_ids:
        idx = cycle_ids.index(selected)
        if idx + 1 < len(cycle_ids):
            previous_id = cycle_ids[idx + 1]
    previous_scores = {
        row.user_id: _history_score(row)
        for row in visible
        if row.cycle_id == previous_id
    }

    def _sort_key(row: PerformanceAssessment):
        score = _history_score(row)
        if sort == "high":
            return (score is None, -(score or 0))
        if sort == "low":
            return (score is None, score or 0)
        return (0, row.id)

    filtered.sort(key=_sort_key)
    items = []
    for row in filtered:
        person = _history_person(row)
        score = _history_score(row)
        previous = previous_scores.get(row.user_id)
        delta = None if score is None or previous is None else (score - previous)
        items.append({
            "assessment_id": row.id,
            "user_id": row.user_id,
            "name": person.get("name"),
            "department_name": person.get("department_name"),
            "job_title": person.get("job_title"),
            "manager_id": row.manager_id,
            "manager_name": person.get("manager_name"),
            "score": None if score is None else str(score.quantize(Decimal("0.01"))),
            "status": row.status,
            "previous_score": None if previous is None else str(previous.quantize(Decimal("0.01"))),
            "score_delta": None if delta is None else str(delta.quantize(Decimal("0.01"))),
        })
    numbers = [Decimal(item["score"]) for item in items if item["score"] is not None]
    return {
        "cycle_id": selected,
        "period_label": cycles[selected].period_label if selected in cycles else None,
        "scope": scope,
        "periods": periods,
        "departments": departments,
        "stats": {
            "count": len(items),
            "average": None if not numbers else str((sum(numbers) / len(numbers)).quantize(Decimal("0.1"))),
            "max_score": None if not numbers else str(max(numbers).quantize(Decimal("0.01"))),
            "department_count": len({item["department_name"] for item in items if item["department_name"]}),
        },
        "rows": items,
    }


def get_batch_progress(db: Session, batch_id: int, user: Optional[User] = None) -> dict[str, Any]:
    batch = db.query(PerformanceAssessmentBatch).filter(PerformanceAssessmentBatch.id == batch_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="考核批次不存在")
    if user is not None:
        visible = _visible_batch_ids(db, user)
        if visible is not None and batch_id not in visible:
            raise HTTPException(status_code=403, detail="无权查看该考核批次")
    return batch_progress_out(db, batch)


def batch_out(
    db: Session,
    batch: PerformanceAssessmentBatch,
    *,
    idempotent: bool = False,
    assessment_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    if assessment_ids is None:
        assessment_ids = [
            r.id
            for r in db.query(PerformanceAssessment)
            .filter(PerformanceAssessment.batch_id == batch.id)
            .order_by(PerformanceAssessment.id.asc())
            .all()
        ]
    return {
        "id": batch.id,
        "cycle_id": batch.cycle_id,
        "template_id": batch.template_id,
        "status": batch.status,
        "hr_review_required": batch.hr_review_required,
        "idempotency_key": batch.idempotency_key,
        "employee_due_at": batch.employee_due_at.isoformat() if batch.employee_due_at else None,
        "manager_due_at": batch.manager_due_at.isoformat() if batch.manager_due_at else None,
        "hr_review_due_at": batch.hr_review_due_at.isoformat() if batch.hr_review_due_at else None,
        "confirm_due_at": batch.confirm_due_at.isoformat() if batch.confirm_due_at else None,
        "created_by": batch.created_by,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "assessment_ids": assessment_ids,
        "idempotent": idempotent,
    }


def multi_batch_out(
    db: Session,
    batches: list[PerformanceAssessmentBatch],
    *,
    group_key: str,
    idempotent: bool = False,
    assessment_ids_by_batch: Optional[dict[int, list[int]]] = None,
) -> dict[str, Any]:
    items = []
    for b in batches:
        row = batch_progress_out(db, b)
        if assessment_ids_by_batch is not None and b.id in assessment_ids_by_batch:
            row["assessment_ids"] = assessment_ids_by_batch[b.id]
        row["idempotent"] = idempotent
        items.append(row)
    return {
        "group_key": group_key,
        "cycle_id": batches[0].cycle_id if batches else None,
        "hr_review_required": all(bool(b.hr_review_required) for b in batches) if batches else False,
        "batch_count": len(items),
        "batches": items,
        "assessment_count": sum(int(x.get("total") or 0) for x in items),
        "idempotent": idempotent,
    }
