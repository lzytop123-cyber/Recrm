"""旧版绩效周期流程：重置、校准、锁定、工资批次生成/复核/发布。"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.performance import (
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
from app.services.performance import (
    _now,
    _seed_roster,
    can_manage_performance,
    enrich_cycle,
    ensure_cycle,
)


def reset_cycle(db: Session, user: User, period_label: str | None = None) -> PerformanceCycle:
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


def start_calibration(db: Session, user: User, period_label: str | None = None) -> PerformanceCycle:
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


def lock_cycle(db: Session, user: User, period_label: str | None = None) -> PerformanceCycle:
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


def generate_payroll(db: Session, user: User, period_label: str | None = None) -> PerformanceCycle:
    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="无权生成工资批次")
    cycle = ensure_cycle(db, period_label)
    if not cycle.locked:
        raise HTTPException(status_code=400, detail="请先锁定绩效")
    ym = cycle.period_label.replace("-", "")
    cycle.payroll_batch_no = f"GZ-{ym}"
    cycle.payroll_created = True
    cycle.status = CYCLE_STATUS_PAYROLL
    db.commit()
    db.refresh(cycle)
    return enrich_cycle(db, cycle)


def review_payroll(db: Session, user: User, period_label: str | None = None) -> PerformanceCycle:
    if not can_manage_performance(user):
        raise HTTPException(status_code=403, detail="无权复核")
    cycle = ensure_cycle(db, period_label)
    if not cycle.payroll_created:
        raise HTTPException(status_code=400, detail="请先生成工资批次")
    cycle.payroll_reviewed = True
    db.commit()
    db.refresh(cycle)
    return enrich_cycle(db, cycle)


def publish_payroll(db: Session, user: User, period_label: str | None = None) -> PerformanceCycle:
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
