"""审批中心 API（仅系统管理员）。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.approval import ApprovalListOut, ApprovalStatsOut
from app.services import approval as approval_service

router = APIRouter(prefix="/approvals", tags=["审批中心"])


@router.get("/stats", response_model=ApprovalStatsOut, summary="审批统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> ApprovalStatsOut:
    return approval_service.approval_stats(db, current_user)


@router.get("", response_model=ApprovalListOut, summary="审批列表")
def list_approvals(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    tab: Annotated[str, Query(description="pending/initiated/processed/cc")] = "pending",
    category: Annotated[Optional[str], Query()] = None,
    keyword: Annotated[Optional[str], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApprovalListOut:
    return approval_service.list_approvals(
        db,
        current_user,
        tab=tab,
        category=category,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
