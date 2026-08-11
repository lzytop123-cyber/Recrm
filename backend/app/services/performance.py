"""
绩效业务：周期、主管评价、校准、申诉、锁定、工资批次。
OKR 进度仅作为主管评价的建议分，不自动完成考核。
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

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
    PerformanceCycle,
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


def _dept_name(db: Session, dept_id: Optional[int]) -> Optional[str]:
    if not dept_id:
        return None
    d = db.query(Department).filter(Department.id == dept_id).first()
    return d.name if d else None


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
) -> PerformanceAssessment:
    row.user_name = _user_name(db, row.user_id)  # type: ignore[attr-defined]
    row.department_name = _dept_name(db, row.department_id)  # type: ignore[attr-defined]
    if month_period:
        score, count, okr_period = suggested_okr_for_user(db, row.user_id, month_period)
        row.suggested_okr_score = score  # type: ignore[attr-defined]
        row.suggested_okr_count = count  # type: ignore[attr-defined]
        row.suggested_okr_period = okr_period  # type: ignore[attr-defined]
    else:
        row.suggested_okr_score = None  # type: ignore[attr-defined]
        row.suggested_okr_count = 0  # type: ignore[attr-defined]
        row.suggested_okr_period = None  # type: ignore[attr-defined]
    return row


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
            enrich_assessment(db, x, month_period=period_label) for x in assessments
        ],
        "appeals": [enrich_appeal(db, x) for x in appeals],
        "grade_distribution": grade_distribution,
    }


def rate_manager(
    db: Session, user: User, assessment_id: int, payload: ManagerRateRequest
) -> PerformanceAssessment:
    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="仅主管/管理者可提交评价")
    row = db.query(PerformanceAssessment).filter(PerformanceAssessment.id == assessment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="考核记录不存在")
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == row.cycle_id).first()
    if not cycle or cycle.locked:
        raise HTTPException(status_code=400, detail="周期已锁定，不可评价")
    if row.status != ASSESS_PENDING_MANAGER:
        raise HTTPException(status_code=400, detail="当前状态不可提交主管评价")
    if row.user_id == user.id:
        raise HTTPException(status_code=403, detail="不能评价本人")

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
    db.commit()
    db.refresh(cycle)
    return enrich_cycle(db, cycle)
