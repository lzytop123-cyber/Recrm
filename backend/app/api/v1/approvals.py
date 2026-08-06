"""审批中心 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.approval import (
    ApprovalActRequest,
    ApprovalActResult,
    ApprovalDetailOut,
    ApprovalListOut,
    ApprovalStatsOut,
)
from app.services import approval as approval_service

router = APIRouter(prefix="/approvals", tags=["审批中心"])


@router.get("/stats", response_model=ApprovalStatsOut, summary="审批统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> ApprovalStatsOut:
    return approval_service.approval_stats(db, current_user)


@router.get("/cc", response_model=ApprovalListOut, summary="抄送我的（别名）")
def list_cc(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    category: Annotated[Optional[str], Query()] = None,
    keyword: Annotated[Optional[str], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApprovalListOut:
    return approval_service.list_approvals(
        db,
        current_user,
        tab="cc",
        category=category,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )


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


@router.get("/{approval_id}", response_model=ApprovalDetailOut, summary="审批详情")
def get_approval(
    approval_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> ApprovalDetailOut:
    return approval_service.get_approval(db, current_user, approval_id)


@router.post("/{approval_id}/approve", response_model=ApprovalActResult, summary="通过")
def approve(
    approval_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    payload: Optional[ApprovalActRequest] = None,
) -> ApprovalActResult:
    return approval_service.act_approval(
        db, current_user, approval_id, "approve", payload or ApprovalActRequest()
    )


@router.post("/{approval_id}/reject", response_model=ApprovalActResult, summary="驳回")
def reject(
    approval_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    payload: Optional[ApprovalActRequest] = None,
) -> ApprovalActResult:
    return approval_service.act_approval(
        db, current_user, approval_id, "reject", payload or ApprovalActRequest()
    )


@router.post("/{approval_id}/return", response_model=ApprovalActResult, summary="退回")
def return_approval(
    approval_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    payload: Optional[ApprovalActRequest] = None,
) -> ApprovalActResult:
    return approval_service.act_approval(
        db, current_user, approval_id, "return", payload or ApprovalActRequest()
    )


@router.post("/{approval_id}/transfer", response_model=ApprovalActResult, summary="转交")
def transfer(
    approval_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    payload: Optional[ApprovalActRequest] = None,
) -> ApprovalActResult:
    return approval_service.act_approval(
        db, current_user, approval_id, "transfer", payload or ApprovalActRequest()
    )


@router.post("/{approval_id}/remind", response_model=ApprovalActResult, summary="催办")
def remind(
    approval_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    payload: Optional[ApprovalActRequest] = None,
) -> ApprovalActResult:
    return approval_service.act_approval(
        db, current_user, approval_id, "remind", payload or ApprovalActRequest()
    )


@router.post("/{approval_id}/withdraw", response_model=ApprovalActResult, summary="撤回")
def withdraw(
    approval_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    payload: Optional[ApprovalActRequest] = None,
) -> ApprovalActResult:
    return approval_service.act_approval(
        db, current_user, approval_id, "withdraw", payload or ApprovalActRequest()
    )


@router.post("/{approval_id}/resubmit", response_model=ApprovalActResult, summary="重新提交")
def resubmit(
    approval_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    payload: Optional[ApprovalActRequest] = None,
) -> ApprovalActResult:
    return approval_service.act_approval(
        db, current_user, approval_id, "resubmit", payload or ApprovalActRequest()
    )
