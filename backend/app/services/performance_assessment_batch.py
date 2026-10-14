"""批量发起考核：幂等、事务、人员/模板快照；支持多模板一次发起与进度看板。"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.performance import (
    ASSESS_EMPLOYEE_PENDING,
    BATCH_STATUS_LAUNCHED,
    PerformanceActionLog,
    PerformanceAssessment,
    PerformanceAssessmentBatch,
    PerformanceAssessmentItem,
    PerformanceCycle,
    PerformanceTemplate,
    PerformanceTemplateItem,
)
from app.models.user import User
from app.services.employment_status import is_resigned
# 进度看板/往期名单在 performance_batch_progress，这里保留原导入路径
from app.services.performance_batch_progress import (  # noqa: F401
    _sees_all_batches,
    _visible_batch_ids,
    batch_out,
    batch_progress_out,
    current_month_cycle_id,
    get_batch_progress,
    list_assessment_history,
    list_cycle_batch_progress,
    multi_batch_out,
    resolve_list_cycle_id,
)
from app.services.performance_personnel_matcher import match_personnel
from app.services.performance_template import item_evaluator, require_published_for_launch

_BLOCKED_HINTS = {
    "duplicate_assessment": "本周期已存在相同模板（或同系列）考核，不能重复发起",
    "missing_manager": "缺少直属主管，无法生成考核单",
}

def _assert_not_resigned_for_include(person: dict[str, Any], *, user_id: int, field: str) -> None:
    """离职/停用：即使前端勾选并填写原因，也不允许纳入考核。"""
    is_active = bool(person.get("is_active", True))
    status = person.get("employment_status")
    if not is_resigned(status, is_active=is_active):
        return
    name = person.get("name") or f"用户{user_id}"
    raise HTTPException(
        status_code=422,
        detail={
            "code": "KPI_PERSON_RESIGNED",
            "message": f"{name}已离职或停用，不可纳入考核",
            "field": field,
            "details": {
                "user_id": user_id,
                "name": name,
                "is_active": is_active,
                "employment_status": status,
                "how_to_fix": "请取消勾选该人员后再发起",
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

    _validate_deadlines(payload)
    # 一次匹配：范围外的手动添加人员作为 extra 进入名单，走"手动纳入+必填原因"
    match_result = match_personnel(
        db,
        cycle_id=cycle_id,
        template_id=template_id,
        extra_user_ids=[int(r["user_id"]) for r in people_in],
    )
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
            _assert_not_resigned_for_include(matched, user_id=uid, field=f"people[{idx}].user_id")
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
                    # 评分人从模板带过来（列优先，兼容写在 rule 里的）
                    evaluator=item_evaluator(it),
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

    launched: list[tuple[PerformanceAssessmentBatch, list[int]]] = []
    try:
        for index, row in enumerate(batches_in):
            # 允许同一人出现在多个模板批次（跨团队考核）；考核单 instance_key 按批次区分
            people = row.get("people") or []
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


def search_addable_personnel(
    db: Session,
    *,
    cycle_id: int,
    template_id: int,
    keyword: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """搜索可**手动添加**进本模板考核的人员（范围外，部门/岗位不符）。

    仅返回不在模板适用范围内的在职人员，附带 blocked 信息：
    - addable=True 且 blocked_reason 为空 → 可添加（发起时必须填写原因）
    - blocked_reason 非空（离职/停用、无主管、本周期已有同模板考核）→ 不可添加
    """
    from sqlalchemy import or_

    kw = (keyword or "").strip()
    q = db.query(User).filter(User.is_active.is_(True))
    if kw:
        like = f"%{kw}%"
        q = q.filter(or_(User.real_name.ilike(like), User.job_title.ilike(like), User.username.ilike(like)))
    rows = q.order_by(User.id.desc()).limit(max(1, min(limit, 50))).all()

    probe_ids = [u.id for u in rows]
    if not probe_ids:
        return []
    probed = match_personnel(
        db, cycle_id=cycle_id, template_id=template_id, extra_user_ids=probe_ids
    )
    in_scope_ids = {int(uid) for uid in probed.get("in_scope_user_ids") or []}
    by_id = {int(p["user_id"]): p for p in (probed.get("people") or [])}

    out: list[dict[str, Any]] = []
    for u in rows:
        if u.id in in_scope_ids:
            continue  # 已在适用范围内，不需要手动添加
        info = by_id.get(u.id) or {}
        blocked = info.get("match_status") == "blocked" or info.get("allowed_action") == "none"
        reason = info.get("reason") if blocked else None
        out.append(
            {
                "user_id": u.id,
                "name": u.real_name,
                "job_title": u.job_title,
                "department_id": u.department_id,
                "department_name": info.get("department_name") or info.get("department"),
                "manager_id": u.manager_id,
                "employment_status": u.employment_status,
                "addable": not blocked,
                "blocked_reason": reason,
                "match_status": info.get("match_status"),
                "reason_code": info.get("reason_code"),
            }
        )
    return out


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

