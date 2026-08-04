"""系统管理 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.system import (
    AuditLogListOut,
    AuditLogOut,
    PermissionOut,
    RoleCreate,
    RoleOut,
    RoleUpdate,
    SystemStatsOut,
)
from app.services import system as system_service

router = APIRouter(prefix="/system", tags=["系统管理"])


@router.get("/stats", response_model=SystemStatsOut, summary="系统统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> SystemStatsOut:
    _ = current_user
    return SystemStatsOut(**system_service.system_stats(db))


@router.get("/permissions", response_model=list[PermissionOut], summary="权限目录")
def list_permissions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> list[PermissionOut]:
    _ = current_user
    return [PermissionOut.model_validate(x) for x in system_service.list_permissions(db)]


@router.get("/roles", response_model=list[RoleOut], summary="角色列表")
def list_roles(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> list[RoleOut]:
    _ = current_user
    return [RoleOut.model_validate(x) for x in system_service.list_roles(db)]


@router.post("/roles", response_model=RoleOut, summary="创建角色")
def create_role(
    payload: RoleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> RoleOut:
    _ = current_user
    return RoleOut.model_validate(system_service.create_role(db, payload))


@router.get("/roles/{role_id}", response_model=RoleOut, summary="角色详情")
def get_role(
    role_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> RoleOut:
    _ = current_user
    return RoleOut.model_validate(system_service.get_role(db, role_id))


@router.patch("/roles/{role_id}", response_model=RoleOut, summary="编辑角色")
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> RoleOut:
    _ = current_user
    return RoleOut.model_validate(system_service.update_role(db, role_id, payload))


@router.delete("/roles/{role_id}", summary="删除角色")
def delete_role(
    role_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> dict:
    _ = current_user
    system_service.delete_role(db, role_id)
    return {"ok": True}


@router.get("/audit-logs", response_model=AuditLogListOut, summary="审计日志")
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["system:view"]))],
    module: Optional[str] = None,
    action: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> AuditLogListOut:
    _ = current_user
    total, items = system_service.list_audit_logs(
        db,
        module=module,
        action=action,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return AuditLogListOut(total=total, items=[AuditLogOut.model_validate(x) for x in items])
