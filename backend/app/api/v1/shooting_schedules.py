"""拍摄排期 API。"""
from typing import Annotated, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.asset import ShootingScheduleCreate, ShootingScheduleOut
from app.services import asset as asset_service

router = APIRouter(prefix="/shooting-schedules", tags=["拍摄排期"])


@router.get("", response_model=List[ShootingScheduleOut], summary="拍摄排期列表")
def list_schedules(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> List[ShootingScheduleOut]:
    _ = current_user
    return [
        ShootingScheduleOut.model_validate(x)
        for x in asset_service.list_shooting_schedules(db)
    ]


@router.post("", response_model=ShootingScheduleOut, summary="创建拍摄排期")
def create_schedule(
    payload: ShootingScheduleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> ShootingScheduleOut:
    return ShootingScheduleOut.model_validate(
        asset_service.create_shooting_schedule(db, current_user, payload)
    )


@router.get("/{schedule_id}", response_model=ShootingScheduleOut, summary="拍摄排期详情")
def get_schedule(
    schedule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> ShootingScheduleOut:
    _ = current_user
    return ShootingScheduleOut.model_validate(
        asset_service.get_shooting_schedule(db, schedule_id)
    )


@router.post("/{schedule_id}/confirm", response_model=ShootingScheduleOut, summary="确认排期")
def confirm_schedule(
    schedule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> ShootingScheduleOut:
    return ShootingScheduleOut.model_validate(
        asset_service.confirm_shooting_schedule(db, current_user, schedule_id)
    )


@router.post("/{schedule_id}/cancel", response_model=ShootingScheduleOut, summary="取消排期")
def cancel_schedule(
    schedule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> ShootingScheduleOut:
    return ShootingScheduleOut.model_validate(
        asset_service.cancel_shooting_schedule(db, current_user, schedule_id)
    )
