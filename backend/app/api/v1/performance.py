"""绩效 API。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.performance import (
    AppealCreate,
    AppealOut,
    AppealResolveRequest,
    AssessmentOut,
    ManagerRateRequest,
    PerformanceCycleOut,
    PerformanceWorkbenchOut,
    SelfRateRequest,
)
from app.services import performance as perf_service

router = APIRouter(prefix="/performance", tags=["目标绩效"])


@router.get("/workbench", response_model=PerformanceWorkbenchOut, summary="绩效工作台数据")
def workbench(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: str = Query("2026-07"),
) -> PerformanceWorkbenchOut:
    data = perf_service.get_workbench(db, current_user, period_label)
    return PerformanceWorkbenchOut(
        cycle=PerformanceCycleOut.model_validate(data["cycle"]),
        assessments=[AssessmentOut.model_validate(x) for x in data["assessments"]],
        appeals=[AppealOut.model_validate(x) for x in data["appeals"]],
        grade_distribution=data["grade_distribution"],
    )


@router.post("/assessments/{assessment_id}/self-rate", response_model=AssessmentOut)
def self_rate(
    assessment_id: int,
    payload: SelfRateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> AssessmentOut:
    return AssessmentOut.model_validate(
        perf_service.rate_self(db, current_user, assessment_id, payload)
    )


@router.post("/assessments/{assessment_id}/manager-rate", response_model=AssessmentOut)
def manager_rate(
    assessment_id: int,
    payload: ManagerRateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> AssessmentOut:
    return AssessmentOut.model_validate(
        perf_service.rate_manager(db, current_user, assessment_id, payload)
    )


@router.post("/assessments/{assessment_id}/appeals", response_model=AppealOut)
def create_appeal(
    assessment_id: int,
    payload: AppealCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> AppealOut:
    return AppealOut.model_validate(
        perf_service.create_appeal(db, current_user, assessment_id, payload)
    )


@router.post("/appeals/{appeal_id}/resolve", response_model=AppealOut)
def resolve_appeal(
    appeal_id: int,
    payload: AppealResolveRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> AppealOut:
    return AppealOut.model_validate(
        perf_service.resolve_appeal(db, current_user, appeal_id, payload)
    )


@router.post("/cycles/reset", response_model=PerformanceCycleOut, summary="重置考核周期（可重新打分）")
def reset_cycle(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: str = Query("2026-07"),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.reset_cycle(db, current_user, period_label)
    )


@router.post("/cycles/calibrate", response_model=PerformanceCycleOut)
def calibrate(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: str = Query("2026-07"),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.start_calibration(db, current_user, period_label)
    )


@router.post("/cycles/lock", response_model=PerformanceCycleOut)
def lock_cycle(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: str = Query("2026-07"),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.lock_cycle(db, current_user, period_label)
    )


@router.post("/cycles/payroll/generate", response_model=PerformanceCycleOut)
def generate_payroll(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: str = Query("2026-07"),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.generate_payroll(db, current_user, period_label)
    )


@router.post("/cycles/payroll/review", response_model=PerformanceCycleOut)
def review_payroll(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: str = Query("2026-07"),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.review_payroll(db, current_user, period_label)
    )


@router.post("/cycles/payroll/publish", response_model=PerformanceCycleOut)
def publish_payroll(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: str = Query("2026-07"),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.publish_payroll(db, current_user, period_label)
    )
