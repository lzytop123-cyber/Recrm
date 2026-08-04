"""工时 API。"""
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.timesheet import (
    TimesheetCreate,
    TimesheetListOut,
    TimesheetOut,
    TimesheetRejectRequest,
    TimesheetStatsOut,
    TimesheetUpdate,
)
from app.services import timesheet as timesheet_service

router = APIRouter(prefix="/timesheets", tags=["工时管理"])


@router.get("/stats", response_model=TimesheetStatsOut, summary="工时统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["timesheet:view"]))],
) -> TimesheetStatsOut:
    return TimesheetStatsOut(**timesheet_service.timesheet_stats(db, current_user))


@router.get("", response_model=TimesheetListOut, summary="工时列表")
def list_timesheets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["timesheet:view"]))],
    status: Optional[str] = None,
    work_type: Optional[str] = None,
    project_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    scope: Optional[str] = Query(None, description="mine/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> TimesheetListOut:
    total, items = timesheet_service.list_timesheets(
        db,
        current_user,
        status=status,
        work_type=work_type,
        project_id=project_id,
        date_from=date_from,
        date_to=date_to,
        scope_filter=scope,
        page=page,
        page_size=page_size,
    )
    return TimesheetListOut(total=total, items=[TimesheetOut.model_validate(x) for x in items])


@router.post("", response_model=TimesheetOut, summary="登记工时")
def create_timesheet(
    payload: TimesheetCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["timesheet:view"]))],
) -> TimesheetOut:
    return TimesheetOut.model_validate(timesheet_service.create_timesheet(db, current_user, payload))


@router.get("/{ts_id}", response_model=TimesheetOut, summary="工时详情")
def get_timesheet(
    ts_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["timesheet:view"]))],
) -> TimesheetOut:
    return TimesheetOut.model_validate(timesheet_service.get_timesheet(db, current_user, ts_id))


@router.patch("/{ts_id}", response_model=TimesheetOut, summary="编辑工时")
def update_timesheet(
    ts_id: int,
    payload: TimesheetUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["timesheet:view"]))],
) -> TimesheetOut:
    return TimesheetOut.model_validate(
        timesheet_service.update_timesheet(db, current_user, ts_id, payload)
    )


@router.post("/{ts_id}/submit", response_model=TimesheetOut, summary="提交审批")
def submit_timesheet(
    ts_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["timesheet:view"]))],
) -> TimesheetOut:
    return TimesheetOut.model_validate(timesheet_service.submit_timesheet(db, current_user, ts_id))


@router.post("/{ts_id}/approve", response_model=TimesheetOut, summary="审批通过")
def approve_timesheet(
    ts_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["timesheet:view"]))],
) -> TimesheetOut:
    return TimesheetOut.model_validate(timesheet_service.approve_timesheet(db, current_user, ts_id))


@router.post("/{ts_id}/reject", response_model=TimesheetOut, summary="驳回")
def reject_timesheet(
    ts_id: int,
    payload: TimesheetRejectRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["timesheet:view"]))],
) -> TimesheetOut:
    return TimesheetOut.model_validate(
        timesheet_service.reject_timesheet(db, current_user, ts_id, payload)
    )
