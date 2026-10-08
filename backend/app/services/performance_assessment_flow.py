"""简化考核状态机：allowed_actions、revision、审计。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.rbac import collect_permission_codes
from app.models.performance import (
    ASSESS_APPEAL_PENDING,
    ASSESS_COMPLETED,
    ASSESS_EMPLOYEE_CONFIRM_PENDING,
    ASSESS_EMPLOYEE_PENDING,
    ASSESS_HR_REVIEW_PENDING,
    ASSESS_MANAGER_PENDING,
    ASSESS_TRAINING_PENDING,
    PerformanceActionLog,
    PerformanceAppeal,
    PerformanceAssessment,
    PerformanceAssessmentBatch,
    PerformanceAssessmentItem,
    PerformanceCycle,
    PerformanceMaterialTask,
    PerformanceTemplateItem,
)
from app.models.user import User
from app.services import performance_materials as materials

APPEAL_PENDING = "pending"


def _loads_obj(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _fmt_due(value: Any) -> str:
    if value is None or value == "":
        return "未设置"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text


def build_arrangement(db: Session, assessment: PerformanceAssessment) -> list[dict[str, str]]:
    """员工/主管页「安排 / 内容」摘要，避免前端多接口拼装。"""
    person = _loads_obj(assessment.person_snapshot_json)
    tpl = _loads_obj(assessment.template_snapshot_json)
    wf = _workflow(assessment)

    cycle = None
    if assessment.cycle_id:
        cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == assessment.cycle_id).first()
    period = (cycle.period_label if cycle else None) or "—"

    name = person.get("name") or f"用户{assessment.user_id}"
    dept = person.get("department_name") or "—"
    job = person.get("job_title") or "—"
    mgr = person.get("manager_name") or ""
    if not mgr and assessment.manager_id:
        manager = db.query(User).filter(User.id == assessment.manager_id).first()
        if manager:
            mgr = manager.real_name or manager.username or ""
    mgr = mgr or "—"

    adj = person.get("adjustment_type") or "automatic"
    if adj == "manual_include":
        reason = (person.get("adjustment_reason") or "").strip()
        match_way = f"HR手动纳入：{reason}" if reason else "HR手动纳入"
    elif adj == "manual_note":
        reason = (person.get("adjustment_reason") or "").strip()
        match_way = f"系统匹配（备注：{reason}）" if reason else "系统按模板范围自动匹配"
    else:
        match_way = "系统按模板范围自动匹配"

    tpl_name = tpl.get("name") or "—"
    tpl_ver = tpl.get("version")
    tpl_text = f"{tpl_name} · V{tpl_ver}" if tpl_ver is not None else tpl_name

    hr_required = _hr_review_required(db, assessment)
    onboarding = _is_onboarding(assessment)
    if onboarding:
        review_text = f"各部门主管评分（{mgr}） → 培训部评分"
        if hr_required:
            review_text = f"{review_text} → HR复核"
    else:
        review_text = f"各部门主管评分（{mgr}）"
        if hr_required:
            review_text = f"{review_text} / HR复核"

    due_parts = [
        f"各部门主管评分 {_fmt_due(wf.get('manager_due_at'))}",
    ]
    if onboarding:
        due_parts.append("培训部评分")
    if hr_required:
        due_parts.append(f"HR复核 {_fmt_due(wf.get('hr_review_due_at'))}")
    if onboarding:
        due_parts.append(f"三方确认 {_fmt_due(wf.get('confirm_due_at'))}")
    else:
        due_parts.append(f"员工结果确认 {_fmt_due(wf.get('confirm_due_at'))}")

    return [
        {"label": "周期", "value": period},
        {"label": "考核人员", "value": f"{name} · {dept} / {job} · 主管{mgr}"},
        {"label": "匹配方式", "value": match_way},
        {"label": "考核模板", "value": tpl_text},
        {"label": "评分人 / 复核", "value": review_text},
        {"label": "截止日期", "value": " → ".join(due_parts)},
    ]


def _assessment(db: Session, assessment_id: int) -> PerformanceAssessment:
    row = db.query(PerformanceAssessment).filter(PerformanceAssessment.id == assessment_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="考核单不存在")
    return row


def _workflow(assessment: PerformanceAssessment) -> dict:
    return _loads_obj(assessment.workflow_config_json)


ONBOARD_PASS_SCORE = 75


def _save_workflow(assessment: PerformanceAssessment, wf: dict) -> None:
    assessment.workflow_config_json = json.dumps(wf, ensure_ascii=False)


# 入职结果确认三方：直属主管 + 培训部 + HR（无需员工确认）
ONBOARD_CONFIRM_PARTIES = ("manager", "training", "hr")


def _confirmations(assessment: PerformanceAssessment) -> dict[str, Any]:
    wf = _workflow(assessment)
    conf = wf.get("confirmations")
    if not isinstance(conf, dict):
        return {"manager": None, "training": None, "hr": None}
    return {
        "manager": conf.get("manager"),
        "training": conf.get("training"),
        "hr": conf.get("hr"),
    }


def _ensure_confirmations(assessment: PerformanceAssessment) -> dict[str, Any]:
    wf = _workflow(assessment)
    conf = wf.get("confirmations")
    if not isinstance(conf, dict):
        wf["confirmations"] = {"manager": None, "training": None, "hr": None}
        _save_workflow(assessment, wf)
    else:
        # 兼容旧数据：去掉 employee 键，补齐 hr
        changed = False
        if "employee" in conf:
            conf.pop("employee", None)
            changed = True
        for k in ONBOARD_CONFIRM_PARTIES:
            if k not in conf:
                conf[k] = None
                changed = True
        if changed:
            wf["confirmations"] = conf
            _save_workflow(assessment, wf)
    return wf


def _onboarding_stage(assessment: PerformanceAssessment) -> str:
    wf = _workflow(assessment)
    onboard = wf.get("onboarding") if isinstance(wf.get("onboarding"), dict) else {}
    return str(onboard.get("stage") or "")


def _apply_onboarding_grade(assessment: PerformanceAssessment) -> None:
    """入职合格线 75：写 grade_label，不合格时挂 HR 人事跟进标记（不自动改雇佣）。"""
    score = assessment.final_score
    if score is None and assessment.total_points is not None:
        score = int(assessment.total_points)
    if score is None:
        assessment.grade_label = None
        return
    passed = int(score) >= ONBOARD_PASS_SCORE
    assessment.grade_label = "合格" if passed else "不合格"
    assessment.grade = assessment.grade_label
    wf = _workflow(assessment)
    stage = _onboarding_stage(assessment)
    if passed:
        wf.pop("hr_followup", None)
    else:
        consequence = "不予转正" if stage == "M3" else "不予留用"
        wf["hr_followup"] = {
            "needed": True,
            "resolved": False,
            "score": int(score),
            "pass_score": ONBOARD_PASS_SCORE,
            "stage": stage or None,
            "reason": f"入职考核不合格（{stage or '阶段未知'}，得分 {int(score)} < {ONBOARD_PASS_SCORE}），建议{consequence}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    _save_workflow(assessment, wf)


def _all_parties_confirmed(assessment: PerformanceAssessment) -> bool:
    conf = _confirmations(assessment)
    return all(conf.get(k) for k in ONBOARD_CONFIRM_PARTIES)


def _record_party_confirm(
    assessment: PerformanceAssessment, *, party: str, user: User
) -> dict[str, Any]:
    wf = _ensure_confirmations(assessment)
    conf = wf.setdefault("confirmations", {})
    conf[party] = {
        "user_id": user.id,
        "name": user.real_name or user.username,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    _save_workflow(assessment, wf)
    return conf


def _try_complete_onboarding(db: Session, assessment: PerformanceAssessment, user: User, *, action: str) -> bool:
    """三方都确认后完成入职考核并写合格结论。返回是否已完成。"""
    if not _all_parties_confirmed(assessment):
        return False
    from_status = assessment.status
    assessment.status = ASSESS_COMPLETED
    assessment.completed_at = datetime.now(timezone.utc)
    assessment.confirmed_revision = assessment.revision
    assessment.current_handler_type = None
    assessment.current_handler_id = None
    _apply_onboarding_grade(assessment)
    _bump(assessment)
    _log(
        db,
        assessment,
        action=action,
        actor_id=user.id,
        from_status=from_status,
        to_status=assessment.status,
        note=assessment.grade_label,
    )
    return True


def _hr_review_required(db: Session, assessment: PerformanceAssessment) -> bool:
    wf = _workflow(assessment)
    if "hr_review_required" in wf:
        return bool(wf.get("hr_review_required"))
    if assessment.batch_id:
        batch = (
            db.query(PerformanceAssessmentBatch)
            .filter(PerformanceAssessmentBatch.id == assessment.batch_id)
            .first()
        )
        if batch is not None:
            return bool(batch.hr_review_required)
    return False


def _is_hr(user: User) -> bool:
    codes = collect_permission_codes(user)
    role_codes = {r.code for r in (getattr(user, "roles", []) or [])}
    return (
        "*" in codes
        or "kpi:assessment:manage" in codes
        or "kpi:template:manage" in codes
        or "admin" in role_codes
        or "hr" in role_codes
    )


def _can_review(assessment: PerformanceAssessment, user: User) -> bool:
    """谁能操作「复核」节点。

    - 月度等其他考核：维持原逻辑（HR / 管理员 / 模板管理权限）。
    - 入职考核(onboarding)：培训部负责人（kpi:onboarding:manage）也可复核 —— 对应培训部制度里的
      「直属领导 + 培训部」双重考核。但若复核人与该单的评分主管是同一人（培训部内部新员工），
      则不给复核权限，交由 HR 兜底，避免自己评自己审。
    """
    if (assessment.assessment_kind or "") != "onboarding":
        return _is_hr(user)
    codes = collect_permission_codes(user)
    if not ("*" in codes or "kpi:onboarding:manage" in codes or _is_hr(user)):
        return False
    # HR / 管理员始终可复核（技术兜底）；培训部负责人不得复核自己评过或自己带的单
    if _is_hr(user):
        return True
    if assessment.manager_id and assessment.manager_id == user.id:
        return False
    if (
        getattr(assessment, "training_scorer_id", None)
        and assessment.training_scorer_id == user.id
    ):
        return False
    return True


def _check_revision(assessment: PerformanceAssessment, revision: int) -> None:
    if int(revision) != int(assessment.revision or 1):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "KPI_REVISION_CONFLICT",
                "message": "revision 已变化",
                "details": {"revision": assessment.revision},
            },
        )


def _bump(assessment: PerformanceAssessment) -> None:
    assessment.revision = int(assessment.revision or 1) + 1


def _log(
    db: Session,
    assessment: PerformanceAssessment,
    *,
    action: str,
    actor_id: Optional[int],
    from_status: Optional[str],
    to_status: Optional[str],
    note: Optional[str] = None,
    payload: Optional[dict] = None,
) -> None:
    db.add(
        PerformanceActionLog(
            assessment_id=assessment.id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            note=note,
            payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
        )
    )


def _public_status(status: str) -> str:
    """前端认 hr_review，不认 hr_review_pending。"""
    if status == ASSESS_HR_REVIEW_PENDING:
        return "hr_review"
    return status


def allowed_actions(assessment: PerformanceAssessment, user: User) -> list[str]:
    status = assessment.status
    actions: list[str] = []
    if status == ASSESS_COMPLETED:
        return []
    is_employee = assessment.user_id == user.id
    is_manager = assessment.manager_id == user.id
    is_hr = _is_hr(user)
    can_review = _can_review(assessment, user)

    if status == ASSESS_EMPLOYEE_PENDING and is_employee:
        actions.extend(["save_material_draft", "employee_submit"])
    if status == ASSESS_MANAGER_PENDING and is_manager:
        actions.extend(["manager_submit", "return_material", "verify_material"])
    if status == ASSESS_TRAINING_PENDING and _can_training_score(assessment, user):
        actions.append("training_submit")
    if status == ASSESS_HR_REVIEW_PENDING and can_review:
        actions.extend(["hr_approve", "hr_return"])
    if status == ASSESS_EMPLOYEE_CONFIRM_PENDING:
        if _is_onboarding(assessment):
            conf = _confirmations(assessment)
            if is_manager and not conf.get("manager"):
                actions.append("party_confirm")
            if _can_training_score(assessment, user) and not conf.get("training"):
                actions.append("party_confirm")
            if _is_hr(user) and not conf.get("hr"):
                actions.append("party_confirm")
            # 入职结果无需员工确认；员工仅可申诉
            if is_employee:
                actions.append("appeal")
        elif is_employee:
            actions.extend(["result_confirm", "appeal"])
    if status == ASSESS_APPEAL_PENDING and (
        is_hr or (_is_onboarding(assessment) and _can_training_score(assessment, user))
    ):
        actions.append("resolve_appeal")
    if is_hr and status != ASSESS_COMPLETED:
        actions.append("view_admin")
    # 去重保持顺序
    seen = set()
    out = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def next_step_label(assessment: PerformanceAssessment) -> str:
    if assessment.status == ASSESS_TRAINING_PENDING and _is_onboarding(assessment):
        # M3 无培训维度时仍走培训部确认节点
        return "培训部评分/确认"
    if assessment.status == ASSESS_EMPLOYEE_CONFIRM_PENDING and _is_onboarding(assessment):
        conf = _confirmations(assessment)
        missing = [k for k in ONBOARD_CONFIRM_PARTIES if not conf.get(k)]
        labels = {"manager": "主管确认", "training": "培训部确认", "hr": "HR确认"}
        if missing:
            return "三方确认：" + "、".join(labels[m] for m in missing)
        return "三方确认完成"
    mapping = {
        ASSESS_EMPLOYEE_PENDING: "员工填写实际并提交",
        ASSESS_MANAGER_PENDING: "各部门主管评分",
        ASSESS_TRAINING_PENDING: "培训部评分",
        ASSESS_HR_REVIEW_PENDING: "HR 复核",
        ASSESS_EMPLOYEE_CONFIRM_PENDING: "结果确认",
        ASSESS_APPEAL_PENDING: "处理申诉",
        ASSESS_COMPLETED: "已完成",
    }
    return mapping.get(assessment.status, assessment.status)


def detail_payload(db: Session, assessment: PerformanceAssessment, user: User) -> dict[str, Any]:
    missing = []
    tasks = (
        db.query(PerformanceMaterialTask)
        .filter(PerformanceMaterialTask.assessment_id == assessment.id)
        .all()
    )
    for t in tasks:
        if t.status in ("pending", "draft", "returned"):
            missing.append({"task_id": t.id, "title": t.title, "status": t.status})
    person = _loads_obj(assessment.person_snapshot_json)
    adj = person.get("adjustment_type")
    if adj == "manual_include":
        match_label = "人工纳入"
    elif adj == "manual_note":
        match_label = "系统匹配"
    elif adj == "automatic":
        match_label = "自动匹配"
    else:
        match_label = None
    manager_name = person.get("manager_name")
    if assessment.manager_id and not manager_name:
        manager = db.query(User).filter(User.id == assessment.manager_id).first()
        if manager:
            manager_name = manager.real_name or manager.username
    comment_row = (
        db.query(PerformanceAssessmentItem.self_comment)
        .filter(PerformanceAssessmentItem.assessment_id == assessment.id,
                PerformanceAssessmentItem.self_comment.isnot(None))
        .order_by(PerformanceAssessmentItem.order_no, PerformanceAssessmentItem.id)
        .first()
    )
    self_comment = comment_row[0] if comment_row is not None else None
    # 打开详情时补算事件加减分（修复历史单在自动计分关闭期间提交、得分一直为空）
    if assessment.status in (ASSESS_MANAGER_PENDING, ASSESS_EMPLOYEE_PENDING):
        if materials.apply_system_scores(db, assessment.id):
            db.commit()
            db.refresh(assessment)
    item_rows = materials.items_payload(db, assessment.id)
    tpl_snap = _loads_obj(assessment.template_snapshot_json)
    defn = _loads_obj(tpl_snap.get("definition_json") if isinstance(tpl_snap.get("definition_json"), str) else None)
    if not defn and isinstance(tpl_snap.get("definition_json"), dict):
        defn = tpl_snap["definition_json"]
    scoring_mode = tpl_snap.get("scoring_mode") or defn.get("scoring_mode") or "points_sum"
    # 讲师事件台账：满分取标称/起始分，不按各指标 weight（多为 0）合计
    if scoring_mode == "event_ledger":
        raw_full = (
            tpl_snap.get("nominal_total")
            or defn.get("nominal_total")
            or defn.get("base_points")
            or 100
        )
        full_points = Decimal(str(raw_full)).quantize(Decimal("0.01"))
    else:
        full_points = sum(
            (Decimal(row["weight"]) for row in item_rows if row.get("weight") not in (None, "")),
            Decimal("0"),
        ).quantize(Decimal("0.01"))
    appeal_row = (
        db.query(PerformanceAppeal)
        .filter(PerformanceAppeal.assessment_id == assessment.id)
        .order_by(PerformanceAppeal.id.desc())
        .first()
    )
    appeal = None
    if appeal_row:
        appeal = {
            "id": appeal_row.id,
            "status": appeal_row.status,
            "reason": appeal_row.reason,
            "resolution": appeal_row.resolution,
            "request_score": appeal_row.request_score,
        }
    return {
        "id": assessment.id,
        "status": _public_status(assessment.status),
        "current_handler_type": assessment.current_handler_type,
        "current_handler_id": assessment.current_handler_id,
        "next_step_label": next_step_label(assessment),
        "allowed_actions": allowed_actions(assessment, user),
        "material_gaps": missing,
        "arrangement": build_arrangement(db, assessment),
        "user_name": person.get("name"),
        "department_name": person.get("department_name"),
        "job_title": person.get("job_title"),
        "adjustment_type": adj,
        "adjustment_reason": person.get("adjustment_reason"),
        "match_label": match_label,
        "items": item_rows,
        "self_comment": self_comment,
        "manager_comment": assessment.manager_comment,
        "appeal": appeal,
        "revision": assessment.revision,
        "batch_id": assessment.batch_id,
        "manager_id": assessment.manager_id,
        "manager_name": manager_name,
        "user_id": assessment.user_id,
        "total_points": str(assessment.total_points) if assessment.total_points is not None else None,
        "full_points": str(full_points),
        "scoring_mode": scoring_mode,
        "hr_review_required": _hr_review_required(db, assessment),
        # 双评分（入职考核）：区分两个评分人，供前端分区块展示
        "assessment_kind": assessment.assessment_kind,
        "is_onboarding": _is_onboarding(assessment),
        "training_required": _is_onboarding(assessment) or _has_training_items(db, assessment.id),
        "training_ack_only": _is_onboarding(assessment) and not _has_training_items(db, assessment.id),
        "can_training_score": _can_training_score(assessment, user),
        "can_review": _can_review(assessment, user),
        "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else None,
        "grade_label": assessment.grade_label,
        "pass_score": ONBOARD_PASS_SCORE if _is_onboarding(assessment) else None,
        "confirmations": _confirmations(assessment) if _is_onboarding(assessment) else None,
        "hr_followup": (_workflow(assessment).get("hr_followup") if _is_onboarding(assessment) else None),
    }


def get_actions(db: Session, assessment_id: int, user: User) -> dict:
    assessment = _assessment(db, assessment_id)
    return {
        "assessment_id": assessment.id,
        "status": _public_status(assessment.status),
        "revision": assessment.revision,
        "allowed_actions": allowed_actions(assessment, user),
        "next_step_label": next_step_label(assessment),
        "current_handler_type": assessment.current_handler_type,
        "current_handler_id": assessment.current_handler_id,
    }



def _item_handling_mode(db: Session, item: PerformanceAssessmentItem) -> str:
    """取模板项填报归属；无模板时默认员工填。"""
    if not item.template_item_id:
        return "employee_submit"
    tip = db.get(PerformanceTemplateItem, item.template_item_id)
    mode = (tip.handling_mode if tip else None) or "employee_submit"
    return mode


def _employee_must_fill(db: Session, item: PerformanceAssessmentItem) -> bool:
    """员工提交时必须填写的项：employee_submit / system_supplement；主管专填跳过。"""
    mode = _item_handling_mode(db, item)
    return mode not in ("manager_score", "system_auto")


def _apply_actuals(
    db: Session, assessment_id: int, actuals: Optional[list[dict]], *,
    required: bool, allow_empty: bool = False,
) -> None:
    """写入指标实际值。required 时仅校验员工应填项（主管专填项跳过）。"""
    items = (
        db.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == assessment_id)
        .all()
    )
    by_id = {item.id: item for item in items}
    provided: dict[int, Optional[str]] = {}
    for row in actuals or []:
        item_id = int(row["item_id"])
        value = str(row.get("actual") or "").strip()
        if item_id not in by_id:
            raise HTTPException(status_code=404, detail="考核项不存在")
        if not value and allow_empty and not required:
            provided[item_id] = None
            continue
        if not value:
            raise HTTPException(status_code=422, detail={"code": "KPI_ACTUAL_REQUIRED", "message": f"请填写{by_id[item_id].name}的实际完成"})
        if len(value) > 60:
            raise HTTPException(status_code=422, detail={"code": "KPI_ACTUAL_TOO_LONG", "message": f"{by_id[item_id].name}的实际完成请控制在60字以内"})
        provided[item_id] = value
    if required:
        missing = [
            item.name for item in items
            if _employee_must_fill(db, item) and item.id not in provided
        ]
        if missing:
            raise HTTPException(
                status_code=422,
                detail={"code": "KPI_ACTUAL_REQUIRED", "message": "请填写每项指标的实际完成：" + "、".join(missing)},
            )
    for item_id, value in provided.items():
        by_id[item_id].actual_value = value


def employee_submit(
    db: Session, assessment_id: int, user: User, *, revision: int,
    actuals: Optional[list[dict]] = None, self_comment: Optional[str] = None,
    draft: bool = False,
) -> dict:
    assessment = _assessment(db, assessment_id)
    _check_revision(assessment, revision)
    if assessment.status != ASSESS_EMPLOYEE_PENDING:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "当前状态不可提交材料"})
    if assessment.user_id != user.id:
        raise HTTPException(status_code=403, detail="只能提交本人考核材料")
    _apply_actuals(db, assessment_id, actuals, required=not draft, allow_empty=draft)
    if self_comment is not None:
        # Reuse the existing item comment storage for the whole-assessment note.
        for item in db.query(PerformanceAssessmentItem).filter_by(assessment_id=assessment_id).all():
            item.self_comment = self_comment
    if draft:
        _bump(assessment)
        _log(db, assessment, action="employee_draft", actor_id=user.id,
             from_status=assessment.status, to_status=assessment.status, note=self_comment)
        db.commit()
        return detail_payload(db, assessment, user)
    # 员工页只填「实际」时，用实际值自动补齐材料草稿，再校验完整性
    materials.sync_material_drafts_from_actuals(db, assessment_id)
    materials.assert_materials_ready_for_submit(db, assessment_id)
    materials.submit_all_drafts(db, assessment_id)
    materials.apply_system_scores(db, assessment_id)
    from_status = assessment.status
    assessment.status = ASSESS_MANAGER_PENDING
    assessment.current_handler_type = "manager"
    assessment.current_handler_id = assessment.manager_id
    _bump(assessment)
    _log(db, assessment, action="employee_submit", actor_id=user.id, from_status=from_status, to_status=assessment.status)
    db.commit()
    return detail_payload(db, assessment, user)


def manager_submit(
    db: Session,
    assessment_id: int,
    user: User,
    *,
    revision: int,
    scores: Optional[list[dict]] = None,
    comment: Optional[str] = None,
    actuals: Optional[list[dict]] = None,
) -> dict:
    assessment = _assessment(db, assessment_id)
    _check_revision(assessment, revision)
    if assessment.status != ASSESS_MANAGER_PENDING:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "KPI_ACTION_NOT_ALLOWED",
                "message": "当前状态不可主管提交",
                "details": {"status": _public_status(assessment.status)},
            },
        )
    if assessment.manager_id != user.id and not _is_hr(user):
        raise HTTPException(status_code=403, detail="普通员工不能调用主管动作")
    _apply_actuals(db, assessment_id, actuals, required=False)
    materials.apply_system_scores(db, assessment_id)
    # 双评分：主管只评自己负责的维度（培训部维度由培训部评分节点处理）
    split = _has_training_items(db, assessment_id)
    missing = _apply_item_scores(
        db, assessment_id, scores, only_evaluator="manager" if split else None
    )
    if split and missing:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail={
                "code": "KPI_ITEM_SCORES_REQUIRED",
                "message": "还有未评分的指标：" + "、".join(i.name for i in missing),
                "items": [{"id": i.id, "name": i.name} for i in missing],
            },
        )
    _recalc_assessment_total(db, assessment)
    if comment:
        assessment.manager_comment = comment
    from_status = assessment.status
    if _is_onboarding(assessment):
        # 入职考核：主管评完一律进培训部节点（无培训维度时为确认/签字，见 training_ack_only）
        assessment.status = ASSESS_TRAINING_PENDING
        assessment.current_handler_type = "training"
        assessment.current_handler_id = None
    elif _hr_review_required(db, assessment):
        assessment.status = ASSESS_HR_REVIEW_PENDING
        assessment.current_handler_type = "hr"
        assessment.current_handler_id = None
    else:
        assessment.status = ASSESS_EMPLOYEE_CONFIRM_PENDING
        assessment.current_handler_type = "employee"
        assessment.current_handler_id = assessment.user_id
    _bump(assessment)
    _log(
        db,
        assessment,
        action="manager_submit",
        actor_id=user.id,
        from_status=from_status,
        to_status=assessment.status,
        note=comment,
    )
    db.commit()
    return detail_payload(db, assessment, user)


def training_submit(
    db: Session,
    assessment_id: int,
    user: User,
    *,
    revision: int,
    scores: Optional[list[dict]] = None,
    comment: Optional[str] = None,
) -> dict:
    """入职考核专属：培训部评分节点（只评 evaluator=training 的维度）。"""
    assessment = _assessment(db, assessment_id)
    _check_revision(assessment, revision)
    if assessment.status != ASSESS_TRAINING_PENDING:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "KPI_ACTION_NOT_ALLOWED",
                "message": "当前状态不可培训部提交",
                "details": {"status": _public_status(assessment.status)},
            },
        )
    if not _can_training_score(assessment, user):
        raise HTTPException(status_code=403, detail="需要培训部（或 HR）权限")
    has_training = _has_training_items(db, assessment_id)
    missing = (
        _apply_item_scores(db, assessment_id, scores, only_evaluator="training")
        if has_training
        else []
    )
    if has_training and missing:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail={
                "code": "KPI_ITEM_SCORES_REQUIRED",
                "message": "还有未评分的指标：" + "、".join(i.name for i in missing),
                "items": [{"id": i.id, "name": i.name} for i in missing],
            },
        )
    if has_training:
        _recalc_assessment_total(db, assessment)
    # 记录培训部评分/确认人，复核节点禁止自审
    assessment.training_scorer_id = user.id
    from_status = assessment.status
    if _hr_review_required(db, assessment):
        assessment.status = ASSESS_HR_REVIEW_PENDING
        assessment.current_handler_type = "hr"
        assessment.current_handler_id = None
    else:
        assessment.status = ASSESS_EMPLOYEE_CONFIRM_PENDING
        assessment.current_handler_type = "employee"
        assessment.current_handler_id = assessment.user_id
        if _is_onboarding(assessment):
            _ensure_confirmations(assessment)
    _bump(assessment)
    _log(
        db,
        assessment,
        action="training_submit",
        actor_id=user.id,
        from_status=from_status,
        to_status=assessment.status,
        note=comment,
    )
    db.commit()
    return detail_payload(db, assessment, user)


def hr_review(
    db: Session,
    assessment_id: int,
    user: User,
    *,
    revision: int,
    approve: bool = True,
    note: Optional[str] = None,
) -> dict:
    assessment = _assessment(db, assessment_id)
    _check_revision(assessment, revision)
    if not _can_review(assessment, user):
        raise HTTPException(
            status_code=403,
            detail=(
                "该考核单的评分由你提交，不能自行复核（禁止自审），请由 HR 复核"
                if (assessment.training_scorer_id == user.id or assessment.manager_id == user.id)
                else "需要 HR 或培训部复核权限"
            ),
        )
    if assessment.status != ASSESS_HR_REVIEW_PENDING:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "当前不在 HR 复核"})
    from_status = assessment.status
    if approve:
        assessment.status = ASSESS_EMPLOYEE_CONFIRM_PENDING
        assessment.current_handler_type = "employee"
        assessment.current_handler_id = assessment.user_id
        if _is_onboarding(assessment):
            _ensure_confirmations(assessment)
    else:
        assessment.status = ASSESS_MANAGER_PENDING
        assessment.current_handler_type = "manager"
        assessment.current_handler_id = assessment.manager_id
    _bump(assessment)
    _log(db, assessment, action="hr_review", actor_id=user.id, from_status=from_status, to_status=assessment.status, note=note)
    db.commit()
    return detail_payload(db, assessment, user)


def result_confirm(db: Session, assessment_id: int, user: User, *, revision: int) -> dict:
    assessment = _assessment(db, assessment_id)
    _check_revision(assessment, revision)
    if assessment.user_id != user.id:
        raise HTTPException(status_code=403, detail="只能确认本人结果")
    if assessment.status == ASSESS_APPEAL_PENDING:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "申诉未处理不能确认"})
    if assessment.status != ASSESS_EMPLOYEE_CONFIRM_PENDING:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "当前状态不可确认"})
    if _is_onboarding(assessment):
        raise HTTPException(
            status_code=422,
            detail="入职考核无需员工确认，请由主管、培训部、HR 完成三方确认",
        )
    from_status = assessment.status
    assessment.status = ASSESS_COMPLETED
    assessment.completed_at = datetime.now(timezone.utc)
    assessment.confirmed_revision = assessment.revision
    assessment.current_handler_type = None
    assessment.current_handler_id = None
    _bump(assessment)
    _log(db, assessment, action="result_confirm", actor_id=user.id, from_status=from_status, to_status=assessment.status)
    db.commit()
    return detail_payload(db, assessment, user)


def party_confirm(
    db: Session,
    assessment_id: int,
    user: User,
    *,
    revision: int,
    party: str,
) -> dict:
    """入职考核三方确认：主管 / 培训部 / HR（无需员工确认）。"""
    assessment = _assessment(db, assessment_id)
    _check_revision(assessment, revision)
    if not _is_onboarding(assessment):
        raise HTTPException(status_code=422, detail="仅入职考核支持三方确认")
    if assessment.status != ASSESS_EMPLOYEE_CONFIRM_PENDING:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "当前状态不可确认"})
    party = (party or "").strip().lower()
    if party not in ONBOARD_CONFIRM_PARTIES:
        raise HTTPException(status_code=422, detail="party 必须是 manager / training / hr")
    if party == "manager":
        if assessment.manager_id != user.id and not _is_hr(user):
            raise HTTPException(status_code=403, detail="仅直属主管可确认")
    elif party == "training":
        if not _can_training_score(assessment, user):
            raise HTTPException(status_code=403, detail="需要培训部（或 HR）权限")
    elif not _is_hr(user):
        raise HTTPException(status_code=403, detail="需要 HR 权限")
    _record_party_confirm(assessment, party=party, user=user)
    if not _try_complete_onboarding(db, assessment, user, action=f"party_confirm_{party}"):
        from_status = assessment.status
        _bump(assessment)
        _log(
            db,
            assessment,
            action=f"party_confirm_{party}",
            actor_id=user.id,
            from_status=from_status,
            to_status=assessment.status,
            note="三方确认进行中",
        )
    db.commit()
    return detail_payload(db, assessment, user)


def _is_onboarding(assessment: PerformanceAssessment) -> bool:
    return (assessment.assessment_kind or "") == "onboarding"


def _item_evaluator(item: PerformanceAssessmentItem) -> str:
    return (item.evaluator or "manager").strip() or "manager"


def _items_by_evaluator(db: Session, assessment_id: int, evaluator: str) -> list[PerformanceAssessmentItem]:
    rows = (
        db.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == assessment_id)
        .all()
    )
    return [i for i in rows if _item_evaluator(i) == evaluator]


def _has_training_items(db: Session, assessment_id: int) -> bool:
    return bool(_items_by_evaluator(db, assessment_id, "training"))


def _can_training_score(assessment: PerformanceAssessment, user: User) -> bool:
    """培训部评分人：仅入职考核，且需要 kpi:onboarding:manage（培训部负责人）或 HR/管理员。"""
    if not _is_onboarding(assessment):
        return False
    codes = collect_permission_codes(user)
    return "*" in codes or "kpi:onboarding:manage" in codes or _is_hr(user)


def _apply_item_scores(
    db: Session,
    assessment_id: int,
    scores: Optional[list[dict]],
    *,
    only_evaluator: Optional[str] = None,
) -> list[PerformanceAssessmentItem]:
    """写入评分。only_evaluator 为空时按历史行为写全部；否则只写属于该评分人的指标。

    返回本次未评分（仍为空）的指标，交调用方决定是否阻断提交。
    """
    scored_ids: set[int] = set()
    if scores:
        for s in scores:
            raw = s.get("score")
            if raw is None:
                continue
            if isinstance(raw, str) and not raw.strip():
                continue
            item = (
                db.query(PerformanceAssessmentItem)
                .filter(
                    PerformanceAssessmentItem.id == int(s["item_id"]),
                    PerformanceAssessmentItem.assessment_id == assessment_id,
                )
                .first()
            )
            if item is None:
                continue
            if only_evaluator is not None and _item_evaluator(item) != only_evaluator:
                continue
            try:
                score = Decimal(str(raw))
            except Exception:
                continue
            item.leader_score = score
            if s.get("comment") is not None:
                item.leader_comment = s.get("comment")
            item.awarded_points = score
            item.final_score = score
            scored_ids.add(item.id)
    if only_evaluator is None:
        return []
    return [i for i in _items_by_evaluator(db, assessment_id, only_evaluator) if i.id not in scored_ids]


def _recalc_assessment_total(db: Session, assessment: PerformanceAssessment) -> Decimal:
    total = sum(
        (i.awarded_points or Decimal("0"))
        for i in db.query(PerformanceAssessmentItem).filter_by(assessment_id=assessment.id).all()
    )
    tpl_snap = _loads_obj(assessment.template_snapshot_json)
    defn = _loads_obj(tpl_snap.get("definition_json") if isinstance(tpl_snap.get("definition_json"), str) else None)
    if not defn and isinstance(tpl_snap.get("definition_json"), dict):
        defn = tpl_snap["definition_json"]
    # 讲师：起始分 + 事件加减分合计
    if (tpl_snap.get("scoring_mode") or defn.get("scoring_mode")) == "event_ledger":
        base = Decimal(
            str(
                tpl_snap.get("nominal_total")
                or defn.get("nominal_total")
                or defn.get("base_points")
                or 100
            )
        )
        total = base + total
    assessment.total_points = total
    assessment.manager_score = int(total)
    assessment.final_score = int(total)
    return total


def create_appeal(db: Session, assessment_id: int, user: User, *, revision: int, reason: str, request_score: int) -> dict:
    assessment = _assessment(db, assessment_id)
    _check_revision(assessment, revision)
    if assessment.user_id != user.id:
        raise HTTPException(status_code=403, detail="只能申诉本人考核")
    if assessment.status != ASSESS_EMPLOYEE_CONFIRM_PENDING:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "当前状态不可申诉"})
    if assessment.status == ASSESS_COMPLETED:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "已完成不可申诉"})
    from_status = assessment.status
    appeal = PerformanceAppeal(
        assessment_id=assessment.id,
        reason=reason,
        request_score=request_score,
        status=APPEAL_PENDING,
    )
    db.add(appeal)
    assessment.status = ASSESS_APPEAL_PENDING
    assessment.current_handler_type = "hr"
    assessment.current_handler_id = None
    _bump(assessment)
    _log(db, assessment, action="appeal", actor_id=user.id, from_status=from_status, to_status=assessment.status, note=reason)
    db.commit()
    return detail_payload(db, assessment, user)


def resolve_appeal(
    db: Session,
    assessment_id: int,
    user: User,
    *,
    revision: int,
    approve: bool,
    resolution: str,
    final_score: Optional[int] = None,
    scores: Optional[list[dict]] = None,
    return_to_manager: bool = False,
) -> dict:
    assessment = _assessment(db, assessment_id)
    _check_revision(assessment, revision)
    if not (
        _is_hr(user)
        or (_is_onboarding(assessment) and _can_training_score(assessment, user))
    ):
        raise HTTPException(status_code=403, detail="需要 HR 或培训部权限")
    if assessment.status != ASSESS_APPEAL_PENDING:
        raise HTTPException(status_code=409, detail={"code": "KPI_ACTION_NOT_ALLOWED", "message": "当前无待处理申诉"})
    appeal = (
        db.query(PerformanceAppeal)
        .filter(PerformanceAppeal.assessment_id == assessment_id, PerformanceAppeal.status == APPEAL_PENDING)
        .order_by(PerformanceAppeal.id.desc())
        .first()
    )
    decided_approve = bool(approve or scores or return_to_manager or final_score is not None)
    if appeal:
        appeal.status = "approved" if decided_approve else "rejected"
        appeal.resolution = resolution
        appeal.resolved_by = user.id
        appeal.resolved_at = datetime.now(timezone.utc)
    if not return_to_manager:
        if scores:
            _apply_item_scores(db, assessment_id, scores)
            _recalc_assessment_total(db, assessment)
        elif decided_approve and final_score is not None:
            assessment.final_score = final_score
            assessment.total_points = Decimal(str(final_score))
            assessment.manager_score = final_score
    from_status = assessment.status
    if return_to_manager:
        assessment.status = ASSESS_MANAGER_PENDING
        assessment.current_handler_type = "manager"
        assessment.current_handler_id = assessment.manager_id
    else:
        assessment.status = ASSESS_EMPLOYEE_CONFIRM_PENDING
        assessment.current_handler_type = "employee"
        assessment.current_handler_id = assessment.user_id
        if _is_onboarding(assessment):
            # 申诉改分后需重新三方确认
            wf = _ensure_confirmations(assessment)
            wf["confirmations"] = {"manager": None, "training": None, "hr": None}
            _save_workflow(assessment, wf)
    _bump(assessment)
    _log(db, assessment, action="resolve_appeal", actor_id=user.id, from_status=from_status, to_status=assessment.status, note=resolution)
    db.commit()
    return detail_payload(db, assessment, user)
