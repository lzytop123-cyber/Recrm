"""工单 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.ticket import (
    TicketAssignRequest,
    TicketCloseRequest,
    TicketCommentRequest,
    TicketCompleteRequest,
    TicketConfirmRequest,
    TicketCreate,
    TicketDetailOut,
    TicketListOut,
    TicketOut,
    TicketReopenRequest,
    TicketReturnRequest,
    TicketSlaScanOut,
    TicketStatsOut,
    TicketTransferRequest,
    TicketUpdate,
)
from app.services import ticket as ticket_service

router = APIRouter(prefix="/tickets", tags=["工单管理"])


class AssigneeOption(BaseModel):
    id: int
    name: str
    department_id: Optional[int] = None


@router.get("/stats", response_model=TicketStatsOut, summary="工单统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketStatsOut:
    # 列表/看板加载时顺带扫描 SLA，保证提醒与升级落库
    ticket_service.scan_sla(db, current_user)
    return TicketStatsOut(**ticket_service.ticket_stats(db, current_user))


@router.post("/sla/scan", response_model=TicketSlaScanOut, summary="扫描 SLA 提醒与升级")
def sla_scan(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketSlaScanOut:
    return TicketSlaScanOut(**ticket_service.scan_sla(db, current_user))


@router.get("/options/assignees", response_model=list[AssigneeOption], summary="处理人选项")
def assignee_options(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
    department_id: Optional[int] = Query(None, description="按承接部门筛选"),
) -> list[AssigneeOption]:
    _ = current_user
    return [
        AssigneeOption(**x)
        for x in ticket_service.list_assignee_options(db, department_id=department_id)
    ]


@router.get("", response_model=TicketListOut, summary="工单列表")
def list_tickets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
    status: Optional[str] = None,
    ticket_type: Optional[str] = None,
    priority: Optional[str] = None,
    keyword: Optional[str] = None,
    project_id: Optional[int] = None,
    department_id: Optional[int] = None,
    scope: Optional[str] = Query(None, description="mine/mine_created/mine_assigned/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> TicketListOut:
    total, items = ticket_service.list_tickets(
        db,
        current_user,
        status=status,
        ticket_type=ticket_type,
        priority=priority,
        keyword=keyword,
        project_id=project_id,
        department_id=department_id,
        scope_filter=scope,
        page=page,
        page_size=page_size,
    )
    return TicketListOut(total=total, items=[TicketOut.model_validate(x) for x in items])


@router.post("", response_model=TicketDetailOut, summary="创建工单")
def create_ticket(
    payload: TicketCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.create_ticket(db, current_user, payload)
    )


@router.get("/{ticket_id}", response_model=TicketDetailOut, summary="工单详情")
def get_ticket(
    ticket_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.get_ticket(db, current_user, ticket_id)
    )


@router.patch("/{ticket_id}", response_model=TicketDetailOut, summary="编辑工单")
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.update_ticket(db, current_user, ticket_id, payload)
    )


@router.post("/{ticket_id}/assign", response_model=TicketDetailOut, summary="分派")
def assign_ticket(
    ticket_id: int,
    payload: TicketAssignRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.assign_ticket(db, current_user, ticket_id, payload)
    )


@router.post("/{ticket_id}/accept", response_model=TicketDetailOut, summary="受理")
def accept_ticket(
    ticket_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.accept_ticket(db, current_user, ticket_id)
    )


@router.post("/{ticket_id}/transfer", response_model=TicketDetailOut, summary="转派")
def transfer_ticket(
    ticket_id: int,
    payload: TicketTransferRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.transfer_ticket(db, current_user, ticket_id, payload)
    )


@router.post("/{ticket_id}/complete", response_model=TicketDetailOut, summary="提交完成")
def complete_ticket(
    ticket_id: int,
    payload: TicketCompleteRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.complete_ticket(db, current_user, ticket_id, payload)
    )


@router.post("/{ticket_id}/return", response_model=TicketDetailOut, summary="退回处理")
def return_ticket(
    ticket_id: int,
    payload: TicketReturnRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.return_ticket(db, current_user, ticket_id, payload)
    )


@router.post("/{ticket_id}/confirm", response_model=TicketDetailOut, summary="确认并评价关闭")
def confirm_ticket(
    ticket_id: int,
    payload: TicketConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.confirm_ticket(db, current_user, ticket_id, payload)
    )


@router.post("/{ticket_id}/close", response_model=TicketDetailOut, summary="关闭")
def close_ticket(
    ticket_id: int,
    payload: TicketCloseRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.close_ticket(db, current_user, ticket_id, payload)
    )


@router.post("/{ticket_id}/reopen", response_model=TicketDetailOut, summary="重开工单")
def reopen_ticket(
    ticket_id: int,
    payload: TicketReopenRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.reopen_ticket(db, current_user, ticket_id, payload)
    )


@router.post("/{ticket_id}/comments", response_model=TicketDetailOut, summary="添加评论")
def comment_ticket(
    ticket_id: int,
    payload: TicketCommentRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> TicketDetailOut:
    return TicketDetailOut.model_validate(
        ticket_service.comment_ticket(db, current_user, ticket_id, payload)
    )
