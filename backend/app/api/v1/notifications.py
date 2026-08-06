"""站内通知 API。"""
from typing import Annotated, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.system import NotificationOut
from app.services import platform as platform_service

router = APIRouter(prefix="/notifications", tags=["通知"])


@router.get("", response_model=List[NotificationOut], summary="我的通知")
def list_notifications(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> List[NotificationOut]:
    return [
        NotificationOut.model_validate(x)
        for x in platform_service.list_notifications(db, current_user)
    ]


@router.get("/{notification_id}", response_model=NotificationOut, summary="通知详情")
def get_notification(
    notification_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationOut:
    return NotificationOut.model_validate(
        platform_service.get_notification(db, current_user, notification_id)
    )


@router.post("/read-all", summary="全部已读")
def read_all(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return platform_service.mark_all_notifications_read(db, current_user)


@router.post("/{notification_id}/read", response_model=NotificationOut, summary="标记已读")
def read_one(
    notification_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationOut:
    return NotificationOut.model_validate(
        platform_service.mark_notification_read(db, current_user, notification_id)
    )
