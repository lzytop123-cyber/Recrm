"""审批中心 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.approval import (
    ApprovalActRequest,
    ApprovalActResult,
    ApprovalDetailOut,
    ApprovalListOut,
    ApprovalStatsOut,
    FlowActivityItem,
    FlowActivityOut,
)
from app.services import approval as approval_service
from app.services import approval_flow as approval_flow_service

router = APIRouter(prefix="/approvals", tags=["审批中心"])


@router.get("/stats", response_model=ApprovalStatsOut, summary="审批统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> ApprovalStatsOut:
    return approval_service.approval_stats(db, current_user)


@router.get("/resolve", summary="按业务实体解析进行中审批单")
def resolve_open(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    biz_type: Annotated[str, Query(min_length=1)],
    biz_id: Annotated[int, Query(ge=1)],
) -> dict[str, str]:
    return approval_service.resolve_open_approval(
        db, current_user, biz_type=biz_type, biz_id=biz_id
    )


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


# biz_type → 承载实体的分组标签（同实体的多个 biz_type 走同一条 assert_can_view）
_BIZ_GROUP: dict[str, str] = {
    "contract": "contract",
    "contract_activate": "contract",
    "contract_terminate": "contract",
    "contract_modify": "contract",
    "ticket": "ticket",
    "ticket_cross_accept": "ticket",
    "schedule": "schedule",
    "project_no_contract": "project",
    "project_initiation": "project",
    "project_handover": "project",
    "project_acceptance": "project",
    "project_settlement": "project",
    "project_terminate": "project",
    "refund": "refund",
    "receipt": "receipt",
    "receipt_diff": "receipt",
    "asset_borrow": "asset",
    "asset_return": "asset",
    "asset_maintenance": "asset",
    "asset_inventory_diff": "asset",
    "asset_compensation": "asset",
    "timesheet": "timesheet",
    "role_change": "role_change",
}


def _assert_can_view_group(db: Session, user: User, group: str, biz_id: int) -> None:
    """按业务分组校验查看权，避免越权读审批日志。"""
    if group == "contract":
        from app.models.contract import Contract
        from app.services import contract as svc

        entity = db.query(Contract).filter(Contract.id == biz_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="业务对象不存在")
        svc.assert_can_view(user, entity)
        return
    if group == "ticket":
        from app.models.ticket import Ticket
        from app.services import ticket as svc

        entity = db.query(Ticket).filter(Ticket.id == biz_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="业务对象不存在")
        svc.assert_can_view(user, entity)
        return
    if group == "schedule":
        from app.models.schedule import Schedule
        from app.services import schedule as svc

        entity = db.query(Schedule).filter(Schedule.id == biz_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="业务对象不存在")
        svc.assert_can_view(user, entity)
        return
    if group == "project":
        from app.models.project import Project
        from app.services import project as svc

        entity = db.query(Project).filter(Project.id == biz_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="业务对象不存在")
        svc.assert_can_view(user, entity)
        return
    if group == "timesheet":
        from app.models.timesheet import Timesheet
        from app.services import timesheet as svc

        entity = db.query(Timesheet).filter(Timesheet.id == biz_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="业务对象不存在")
        svc.assert_can_view(user, entity)
        return
    # refund / receipt / asset / role_change 无逐条 assert_can_view，走审批中心权限或管理员
    from app.core.rbac import user_can

    if "admin" in {r.code for r in (user.roles or [])} or user_can(user, "approval:center"):
        return
    raise HTTPException(status_code=403, detail="无权查看该业务的审批日志")


def _assert_can_view_biz(
    db: Session, user: User, biz_types: list[str], biz_id: int
) -> None:
    if not biz_types:
        raise HTTPException(status_code=400, detail="必须传入 biz_type")
    groups = {_BIZ_GROUP.get(bt, bt) for bt in biz_types}
    if len(groups) > 1:
        # 不允许把不同业务实体的类型拼在一起（防止绕权）
        raise HTTPException(status_code=400, detail="biz_type 必须属于同一业务实体")
    _assert_can_view_group(db, user, next(iter(groups)), biz_id)


@router.get(
    "/flow/activity",
    response_model=FlowActivityOut,
    summary="业务实体的审批操作日志",
)
def flow_activity(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    biz_type: Annotated[
        list[str], Query(min_length=1, description="可重复传多个（同实体的不同审批流）")
    ],
    biz_id: Annotated[int, Query(ge=1)],
) -> FlowActivityOut:
    """给业务详情页嵌"审批操作日志"卡片用；权限跟随业务实体的查看权。

    合同/项目/工单这类同实体多流程的详情页，把所有相关 biz_type 一次传进来，服务端合并按时间倒序返回。
    """
    # 支持 ?biz_type=a&biz_type=b，也支持 ?biz_type=a,b
    expanded: list[str] = []
    for bt in biz_type:
        expanded.extend([p.strip() for p in bt.split(",") if p.strip()])
    _assert_can_view_biz(db, current_user, expanded, biz_id)
    items = approval_flow_service.list_flow_activity(db, expanded, biz_id)
    return FlowActivityOut(
        biz_type=",".join(expanded),
        biz_id=biz_id,
        items=[FlowActivityItem(**item) for item in items],
    )
