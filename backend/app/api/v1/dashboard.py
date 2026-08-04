"""管理看板 API。"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardOut
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["管理看板"])

VIEW_DASHBOARD = PermissionChecker(["dashboard:view"])


@router.get("", response_model=DashboardOut, summary="经营总览")
def get_dashboard(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_DASHBOARD)],
) -> DashboardOut:
    return DashboardOut(**dashboard_service.build_dashboard(db, current_user))
