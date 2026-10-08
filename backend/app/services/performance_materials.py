"""材料任务：按模板要求与事实缺失动态生成。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.performance import (
    ASSESS_APPEAL_PENDING,
    ASSESS_COMPLETED,
    ASSESS_EMPLOYEE_CONFIRM_PENDING,
    ASSESS_EMPLOYEE_PENDING,
    ASSESS_HR_REVIEW_PENDING,
    MATERIAL_DRAFT,
    MATERIAL_PENDING,
    MATERIAL_RETURNED,
    MATERIAL_SUBMITTED,
    MATERIAL_VERIFIED,
    PerformanceAssessment,
    PerformanceAssessmentItem,
    PerformanceMaterialTask,
    PerformanceMetricFact,
    PerformanceTemplateItem,
)
from app.models.user import User


def _loads(raw: Optional[str]) -> Any:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _assessment(db: Session, assessment_id: int) -> PerformanceAssessment:
    row = db.query(PerformanceAssessment).filter(PerformanceAssessment.id == assessment_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="考核单不存在")
    return row


def _task(db: Session, task_id: int) -> PerformanceMaterialTask:
    row = db.query(PerformanceMaterialTask).filter(PerformanceMaterialTask.id == task_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="材料任务不存在")
    return row


def _require_not_completed(assessment: PerformanceAssessment) -> None:
    if assessment.status == ASSESS_COMPLETED or assessment.completed_at is not None:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "已完成考核只读"})


def _is_event_ledger(assessment: PerformanceAssessment) -> bool:
    """讲师事件台账：员工只填发生次数，不走「提交材料」任务。"""
    raw = assessment.template_snapshot_json
    if not raw:
        return False
    try:
        snap = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except json.JSONDecodeError:
        return False
    if not isinstance(snap, dict):
        return False
    if snap.get("scoring_mode") == "event_ledger":
        return True
    defn = snap.get("definition_json")
    if isinstance(defn, str):
        try:
            defn = json.loads(defn)
        except json.JSONDecodeError:
            defn = None
    if isinstance(defn, dict) and defn.get("scoring_mode") == "event_ledger":
        return True
    return False


def generate_material_tasks(db: Session, assessment_id: int) -> list[PerformanceMaterialTask]:
    assessment = _assessment(db, assessment_id)
    # 事件台账无独立材料填报页，勿生成「提交材料」任务（次数已在指标「实际」中）
    if _is_event_ledger(assessment):
        return []
    items = (
        db.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == assessment_id)
        .all()
    )
    created: list[PerformanceMaterialTask] = []
    for aitem in items:
        tpl_item = None
        if aitem.template_item_id:
            tpl_item = (
                db.query(PerformanceTemplateItem)
                .filter(PerformanceTemplateItem.id == aitem.template_item_id)
                .first()
            )
        handling = (tpl_item.handling_mode if tpl_item else None) or "system_auto"
        evidence = _loads(tpl_item.evidence_policy_json if tpl_item else None)
        required_fields = list(evidence.get("required_fields") or [])

        if handling == "manager_score":
            continue
        if handling == "system_auto" and not required_fields:
            continue

        facts = []
        if aitem.metric_key:
            facts = (
                db.query(PerformanceMetricFact)
                .filter(
                    PerformanceMetricFact.metric_key == aitem.metric_key,
                    PerformanceMetricFact.owner_id == assessment.user_id,
                )
                .all()
            )

        if handling == "employee_submit":
            source_type = "employee_submit"
            source_id = f"item_{aitem.id}"
            existing = (
                db.query(PerformanceMaterialTask)
                .filter_by(
                    assessment_id=assessment_id,
                    assessment_item_id=aitem.id,
                    source_record_type=source_type,
                    source_record_id=source_id,
                )
                .first()
            )
            if existing:
                continue
            task = PerformanceMaterialTask(
                assessment_id=assessment_id,
                assessment_item_id=aitem.id,
                source_record_type=source_type,
                source_record_id=source_id,
                title=f"提交材料：{aitem.name}",
                existing_data_json=None,
                missing_fields_json=json.dumps(required_fields or ["content"], ensure_ascii=False),
                requirement_text=evidence.get("requirement_text") or f"请提交「{aitem.name}」相关材料",
                status=MATERIAL_PENDING,
                revision=assessment.revision or 1,
            )
            db.add(task)
            created.append(task)
            continue

        if handling in ("system_supplement", "system_auto"):
            if not facts:
                # 无业务记录：system_supplement 表示「系统缺失时员工补充」
                # 未配 evidence_policy 时默认要求补 value（与手工台账字段对齐）
                if handling == "system_supplement":
                    gap_fields = required_fields or ["value"]
                    source_type = "metric_gap"
                    source_id = aitem.metric_key or f"item_{aitem.id}"
                    if (
                        db.query(PerformanceMaterialTask)
                        .filter_by(
                            assessment_id=assessment_id,
                            assessment_item_id=aitem.id,
                            source_record_type=source_type,
                            source_record_id=source_id,
                        )
                        .first()
                    ):
                        continue
                    task = PerformanceMaterialTask(
                        assessment_id=assessment_id,
                        assessment_item_id=aitem.id,
                        source_record_type=source_type,
                        source_record_id=source_id,
                        title=f"补充数据：{aitem.name}",
                        existing_data_json=None,
                        missing_fields_json=json.dumps(gap_fields, ensure_ascii=False),
                        requirement_text=(
                            evidence.get("requirement_text")
                            or f"系统缺少「{aitem.name}」数据，请补充"
                        ),
                        status=MATERIAL_PENDING,
                        revision=assessment.revision or 1,
                    )
                    db.add(task)
                    created.append(task)
                continue

            if not required_fields:
                continue

            for fact in facts:
                existing_data = {
                    "value": str(fact.value) if fact.value is not None else None,
                    "unit": fact.unit,
                    "source_record_id": fact.source_record_id,
                    "status": fact.status,
                }
                # 事实行可携带扩展 JSON：暂无 unit/project_ref 近似；缺失字段按 required_fields 相对已有键判断
                present = {k for k, v in existing_data.items() if v not in (None, "")}
                # 业务扩展字段若未在现有事实中，一律视为缺失（如 customer_industry）
                missing = [f for f in required_fields if f not in present]
                if not missing:
                    continue
                source_type = "metric_fact"
                source_id = fact.source_record_id
                if (
                    db.query(PerformanceMaterialTask)
                    .filter_by(
                        assessment_id=assessment_id,
                        assessment_item_id=aitem.id,
                        source_record_type=source_type,
                        source_record_id=source_id,
                    )
                    .first()
                ):
                    continue
                task = PerformanceMaterialTask(
                    assessment_id=assessment_id,
                    assessment_item_id=aitem.id,
                    source_record_type=source_type,
                    source_record_id=source_id,
                    title=f"补充字段：{aitem.name} / {fact.source_record_id}",
                    existing_data_json=json.dumps(existing_data, ensure_ascii=False),
                    missing_fields_json=json.dumps(missing, ensure_ascii=False),
                    requirement_text=f"请补充缺失字段：{', '.join(missing)}",
                    status=MATERIAL_PENDING,
                    revision=assessment.revision or 1,
                )
                db.add(task)
                created.append(task)
    db.flush()
    return created


def list_material_tasks(db: Session, assessment_id: int, user: User, *, manage: bool = False) -> list[dict]:
    assessment = _assessment(db, assessment_id)
    if not manage and assessment.user_id != user.id and assessment.manager_id != user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "KPI_MATERIAL_FORBIDDEN",
                "message": "无权查看材料任务：仅被考核人、其主管，或具备绩效管理权限（admin/hr）的用户可查看",
                "details": {
                    "assessment_id": assessment_id,
                    "assessment_user_id": assessment.user_id,
                    "assessment_manager_id": assessment.manager_id,
                },
            },
        )
    # 讲师事件台账：历史误生成的「提交材料」任务不展示（员工从未单独交材料）
    if _is_event_ledger(assessment):
        return []
    rows = (
        db.query(PerformanceMaterialTask)
        .filter(PerformanceMaterialTask.assessment_id == assessment_id)
        .order_by(PerformanceMaterialTask.id.asc())
        .all()
    )
    return [task_out(r) for r in rows]


def save_draft(db: Session, task_id: int, user: User, content: str) -> dict:
    task = _task(db, task_id)
    assessment = _assessment(db, task.assessment_id)
    _require_not_completed(assessment)
    if assessment.user_id != user.id:
        raise HTTPException(status_code=403, detail="只能编辑本人材料")
    editable = {MATERIAL_PENDING, MATERIAL_DRAFT, MATERIAL_RETURNED}
    # 考核仍在员工阶段时，允许改「已提交但未核实」的材料（例如退回后重填，或前端批量保存）
    if (
        assessment.status == ASSESS_EMPLOYEE_PENDING
        and task.status == MATERIAL_SUBMITTED
        and task.verified_at is None
    ):
        editable = editable | {MATERIAL_SUBMITTED}
    if task.status not in editable:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "KPI_ACTION_NOT_ALLOWED",
                "message": f"材料「{task.title}」当前状态为 {task.status}，不可再编辑草稿",
                "details": {
                    "task_id": task_id,
                    "status": task.status,
                    "assessment_status": assessment.status,
                    "editable_when": ["pending", "draft", "returned", "submitted(仅员工阶段且未核实)"],
                },
            },
        )
    task.employee_content = content
    task.status = MATERIAL_DRAFT
    task.submitted_at = None
    db.commit()
    db.refresh(task)
    return task_out(task)


def return_task(db: Session, task_id: int, user: User, reason: str) -> dict:
    task = _task(db, task_id)
    assessment = _assessment(db, task.assessment_id)
    _require_not_completed(assessment)
    if assessment.manager_id != user.id:
        raise HTTPException(status_code=403, detail="仅主管可退回材料")
    if task.status != MATERIAL_SUBMITTED:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "仅已提交材料可退回"})
    task.status = MATERIAL_RETURNED
    task.return_reason = reason
    assessment.status = ASSESS_EMPLOYEE_PENDING
    assessment.current_handler_type = "employee"
    assessment.current_handler_id = assessment.user_id
    db.commit()
    db.refresh(task)
    return task_out(task)


def verify_task(db: Session, task_id: int, user: User) -> dict:
    task = _task(db, task_id)
    assessment = _assessment(db, task.assessment_id)
    _require_not_completed(assessment)
    if assessment.manager_id != user.id:
        raise HTTPException(status_code=403, detail="仅主管可核实材料")
    if task.status != MATERIAL_SUBMITTED:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "仅已提交材料可核实"})
    task.status = MATERIAL_VERIFIED
    task.verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task_out(task)


def mark_tasks_submitted(db: Session, assessment_id: int) -> None:
    assert_materials_ready_for_submit(db, assessment_id)
    submit_all_drafts(db, assessment_id)


def sync_material_drafts_from_actuals(db: Session, assessment_id: int) -> int:
    """简化填报：员工只填指标实际值时，用实际值补齐对应材料草稿，避免提交被卡住。"""
    items = {
        row.id: row
        for row in db.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == assessment_id)
        .all()
    }
    rows = (
        db.query(PerformanceMaterialTask)
        .filter(PerformanceMaterialTask.assessment_id == assessment_id)
        .all()
    )
    synced = 0
    for task in rows:
        if task.status not in (MATERIAL_PENDING, MATERIAL_RETURNED, MATERIAL_DRAFT):
            continue
        if (task.employee_content or "").strip():
            # 已有内容的草稿只确保状态可提交
            if task.status in (MATERIAL_PENDING, MATERIAL_RETURNED):
                task.status = MATERIAL_DRAFT
                synced += 1
            continue
        item = items.get(task.assessment_item_id) if task.assessment_item_id else None
        actual = (item.actual_value or "").strip() if item is not None else ""
        if not actual:
            continue
        task.employee_content = actual
        task.status = MATERIAL_DRAFT
        synced += 1
    return synced


def assert_materials_ready_for_submit(db: Session, assessment_id: int) -> None:
    assessment = _assessment(db, assessment_id)
    if _is_event_ledger(assessment):
        return
    rows = (
        db.query(PerformanceMaterialTask)
        .filter(PerformanceMaterialTask.assessment_id == assessment_id)
        .all()
    )
    for task in rows:
        if task.status in (MATERIAL_PENDING, MATERIAL_RETURNED):
            raise HTTPException(
                status_code=409,
                detail={"code": "KPI_MATERIAL_INCOMPLETE", "message": f"必填材料未完成：{task.title}"},
            )
        if task.status == MATERIAL_DRAFT and not (task.employee_content or "").strip():
            raise HTTPException(
                status_code=409,
                detail={"code": "KPI_MATERIAL_INCOMPLETE", "message": f"材料未填写：{task.title}"},
            )


def submit_all_drafts(db: Session, assessment_id: int) -> None:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(PerformanceMaterialTask)
        .filter(PerformanceMaterialTask.assessment_id == assessment_id)
        .all()
    )
    for task in rows:
        if task.status == MATERIAL_DRAFT:
            task.status = MATERIAL_SUBMITTED
            task.submitted_at = now
            _sync_item_actual_from_task(db, task)
        elif task.status in (MATERIAL_SUBMITTED, MATERIAL_VERIFIED):
            # 已提交但未回写的 actual，补同步
            _sync_item_actual_from_task(db, task)


def _sync_item_actual_from_task(db: Session, task: PerformanceMaterialTask) -> None:
    """把员工补充内容回写到考核项实际值，供指标表展示与后续计分。"""
    content = (task.employee_content or "").strip()
    if not content or not task.assessment_item_id:
        return
    item = (
        db.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.id == task.assessment_item_id)
        .first()
    )
    if item is None:
        return
    # 已有系统实际值时不覆盖
    if item.actual_value not in (None, ""):
        return
    item.actual_value = content


def _event_points_from_actual(item: PerformanceAssessmentItem) -> Optional[Decimal]:
    """事件加减分：实际次数 × 单次分值。区间项（如 2~5）交主管评，返回 None。"""
    rule = (item.score_rule or "").strip()
    if rule not in ("event_bonus", "event_deduction"):
        return None
    raw = (item.actual_value or "").strip()
    if not raw:
        return None
    try:
        actual = Decimal(raw)
    except Exception:
        return None
    tv = (item.target_value or "").strip()
    if not tv or "~" in tv:
        return None
    sign = Decimal("1") if rule == "event_bonus" else Decimal("-1")
    try:
        if "/" in tv:
            left, right = tv.split("/", 1)
            per, unit = Decimal(left.strip()), Decimal(right.strip())
            if unit == 0:
                return None
            pts = (actual / unit) * per * sign
        else:
            pts = actual * Decimal(tv) * sign
    except Exception:
        return None
    return pts.quantize(Decimal("0.01"))


def apply_system_scores(db: Session, assessment_id: int) -> int:
    """事件加减分按实际自动计分；其余仍由主管填写。"""
    items = (
        db.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == assessment_id)
        .all()
    )
    n = 0
    for item in items:
        pts = _event_points_from_actual(item)
        if pts is None:
            continue
        changed = False
        if item.system_score != pts:
            item.system_score = pts
            changed = True
        # 主管尚未改分时，用系统分作为得分
        if item.leader_score is None and (
            item.awarded_points != pts or item.final_score != pts
        ):
            item.awarded_points = pts
            item.final_score = pts
            changed = True
        if changed:
            n += 1
    if n:
        db.flush()
    return n


def enrich_assessment_items(
    db: Session,
    assessment_id: int,
    items: list[PerformanceAssessmentItem],
) -> list[PerformanceAssessmentItem]:
    """为指标行附带材料展示字段：display_actual / material_* / score_label。"""
    assessment = (
        db.query(PerformanceAssessment)
        .filter(PerformanceAssessment.id == assessment_id)
        .first()
    )
    status = assessment.status if assessment else None
    # 主管已提交之后，不再用「待核实」（那是主管阶段用语）
    post_manager = status in (
        ASSESS_EMPLOYEE_CONFIRM_PENDING,
        ASSESS_APPEAL_PENDING,
        ASSESS_COMPLETED,
        ASSESS_HR_REVIEW_PENDING,
    )

    tasks = (
        db.query(PerformanceMaterialTask)
        .filter(PerformanceMaterialTask.assessment_id == assessment_id)
        .order_by(PerformanceMaterialTask.id.asc())
        .all()
    )
    by_item: dict[int, PerformanceMaterialTask] = {}
    priority = {
        MATERIAL_VERIFIED: 5,
        MATERIAL_SUBMITTED: 4,
        MATERIAL_DRAFT: 3,
        MATERIAL_RETURNED: 2,
        MATERIAL_PENDING: 1,
    }
    for task in tasks:
        if not task.assessment_item_id:
            continue
        prev = by_item.get(task.assessment_item_id)
        if prev is None or priority.get(task.status, 0) >= priority.get(prev.status, 0):
            by_item[task.assessment_item_id] = task

    for item in items:
        task = by_item.get(item.id)
        content = (task.employee_content or "").strip() if task else None
        if content == "":
            content = None
        actual = item.actual_value
        if actual is not None and str(actual).strip() == "":
            actual = None
        display = actual if actual is not None else content

        item.display_actual = display  # type: ignore[attr-defined]
        item.material_task_id = task.id if task else None  # type: ignore[attr-defined]
        item.material_status = task.status if task else None  # type: ignore[attr-defined]
        item.material_content = content  # type: ignore[attr-defined]

        tpl = None
        if item.template_item_id:
            tpl = db.get(PerformanceTemplateItem, item.template_item_id)
        item.handling_mode = tpl.handling_mode if tpl else None  # type: ignore[attr-defined]
        item.scoring_type = tpl.scoring_type if tpl else None  # type: ignore[attr-defined]

        if item.final_score is not None:
            item.score_label = str(item.final_score)  # type: ignore[attr-defined]
        elif item.leader_score is not None:
            item.score_label = str(item.leader_score)  # type: ignore[attr-defined]
        elif item.system_score is not None:
            item.score_label = str(item.system_score)  # type: ignore[attr-defined]
        elif post_manager:
            item.score_label = "未评分"  # type: ignore[attr-defined]
        elif task and task.status in (
            MATERIAL_SUBMITTED,
            MATERIAL_VERIFIED,
            MATERIAL_DRAFT,
            MATERIAL_PENDING,
            MATERIAL_RETURNED,
        ):
            item.score_label = "待核实"  # type: ignore[attr-defined]
        else:
            item.score_label = "待评分"  # type: ignore[attr-defined]
    return items


def items_payload(db: Session, assessment_id: int) -> list[dict[str, Any]]:
    items = (
        db.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == assessment_id)
        .order_by(PerformanceAssessmentItem.order_no.asc(), PerformanceAssessmentItem.id.asc())
        .all()
    )
    enrich_assessment_items(db, assessment_id, items)
    tip_ids = [i.template_item_id for i in items if i.template_item_id]
    hint_by_tpl: dict[int, Optional[str]] = {}
    if tip_ids:
        for tip in (
            db.query(PerformanceTemplateItem)
            .filter(PerformanceTemplateItem.id.in_(tip_ids))
            .all()
        ):
            hint_by_tpl[tip.id] = tip.hint
    out: list[dict[str, Any]] = []
    for item in items:
        out.append(
            {
                "id": item.id,
                "assessment_id": item.assessment_id,
                "template_item_id": item.template_item_id,
                "order_no": item.order_no,
                "name": item.name,
                "weight": str(item.weight) if item.weight is not None else None,
                "data_source": item.data_source,
                "source_ref": item.source_ref,
                "target_value": item.target_value,
                "score_rule": item.score_rule,
                "hint": hint_by_tpl.get(item.template_item_id) if item.template_item_id else None,
                "metric_key": item.metric_key,
                "actual_value": item.actual_value,
                "display_actual": getattr(item, "display_actual", None),
                "material_task_id": getattr(item, "material_task_id", None),
                "material_status": getattr(item, "material_status", None),
                "material_content": getattr(item, "material_content", None),
                "system_score": str(item.system_score) if item.system_score is not None else None,
                "self_score": str(item.self_score) if item.self_score is not None else None,
                "leader_score": str(item.leader_score) if item.leader_score is not None else None,
                "final_score": str(item.final_score) if item.final_score is not None else None,
                "awarded_points": str(item.awarded_points) if item.awarded_points is not None else None,
                "score_label": getattr(item, "score_label", None),
                "handling_mode": getattr(item, "handling_mode", None),
                "scoring_type": getattr(item, "scoring_type", None),
            }
        )
    return out


def task_out(row: PerformanceMaterialTask) -> dict:
    missing = []
    if row.missing_fields_json:
        try:
            missing = json.loads(row.missing_fields_json)
        except json.JSONDecodeError:
            missing = []
    return {
        "id": row.id,
        "assessment_id": row.assessment_id,
        "assessment_item_id": row.assessment_item_id,
        "source_record_type": row.source_record_type,
        "source_record_id": row.source_record_id,
        "title": row.title,
        "existing_data": _loads(row.existing_data_json) if row.existing_data_json else None,
        "missing_fields": missing,
        "requirement_text": row.requirement_text,
        "employee_content": row.employee_content,
        "status": row.status,
        "return_reason": row.return_reason,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        "revision": row.revision,
    }
