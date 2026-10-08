"""
绩效业务：周期、主管评价、校准、申诉、锁定、工资批次。
OKR 进度仅作为主管评价的建议分，不自动完成考核。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.okr import (
    OKR_LEVEL_PERSONAL,
    OKR_STATUS_TERMINATED,
    Okr,
)
from app.models.performance import (
    APPEAL_APPROVED,
    APPEAL_PENDING,
    APPEAL_REJECTED,
    ASSESS_APPEALING,
    ASSESS_COMPLETED,
    ASSESS_PENDING_CALIBRATION,
    ASSESS_PENDING_MANAGER,
    ASSESS_PENDING_SELF,
    CYCLE_STATUS_ASSESSING,
    CYCLE_STATUS_CALIBRATING,
    CYCLE_STATUS_LOCKED,
    CYCLE_STATUS_PAYROLL,
    CYCLE_STATUS_PUBLISHED,
    PerformanceAppeal,
    PerformanceAssessment,
    PerformanceAssessmentItem,
    PerformanceCycle,
    PerformanceTemplate,
    PerformanceTemplateItem,
)
from app.models.user import User
from app.schemas.performance import (
    AppealCreate,
    AppealResolveRequest,
    ManagerRateRequest,
    SelfRateRequest,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    return (u.real_name or u.username) if u else None


def _user_job_title(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    return (u.job_title or None) if u else None


def _dept_name(db: Session, dept_id: Optional[int]) -> Optional[str]:
    if not dept_id:
        return None
    d = db.query(Department).filter(Department.id == dept_id).first()
    return d.name if d else None


def _person_snapshot(row: PerformanceAssessment) -> dict:
    raw = getattr(row, "person_snapshot_json", None) or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _match_label(adjustment_type: Optional[str]) -> Optional[str]:
    if adjustment_type == "manual_include":
        return "人工纳入"
    if adjustment_type == "manual_note":
        return "系统匹配"
    if adjustment_type == "automatic":
        return "自动匹配"
    return None


def _grade_and_coeff(score: int) -> tuple[str, Decimal]:
    if score >= 90:
        return "A+", Decimal("1.20")
    if score >= 85:
        return "A", Decimal("1.10")
    if score >= 70:
        return "B", Decimal("1.00")
    if score >= 60:
        return "C", Decimal("0.85")
    return "D", Decimal("0.70")


def _bonus(coeff: Decimal) -> Decimal:
    return (Decimal("5000") * coeff).quantize(Decimal("0.01"))


GRADE_COEFF = {
    "A+": Decimal("1.20"),
    "A": Decimal("1.10"),
    "B": Decimal("1.00"),
    "C": Decimal("0.85"),
    "D": Decimal("0.70"),
}


def resolve_grade(score) -> str:
    s = Decimal(str(score or 0))
    if s >= 95:
        return "A+"
    if s >= 85:
        return "A"
    if s >= 75:
        return "B"
    if s >= 65:
        return "C"
    return "D"


def _item_effective_score(item) -> Decimal:
    for attr in ("final_score", "leader_score", "system_score", "self_score"):
        v = getattr(item, attr, None)
        if v is not None:
            return Decimal(str(v))
    return Decimal("0")


def compute_weighted_score(items) -> Decimal:
    """加权平均，权重合计为分母。空列表返回 0。"""
    rows = list(items or [])
    total_w = sum(Decimal(str(getattr(i, "weight", 0) or 0)) for i in rows)
    if total_w <= 0:
        return Decimal("0.00")
    acc = sum(_item_effective_score(i) * Decimal(str(i.weight)) for i in rows)
    return (acc / total_w).quantize(Decimal("0.01"))


def _as_int_score(val: Decimal) -> int:
    return int(val.quantize(Decimal("1")))


def _fill_score_caches(assessment: PerformanceAssessment, items: list[PerformanceAssessmentItem]) -> None:
    if getattr(assessment, "engine_version", None) not in (None, "", "legacy"):
        return
    okr = [i for i in items if i.data_source == "okr"]
    kpi = [i for i in items if i.data_source == "system"]
    behavior = [i for i in items if i.data_source == "manual"]
    self_items = [i for i in items if i.data_source in ("self_manual", "manual")]
    if okr:
        assessment.okr_score = _as_int_score(compute_weighted_score(okr))
    if kpi:
        assessment.kpi_score = _as_int_score(compute_weighted_score(kpi))
    if behavior:
        assessment.behavior_score = _as_int_score(compute_weighted_score(behavior))
    if self_items and any(i.self_score is not None for i in self_items):
        assessment.self_score = _as_int_score(compute_weighted_score(self_items))
    if any(i.leader_score is not None or i.system_score is not None for i in items):
        total = compute_weighted_score(items)
        assessment.manager_score = _as_int_score(total)
        assessment.grade = resolve_grade(total)
        assessment.coefficient = GRADE_COEFF[assessment.grade]
        assessment.bonus_amount = _bonus(assessment.coefficient)


def _freeze_actuals(db, assessment: PerformanceAssessment, items: list[PerformanceAssessmentItem]) -> None:
    from app.services.performance_data_source import resolve_actual

    for item in items:
        actual, _score = resolve_actual(item, assessment, db)
        item.actual_value = actual
        item.system_score = None


def _archive_item_finals(items: list[PerformanceAssessmentItem]) -> None:
    for item in items:
        if item.leader_score is not None:
            item.final_score = item.leader_score
        elif item.system_score is not None:
            item.final_score = item.system_score
        elif item.self_score is not None:
            item.final_score = item.self_score


def status_from_instance(instance) -> str:
    from app.models.approval_flow import INSTANCE_APPROVED, INSTANCE_REJECTED

    if instance.status == INSTANCE_APPROVED:
        return ASSESS_COMPLETED
    if instance.status == INSTANCE_REJECTED:
        return ASSESS_PENDING_SELF
    seq = instance.current_seq or 1
    if seq <= 1:
        return ASSESS_PENDING_SELF
    if seq in (2, 3):
        return ASSESS_PENDING_MANAGER
    return ASSESS_PENDING_CALIBRATION


def _sync_from_instance(assessment: PerformanceAssessment, instance) -> None:
    assessment.status = status_from_instance(instance)


def _manager_chain(db, user: User) -> tuple[Optional[int], Optional[int]]:
    mid = user.manager_id
    skip = None
    if mid:
        mgr = db.query(User).filter(User.id == mid).first()
        skip = mgr.manager_id if mgr else None
    return mid, skip or mid


def _assessment_items(db, assessment_id: int) -> list[PerformanceAssessmentItem]:
    from app.services import performance_materials as mats

    items = (
        db.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == assessment_id)
        .order_by(PerformanceAssessmentItem.order_no.asc(), PerformanceAssessmentItem.id.asc())
        .all()
    )
    return mats.enrich_assessment_items(db, assessment_id, items)


def _apply_item_rates(items: list[PerformanceAssessmentItem], rates, *, leader: bool) -> None:
    by_id = {i.id: i for i in items}
    for raw in rates or []:
        row = by_id.get(raw.item_id)
        if not row:
            continue
        if leader:
            if raw.leader_score is not None:
                row.leader_score = raw.leader_score
            if raw.leader_comment is not None:
                row.leader_comment = raw.leader_comment
        else:
            if raw.self_score is not None:
                row.self_score = raw.self_score
            if raw.self_comment is not None:
                row.self_comment = raw.self_comment


def _advance_assessment_flow(db, user: User, assessment: PerformanceAssessment, comment: str) -> None:
    from app.models.approval_flow import ApprovalInstance
    from app.services import approval_flow

    if not assessment.approval_instance_id:
        return
    inst = db.query(ApprovalInstance).filter(ApprovalInstance.id == assessment.approval_instance_id).first()
    if not inst:
        return
    approval_flow.act(db, user, inst, approve=True, comment=comment, commit=False)
    db.refresh(inst)
    _sync_from_instance(assessment, inst)
    if assessment.status == ASSESS_COMPLETED:
        items = _assessment_items(db, assessment.id)
        _freeze_actuals(db, assessment, items)
        _archive_item_finals(items)
        _fill_score_caches(assessment, items)
        assessment.final_score = _as_int_score(compute_weighted_score(items))
        assessment.grade = resolve_grade(assessment.final_score)
        assessment.coefficient = GRADE_COEFF[assessment.grade]
        assessment.bonus_amount = _bonus(assessment.coefficient)


def create_cycle(
    db,
    name: str,
    template_id: int,
    cycle_type: str = "monthly",
    dates=None,
    scope: Optional[dict[str, Any]] = None,
) -> PerformanceCycle:
    _ = dates  # 起止日由 period_label + cycle_type 推导，不另存字段
    if db.query(PerformanceCycle).filter(PerformanceCycle.period_label == name).first():
        raise HTTPException(status_code=409, detail=f"周期已存在：{name}")
    tpl = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="绩效模板不存在")
    cycle = PerformanceCycle(
        period_label=name,
        rule_version="V2026.07",
        status=CYCLE_STATUS_ASSESSING,
        cycle_type=cycle_type or tpl.cycle_type or "monthly",
        default_template_id=template_id,
        remark=None if not scope else str(scope),
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    cycle._scope = scope  # type: ignore[attr-defined]
    return enrich_cycle(db, cycle)


def _scope_users(db, scope: Optional[dict[str, Any]]) -> list[User]:
    q = db.query(User).filter(User.is_active.is_(True))
    if scope:
        ids = scope.get("user_ids")
        dept_id = scope.get("department_id")
        if ids:
            q = q.filter(User.id.in_(list(ids)))
        elif dept_id:
            q = q.filter(User.department_id == dept_id)
    return q.order_by(User.id.asc()).all()


def generate_assessments(
    db,
    cycle_id: int,
    scope: Optional[dict[str, Any]] = None,
) -> list[PerformanceAssessment]:
    from app.services.approval_flow import start_instance

    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="考核周期不存在")
    if not cycle.default_template_id:
        raise HTTPException(status_code=400, detail="周期未绑定指标模板")
    tpl_items = (
        db.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == cycle.default_template_id)
        .order_by(PerformanceTemplateItem.order_no.asc(), PerformanceTemplateItem.id.asc())
        .all()
    )
    if not tpl_items:
        raise HTTPException(status_code=400, detail="模板没有指标，无法生成考核单")

    existing = {
        (uid, key or "monthly_primary")
        for uid, key in db.query(PerformanceAssessment.user_id, PerformanceAssessment.instance_key)
        .filter(PerformanceAssessment.cycle_id == cycle.id)
        .all()
    }
    created: list[PerformanceAssessment] = []
    for u in _scope_users(db, scope):
        if (u.id, "monthly_primary") in existing:
            continue
        row = PerformanceAssessment(
            cycle_id=cycle.id,
            user_id=u.id,
            department_id=u.department_id,
            template_id=cycle.default_template_id,
            evidence_status="待补充",
            status=ASSESS_PENDING_SELF,
            instance_key="monthly_primary",
            assessment_kind="monthly",
            engine_version="legacy",
        )
        db.add(row)
        db.flush()
        items: list[PerformanceAssessmentItem] = []
        for it in tpl_items:
            item = PerformanceAssessmentItem(
                assessment_id=row.id,
                template_item_id=it.id,
                order_no=it.order_no,
                name=it.name,
                weight=it.weight,
                data_source=it.data_source,
                source_ref=it.source_ref,
                target_value=it.target_value,
                score_rule=it.score_rule,
            )
            db.add(item)
            items.append(item)
        db.flush()
        _freeze_actuals(db, row, items)
        _fill_score_caches(row, items)
        mid, skip = _manager_chain(db, u)
        inst = start_instance(
            db,
            biz_type="kpi_review",
            biz_id=row.id,
            initiator=u,
            title=f"{cycle.period_label} 绩效考核 · {u.real_name or u.username}",
            department_id=u.department_id,
            assignees={"user_id": u.id, "manager_id": mid, "skip_manager_id": skip},
            commit=False,
        )
        row.approval_instance_id = inst.id
        _sync_from_instance(row, inst)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return created


def on_kpi_review_result(db, instance, *, approved: bool, withdrawn: bool = False) -> None:
    row = (
        db.query(PerformanceAssessment)
        .filter(PerformanceAssessment.approval_instance_id == instance.id)
        .first()
    )
    if not row:
        return
    _sync_from_instance(row, instance)
    if approved and not withdrawn:
        items = _assessment_items(db, row.id)
        _freeze_actuals(db, row, items)
        _archive_item_finals(items)
        _fill_score_caches(row, items)
        row.final_score = _as_int_score(compute_weighted_score(items))
        row.grade = resolve_grade(row.final_score)
        row.coefficient = GRADE_COEFF[row.grade]
        row.bonus_amount = _bonus(row.coefficient)


def _weighted_score(okr: int, kpi: int, behavior: int) -> int:
    return int(round(okr * 0.5 + kpi * 0.3 + behavior * 0.2))


def month_to_okr_period(period_label: str) -> str:
    """考核月 2026-07 → 所属季度 2026-Q3。"""
    try:
        year_s, month_s = period_label.split("-", 1)
        year, month = int(year_s), int(month_s)
        quarter = (month - 1) // 3 + 1
        return f"{year}-Q{quarter}"
    except (ValueError, TypeError):
        return period_label


def suggested_okr_for_user(db: Session, user_id: int, month_period: str) -> tuple[Optional[int], int, str]:
    okr_period = month_to_okr_period(month_period)
    items = (
        db.query(Okr)
        .filter(
            Okr.owner_id == user_id,
            Okr.level == OKR_LEVEL_PERSONAL,
            Okr.period_label == okr_period,
            Okr.status != OKR_STATUS_TERMINATED,
        )
        .all()
    )
    if not items:
        return None, 0, okr_period
    avg = int(round(sum((x.progress or 0) for x in items) / len(items)))
    return max(0, min(100, avg)), len(items), okr_period


def can_manage_performance(user: User) -> bool:
    from app.core.rbac import user_can

    if user_can(user, "org:manage"):
        return True
    codes = {r.code for r in user.roles}
    return bool(codes & {"executive", "middle_manager", "hr_supervisor"})


def enrich_assessment(
    db: Session,
    row: PerformanceAssessment,
    month_period: Optional[str] = None,
    *,
    with_items: bool = False,
) -> PerformanceAssessment:
    snap = _person_snapshot(row)
    row.user_name = snap.get("name") or _user_name(db, row.user_id)  # type: ignore[attr-defined]
    row.department_name = snap.get("department_name") or _dept_name(db, row.department_id)  # type: ignore[attr-defined]
    row.job_title = snap.get("job_title") or _user_job_title(db, row.user_id)  # type: ignore[attr-defined]
    row.adjustment_type = snap.get("adjustment_type")  # type: ignore[attr-defined]
    row.adjustment_reason = snap.get("adjustment_reason")  # type: ignore[attr-defined]
    row.match_label = _match_label(snap.get("adjustment_type"))  # type: ignore[attr-defined]
    if month_period:
        score, count, okr_period = suggested_okr_for_user(db, row.user_id, month_period)
        row.suggested_okr_score = score  # type: ignore[attr-defined]
        row.suggested_okr_count = count  # type: ignore[attr-defined]
        row.suggested_okr_period = okr_period  # type: ignore[attr-defined]
        row.period_label = month_period  # type: ignore[attr-defined]
    else:
        cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == row.cycle_id).first()
        row.period_label = cycle.period_label if cycle else None  # type: ignore[attr-defined]
        row.suggested_okr_score = None  # type: ignore[attr-defined]
        row.suggested_okr_count = 0  # type: ignore[attr-defined]
        row.suggested_okr_period = None  # type: ignore[attr-defined]
    if with_items:
        row.items = _assessment_items(db, row.id)  # type: ignore[attr-defined]
    else:
        row.items = []  # type: ignore[attr-defined]
    return row


def _grade_distribution(assessments: list[PerformanceAssessment]) -> dict:
    dist = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0}
    scored = [x for x in assessments if x.final_score is not None]
    for x in scored:
        g = x.grade or "B"
        if g in dist:
            dist[g] += 1
        elif g.startswith("A"):
            dist["A"] += 1
        else:
            dist["B"] += 1
    total = max(1, len(scored))
    return {
        "A+_A": round((dist["A+"] + dist["A"]) * 100 / total) if scored else 0,
        "B": round(dist["B"] * 100 / total) if scored else 0,
        "C_D": round((dist["C"] + dist["D"]) * 100 / total) if scored else 0,
        "counts": dist,
    }


def get_assessment_detail(db: Session, user: User, assessment_id: int) -> PerformanceAssessment:
    from app.models.approval_flow import ApprovalInstance
    from app.services.approval_flow import instance_timeline

    row = db.query(PerformanceAssessment).filter(PerformanceAssessment.id == assessment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="考核记录不存在")
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == row.cycle_id).first()
    period = cycle.period_label if cycle else None
    enrich_assessment(db, row, month_period=period, with_items=True)
    timeline = []
    if row.approval_instance_id:
        inst = (
            db.query(ApprovalInstance)
            .filter(ApprovalInstance.id == row.approval_instance_id)
            .first()
        )
        if inst:
            timeline = instance_timeline(inst, db)
    row.timeline = timeline  # type: ignore[attr-defined]
    _ = user
    return row


def list_my_assessments(db: Session, user: User) -> dict:
    rows = (
        db.query(PerformanceAssessment)
        .filter(PerformanceAssessment.user_id == user.id)
        .order_by(PerformanceAssessment.id.desc())
        .all()
    )
    cycle_ids = {r.cycle_id for r in rows}
    cycles = {
        c.id: c
        for c in db.query(PerformanceCycle).filter(PerformanceCycle.id.in_(cycle_ids or [-1])).all()
    }
    assessments = []
    trend = []
    for r in rows:
        period = cycles[r.cycle_id].period_label if r.cycle_id in cycles else None
        enrich_assessment(db, r, month_period=period, with_items=True)
        assessments.append(r)
        trend.append(
            {
                "assessment_id": r.id,
                "period_label": period,
                "final_score": r.final_score,
                "grade": r.grade,
                "status": r.status,
            }
        )
    trend.reverse()
    return {"assessments": assessments, "trend": trend}


def _direct_report_ids(db: Session, manager_id: int) -> list[int]:
    return [
        uid
        for (uid,) in db.query(User.id)
        .filter(User.manager_id == manager_id, User.is_active.is_(True))
        .all()
    ]


def _dept_report_ids(db: Session, root_manager_id: int) -> list[int]:
    """递归下属：manager_id 链下所有人。"""
    found: list[int] = []
    queue = list(_direct_report_ids(db, root_manager_id))
    seen = set(queue)
    while queue:
        uid = queue.pop(0)
        found.append(uid)
        for child in _direct_report_ids(db, uid):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return found


def list_team_assessments(
    db: Session,
    user: User,
    *,
    scope: str = "direct",
    period_label: Optional[str] = None,
) -> list[PerformanceAssessment]:
    ids = _direct_report_ids(db, user.id) if scope == "direct" else _dept_report_ids(db, user.id)
    if not ids:
        return []
    q = db.query(PerformanceAssessment).filter(PerformanceAssessment.user_id.in_(ids))
    if period_label:
        cycle = (
            db.query(PerformanceCycle)
            .filter(PerformanceCycle.period_label == period_label)
            .first()
        )
        if not cycle:
            return []
        q = q.filter(PerformanceAssessment.cycle_id == cycle.id)
    rows = q.order_by(PerformanceAssessment.id.desc()).all()
    cycle_map = {
        c.id: c
        for c in db.query(PerformanceCycle)
        .filter(PerformanceCycle.id.in_({r.cycle_id for r in rows} or [-1]))
        .all()
    }
    return [
        enrich_assessment(
            db,
            r,
            month_period=cycle_map[r.cycle_id].period_label if r.cycle_id in cycle_map else None,
            with_items=True,
        )
        for r in rows
    ]


def list_cycles(db: Session, *, status: Optional[str] = None) -> list[PerformanceCycle]:
    q = db.query(PerformanceCycle).order_by(PerformanceCycle.id.desc())
    if status:
        q = q.filter(PerformanceCycle.status == status)
    return [enrich_cycle(db, c) for c in q.all()]


def get_cycle_detail(db: Session, cycle_id: int) -> dict:
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="考核周期不存在")
    assessments = (
        db.query(PerformanceAssessment)
        .filter(PerformanceAssessment.cycle_id == cycle.id)
        .order_by(PerformanceAssessment.id.asc())
        .all()
    )
    enriched = [
        enrich_assessment(db, x, month_period=cycle.period_label, with_items=True)
        for x in assessments
    ]
    return {
        "cycle": enrich_cycle(db, cycle),
        "assessments": enriched,
        "grade_distribution": _grade_distribution(assessments),
    }


def enrich_appeal(db: Session, row: PerformanceAppeal) -> PerformanceAppeal:
    a = db.query(PerformanceAssessment).filter(PerformanceAssessment.id == row.assessment_id).first()
    row.user_name = _user_name(db, a.user_id) if a else None  # type: ignore[attr-defined]
    row.department_name = _dept_name(db, a.department_id) if a else None  # type: ignore[attr-defined]
    row.current_score = a.final_score if a else None  # type: ignore[attr-defined]
    return row


def enrich_cycle(db: Session, cycle: PerformanceCycle) -> PerformanceCycle:
    assessments = (
        db.query(PerformanceAssessment).filter(PerformanceAssessment.cycle_id == cycle.id).all()
    )
    appeals = (
        db.query(PerformanceAppeal)
        .join(PerformanceAssessment, PerformanceAssessment.id == PerformanceAppeal.assessment_id)
        .filter(PerformanceAssessment.cycle_id == cycle.id)
        .all()
    )
    cycle.pending_self = sum(1 for x in assessments if x.status == ASSESS_PENDING_SELF)  # type: ignore
    cycle.pending_manager = sum(1 for x in assessments if x.status == ASSESS_PENDING_MANAGER)  # type: ignore
    cycle.pending_appeals = sum(1 for x in appeals if x.status == APPEAL_PENDING)  # type: ignore
    cycle.completed_count = sum(1 for x in assessments if x.status == ASSESS_COMPLETED)  # type: ignore
    cycle.total_assessments = len(assessments)  # type: ignore
    return cycle


def _seed_roster(db: Session, cycle: PerformanceCycle) -> None:
    users = db.query(User).filter(User.is_active.is_(True)).order_by(User.id.asc()).all()
    for u in users:
        db.add(
            PerformanceAssessment(
                cycle_id=cycle.id,
                user_id=u.id,
                department_id=u.department_id,
                evidence_status="待补充",
                status=ASSESS_PENDING_SELF,
            )
        )


def ensure_cycle(db: Session, period_label: str = "2026-07") -> PerformanceCycle:
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.period_label == period_label).first()
    if cycle:
        return enrich_cycle(db, cycle)

    cycle = PerformanceCycle(
        period_label=period_label,
        rule_version="V2026.07",
        status=CYCLE_STATUS_ASSESSING,
    )
    db.add(cycle)
    db.flush()
    _seed_roster(db, cycle)
    db.commit()
    db.refresh(cycle)
    return enrich_cycle(db, cycle)


def reset_cycle(db: Session, user: User, period_label: str = "2026-07") -> PerformanceCycle:
    """管理员重置周期：清空分数与申诉，回到待自评，可重新打分。"""
    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="仅管理者可重置考核周期")
    cycle = ensure_cycle(db, period_label)

    assessment_ids = [
        aid
        for (aid,) in db.query(PerformanceAssessment.id)
        .filter(PerformanceAssessment.cycle_id == cycle.id)
        .all()
    ]
    if assessment_ids:
        db.query(PerformanceAppeal).filter(
            PerformanceAppeal.assessment_id.in_(assessment_ids)
        ).delete(synchronize_session=False)

    db.query(PerformanceAssessment).filter(PerformanceAssessment.cycle_id == cycle.id).delete(
        synchronize_session=False
    )
    _seed_roster(db, cycle)

    cycle.calibration_started = False
    cycle.locked = False
    cycle.locked_at = None
    cycle.payroll_batch_no = None
    cycle.payroll_created = False
    cycle.payroll_reviewed = False
    cycle.payroll_published = False
    cycle.status = CYCLE_STATUS_ASSESSING
    cycle.remark = f"已于 {_now().isoformat()} 重置为待自评"
    db.commit()
    db.refresh(cycle)
    return enrich_cycle(db, cycle)


def get_workbench(db: Session, user: User, period_label: str = "2026-07") -> dict:
    _ = user
    cycle = ensure_cycle(db, period_label)
    assessments = (
        db.query(PerformanceAssessment)
        .filter(PerformanceAssessment.cycle_id == cycle.id)
        .order_by(PerformanceAssessment.id.asc())
        .all()
    )
    appeals = (
        db.query(PerformanceAppeal)
        .join(PerformanceAssessment, PerformanceAssessment.id == PerformanceAppeal.assessment_id)
        .filter(PerformanceAssessment.cycle_id == cycle.id)
        .order_by(PerformanceAppeal.id.asc())
        .all()
    )
    dist = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0}
    scored = [x for x in assessments if x.final_score is not None]
    for x in scored:
        g = x.grade or "B"
        if g in dist:
            dist[g] += 1
        elif g.startswith("A"):
            dist["A"] += 1
        else:
            dist["B"] += 1
    total = max(1, len(scored))
    grade_distribution = {
        "A+_A": round((dist["A+"] + dist["A"]) * 100 / total) if scored else 0,
        "B": round(dist["B"] * 100 / total) if scored else 0,
        "C_D": round((dist["C"] + dist["D"]) * 100 / total) if scored else 0,
    }
    return {
        "cycle": enrich_cycle(db, cycle),
        "assessments": [
            enrich_assessment(db, x, month_period=period_label, with_items=True) for x in assessments
        ],
        "appeals": [enrich_appeal(db, x) for x in appeals],
        "grade_distribution": grade_distribution,
    }


def rate_manager(
    db: Session, user: User, assessment_id: int, payload: ManagerRateRequest
) -> PerformanceAssessment:
    row = db.query(PerformanceAssessment).filter(PerformanceAssessment.id == assessment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="考核记录不存在")
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == row.cycle_id).first()
    if not cycle or cycle.locked:
        raise HTTPException(status_code=400, detail="周期已锁定，不可评价")
    if row.user_id == user.id:
        raise HTTPException(status_code=403, detail="不能评价本人")

    if row.template_id:
        items = _assessment_items(db, row.id)
        _apply_item_rates(items, payload.items, leader=True)
        if payload.comment:
            row.manager_comment = payload.comment.strip()
        _fill_score_caches(row, items)
        _advance_assessment_flow(db, user, row, payload.comment.strip())
        db.commit()
        db.refresh(row)
        return enrich_assessment(db, row, month_period=cycle.period_label)

    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="仅主管/管理者可提交评价")
    if row.status != ASSESS_PENDING_MANAGER:
        raise HTTPException(status_code=400, detail="当前状态不可提交主管评价")

    total = _weighted_score(payload.okr_score, payload.kpi_score, payload.behavior_score)
    row.okr_score = payload.okr_score
    row.kpi_score = payload.kpi_score
    row.behavior_score = payload.behavior_score
    row.manager_score = total
    row.final_score = total
    row.grade, row.coefficient = _grade_and_coeff(total)
    row.bonus_amount = _bonus(row.coefficient)
    row.manager_comment = payload.comment.strip()
    row.status = ASSESS_PENDING_CALIBRATION
    db.commit()
    db.refresh(row)
    period = cycle.period_label if cycle else None
    return enrich_assessment(db, row, month_period=period)


def rate_self(
    db: Session, user: User, assessment_id: int, payload: SelfRateRequest
) -> PerformanceAssessment:
    row = db.query(PerformanceAssessment).filter(PerformanceAssessment.id == assessment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="考核记录不存在")
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == row.cycle_id).first()
    if cycle and cycle.locked:
        raise HTTPException(status_code=400, detail="周期已锁定，不可自评")
    if row.user_id != user.id and not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="仅本人可自评")

    if row.template_id:
        items = _assessment_items(db, row.id)
        _apply_item_rates(items, payload.items, leader=False)
        row.self_score = payload.self_score
        _fill_score_caches(row, items)
        _advance_assessment_flow(db, user, row, "自评完成")
        db.commit()
        db.refresh(row)
        period = cycle.period_label if cycle else None
        return enrich_assessment(db, row, month_period=period)

    if row.status != ASSESS_PENDING_SELF:
        raise HTTPException(status_code=400, detail="当前状态不可自评")
    row.self_score = payload.self_score
    row.status = ASSESS_PENDING_MANAGER
    db.commit()
    db.refresh(row)
    period = cycle.period_label if cycle else None
    return enrich_assessment(db, row, month_period=period)


def create_appeal(
    db: Session, user: User, assessment_id: int, payload: AppealCreate
) -> PerformanceAppeal:
    row = db.query(PerformanceAssessment).filter(PerformanceAssessment.id == assessment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="考核记录不存在")
    if row.user_id != user.id and not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="仅本人可申诉")
    if row.final_score is None:
        raise HTTPException(status_code=400, detail="尚无综合分，不可申诉")
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == row.cycle_id).first()
    if cycle and cycle.locked:
        raise HTTPException(status_code=400, detail="已锁定不可申诉")

    appeal = PerformanceAppeal(
        assessment_id=row.id,
        reason=payload.reason.strip(),
        request_score=payload.request_score,
        status=APPEAL_PENDING,
    )
    row.status = ASSESS_APPEALING
    db.add(appeal)
    db.commit()
    db.refresh(appeal)
    return enrich_appeal(db, appeal)


def resolve_appeal(
    db: Session, user: User, appeal_id: int, payload: AppealResolveRequest
) -> PerformanceAppeal:
    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="仅综合管理/管理者可处理申诉")
    appeal = db.query(PerformanceAppeal).filter(PerformanceAppeal.id == appeal_id).first()
    if not appeal or appeal.status != APPEAL_PENDING:
        raise HTTPException(status_code=400, detail="申诉不存在或已处理")
    row = db.query(PerformanceAssessment).filter(PerformanceAssessment.id == appeal.assessment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="考核记录不存在")

    appeal.resolution = payload.resolution.strip()
    appeal.resolved_by = user.id
    appeal.resolved_at = _now()
    if payload.approve:
        appeal.status = APPEAL_APPROVED
        score = payload.final_score if payload.final_score is not None else appeal.request_score
        row.final_score = score
        row.manager_score = score
        row.grade, row.coefficient = _grade_and_coeff(score)
        row.bonus_amount = _bonus(row.coefficient)
    else:
        appeal.status = APPEAL_REJECTED
    row.status = ASSESS_COMPLETED
    db.commit()
    db.refresh(appeal)
    return enrich_appeal(db, appeal)


def start_calibration(db: Session, user: User, period_label: str = "2026-07") -> PerformanceCycle:
    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="无权发起校准")
    cycle = ensure_cycle(db, period_label)
    if cycle.locked:
        raise HTTPException(status_code=400, detail="已锁定")
    pending_self = (
        db.query(PerformanceAssessment)
        .filter(
            PerformanceAssessment.cycle_id == cycle.id,
            PerformanceAssessment.status == ASSESS_PENDING_SELF,
        )
        .count()
    )
    pending_mgr = (
        db.query(PerformanceAssessment)
        .filter(
            PerformanceAssessment.cycle_id == cycle.id,
            PerformanceAssessment.status == ASSESS_PENDING_MANAGER,
        )
        .count()
    )
    if pending_self or pending_mgr:
        raise HTTPException(
            status_code=400,
            detail=f"仍有 {pending_self} 项待自评、{pending_mgr} 项待主管评价，无法发起校准",
        )
    cycle.calibration_started = True
    cycle.status = CYCLE_STATUS_CALIBRATING
    db.commit()
    db.refresh(cycle)
    return enrich_cycle(db, cycle)


def lock_cycle(db: Session, user: User, period_label: str = "2026-07") -> PerformanceCycle:
    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="无权锁定")
    cycle = ensure_cycle(db, period_label)
    if not cycle.calibration_started:
        raise HTTPException(status_code=400, detail="请先发起校准")
    cycle = enrich_cycle(db, cycle)
    if getattr(cycle, "pending_manager", 0) or getattr(cycle, "pending_appeals", 0) or getattr(
        cycle, "pending_self", 0
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"仍有 {cycle.pending_self} 项自评、{cycle.pending_manager} 项主管评价、"
                f"{cycle.pending_appeals} 项申诉未完成"
            ),
        )
    db.query(PerformanceAssessment).filter(
        PerformanceAssessment.cycle_id == cycle.id,
        PerformanceAssessment.status == ASSESS_PENDING_CALIBRATION,
    ).update({PerformanceAssessment.status: ASSESS_COMPLETED}, synchronize_session=False)
    cycle.locked = True
    cycle.locked_at = _now()
    cycle.status = CYCLE_STATUS_LOCKED
    db.commit()
    db.refresh(cycle)
    return enrich_cycle(db, cycle)


def generate_payroll(db: Session, user: User, period_label: str = "2026-07") -> PerformanceCycle:
    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="无权生成工资批次")
    cycle = ensure_cycle(db, period_label)
    if not cycle.locked:
        raise HTTPException(status_code=400, detail="请先锁定绩效")
    ym = period_label.replace("-", "")
    cycle.payroll_batch_no = f"GZ-{ym}"
    cycle.payroll_created = True
    cycle.status = CYCLE_STATUS_PAYROLL
    db.commit()
    db.refresh(cycle)
    return enrich_cycle(db, cycle)


def review_payroll(db: Session, user: User, period_label: str = "2026-07") -> PerformanceCycle:
    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="无权复核")
    cycle = ensure_cycle(db, period_label)
    if not cycle.payroll_created:
        raise HTTPException(status_code=400, detail="请先生成工资批次")
    cycle.payroll_reviewed = True
    db.commit()
    db.refresh(cycle)
    return enrich_cycle(db, cycle)


def publish_payroll(db: Session, user: User, period_label: str = "2026-07") -> PerformanceCycle:
    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="无权发布")
    cycle = ensure_cycle(db, period_label)
    if not cycle.payroll_reviewed:
        raise HTTPException(status_code=400, detail="请先完成财务复核")
    cycle.payroll_published = True
    cycle.status = CYCLE_STATUS_PUBLISHED
    from app.services import hr as hr_service

    hr_service.generate_payslips_for_cycle(db, cycle)
    db.commit()
    db.refresh(cycle)
    return enrich_cycle(db, cycle)
