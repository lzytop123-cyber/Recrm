"""系统管理 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_current_active_user
from app.database import get_db
from app.models.user import User
from app.schemas.system import (
    AccountOut,
    AccountUpdate,
    AuditLogListOut,
    AuditLogOut,
    DelegationCreate,
    DelegationOut,
    DelegationUpdate,
    DictionaryItemOut,
    ExportDownloadOut,
    ExportJobCreate,
    ExportJobOut,
    PermissionOut,
    RoleCreate,
    RoleOut,
    RoleUpdate,
    SystemConfigCreate,
    SystemConfigOut,
    SystemConfigUpdate,
    SystemDictionaryCreate,
    SystemDictionaryOut,
    SystemDictionaryUpdate,
    SystemStatsOut,
)
from app.services import platform as platform_service
from app.services import system as system_service

router = APIRouter(prefix="/system", tags=["系统管理"])

VIEW_SYSTEM = PermissionChecker(["system:view"])
MANAGE_SYSTEM = PermissionChecker(["system:manage"])


def _dictionary_out(row) -> SystemDictionaryOut:
    items = [
        DictionaryItemOut(
            value=x["value"],
            label=x["label"],
            enabled=bool(x.get("enabled", True)),
            sort=int(x.get("sort") or 100),
        )
        for x in platform_service.parse_dictionary_items(row.items_json)
    ]
    return SystemDictionaryOut(
        id=row.id,
        code=row.code,
        name=row.name,
        items_json=row.items_json,
        updated_at=row.updated_at,
        items=items,
    )


@router.get("/stats", response_model=SystemStatsOut, summary="系统统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> SystemStatsOut:
    _ = current_user
    return SystemStatsOut(**system_service.system_stats(db))


@router.get("/permissions", response_model=list[PermissionOut], summary="权限目录")
def list_permissions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> list[PermissionOut]:
    _ = current_user
    return [PermissionOut.model_validate(x) for x in system_service.list_permissions(db)]


@router.get("/roles", response_model=list[RoleOut], summary="角色列表")
def list_roles(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> list[RoleOut]:
    _ = current_user
    return [RoleOut.model_validate(x) for x in system_service.list_roles(db)]


@router.post("/roles", response_model=RoleOut, summary="创建角色")
def create_role(
    payload: RoleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> RoleOut:
    _ = current_user
    return RoleOut.model_validate(system_service.create_role(db, payload))


@router.get("/roles/{role_id}", response_model=RoleOut, summary="角色详情")
def get_role(
    role_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> RoleOut:
    _ = current_user
    return RoleOut.model_validate(system_service.get_role(db, role_id))


@router.patch("/roles/{role_id}", response_model=RoleOut, summary="编辑角色")
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> RoleOut:
    _ = current_user
    return RoleOut.model_validate(system_service.update_role(db, role_id, payload))


@router.delete("/roles/{role_id}", summary="删除角色")
def delete_role(
    role_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> dict:
    _ = current_user
    system_service.delete_role(db, role_id)
    return {"ok": True}


@router.get("/audit-logs", response_model=AuditLogListOut, summary="审计日志")
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
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


@router.get("/configs", response_model=list[SystemConfigOut], summary="系统配置列表")
def list_configs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> list[SystemConfigOut]:
    _ = current_user
    return [SystemConfigOut.model_validate(x) for x in platform_service.list_configs(db)]


@router.post("/configs", response_model=SystemConfigOut, summary="创建系统配置")
def create_config(
    payload: SystemConfigCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> SystemConfigOut:
    return SystemConfigOut.model_validate(
        platform_service.create_config(db, current_user, payload)
    )


@router.get("/configs/{key}", response_model=SystemConfigOut, summary="配置详情")
def get_config(
    key: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> SystemConfigOut:
    _ = current_user
    return SystemConfigOut.model_validate(platform_service.get_config(db, key))


@router.patch("/configs/{key}", response_model=SystemConfigOut, summary="更新配置")
def update_config(
    key: str,
    payload: SystemConfigUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> SystemConfigOut:
    return SystemConfigOut.model_validate(
        platform_service.update_config(db, current_user, key, payload)
    )


@router.get("/dictionaries", response_model=list[SystemDictionaryOut], summary="字典列表")
def list_dictionaries(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> list[SystemDictionaryOut]:
    _ = current_user
    return [_dictionary_out(x) for x in platform_service.list_dictionaries(db)]


@router.post("/dictionaries", response_model=SystemDictionaryOut, summary="创建字典")
def create_dictionary(
    payload: SystemDictionaryCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> SystemDictionaryOut:
    _ = current_user
    return _dictionary_out(platform_service.create_dictionary(db, payload))


@router.get(
    "/dictionaries/{code}",
    response_model=SystemDictionaryOut,
    summary="字典详情",
)
def get_dictionary(
    code: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> SystemDictionaryOut:
    _ = current_user
    return _dictionary_out(platform_service.get_dictionary(db, code))


@router.patch(
    "/dictionaries/{code}",
    response_model=SystemDictionaryOut,
    summary="更新字典",
)
def update_dictionary(
    code: str,
    payload: SystemDictionaryUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> SystemDictionaryOut:
    _ = current_user
    return _dictionary_out(platform_service.update_dictionary(db, code, payload))


@router.get(
    "/dictionaries/{code}/items",
    response_model=list[DictionaryItemOut],
    summary="字典选项（登录可读）",
)
def list_dictionary_items(
    code: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    enabled_only: bool = Query(True),
) -> list[DictionaryItemOut]:
    """业务下拉框用：任意登录用户可读，不要求 system:view。"""
    _ = current_user
    if code == platform_service.BUSINESS_TYPE_DICT_CODE:
        items = platform_service.list_business_type_items(db, enabled_only=enabled_only)
    elif code == platform_service.LEAD_SOURCE_DICT_CODE:
        items = platform_service.list_lead_source_items(db, enabled_only=enabled_only)
    else:
        # 预留：其它字典暂仍走管理权限
        raise HTTPException(status_code=404, detail="字典不存在")
    return [
        DictionaryItemOut(
            value=x["value"],
            label=x["label"],
            enabled=bool(x.get("enabled", True)),
            sort=int(x.get("sort") or 100),
        )
        for x in items
    ]


@router.get("/delegations", response_model=list[DelegationOut], summary="委托列表")
def list_delegations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> list[DelegationOut]:
    return [
        DelegationOut.model_validate(x)
        for x in platform_service.list_delegations(db, current_user)
    ]


@router.post("/delegations", response_model=DelegationOut, summary="创建委托")
def create_delegation(
    payload: DelegationCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> DelegationOut:
    return DelegationOut.model_validate(
        platform_service.create_delegation(db, current_user, payload)
    )


@router.patch("/delegations/{delegation_id}", response_model=DelegationOut, summary="更新委托")
def update_delegation(
    delegation_id: int,
    payload: DelegationUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> DelegationOut:
    return DelegationOut.model_validate(
        platform_service.update_delegation(db, current_user, delegation_id, payload)
    )


@router.post(
    "/delegations/{delegation_id}/revoke",
    response_model=DelegationOut,
    summary="撤销委托",
)
def revoke_delegation(
    delegation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> DelegationOut:
    return DelegationOut.model_validate(
        platform_service.revoke_delegation(db, current_user, delegation_id)
    )


@router.post("/exports", response_model=ExportJobOut, summary="创建导出任务")
def create_export(
    payload: ExportJobCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> ExportJobOut:
    return ExportJobOut.model_validate(
        platform_service.create_export_job(db, current_user, payload)
    )


@router.get(
    "/exports/{job_id}/download",
    response_model=ExportDownloadOut,
    summary="导出下载",
)
def download_export(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> ExportDownloadOut:
    return ExportDownloadOut(**platform_service.export_download(db, current_user, job_id))


@router.get("/jobs", response_model=list[ExportJobOut], summary="后台任务列表")
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> list[ExportJobOut]:
    _ = current_user
    return [ExportJobOut.model_validate(x) for x in platform_service.list_jobs(db)]


@router.get("/dead-letters", summary="死信队列")
def dead_letters(
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> list:
    _ = current_user
    return platform_service.list_dead_letters()


@router.post("/jobs/{job_id}/retry", response_model=ExportJobOut, summary="重试任务")
def retry_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> ExportJobOut:
    _ = current_user
    return ExportJobOut.model_validate(platform_service.retry_job(db, job_id))


@router.get("/accounts", response_model=list[AccountOut], summary="账号列表")
def list_accounts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> list[AccountOut]:
    _ = current_user
    return [AccountOut(**x) for x in platform_service.list_accounts(db)]


@router.post("/accounts", response_model=list[AccountOut], summary="账号列表(POST)")
def list_accounts_post(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_SYSTEM)],
) -> list[AccountOut]:
    return list_accounts(db, current_user)


@router.patch("/accounts/{account_id}", response_model=AccountOut, summary="更新账号")
def update_account(
    account_id: int,
    payload: AccountUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> AccountOut:
    _ = current_user
    return AccountOut(**platform_service.update_account(db, account_id, payload))


@router.post("/accounts/{account_id}/enable", response_model=AccountOut, summary="启用账号")
def enable_account(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> AccountOut:
    _ = current_user
    return AccountOut(**platform_service.set_account_active(db, account_id, active=True))


@router.post("/accounts/{account_id}/disable", response_model=AccountOut, summary="禁用账号")
def disable_account(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_SYSTEM)],
) -> AccountOut:
    _ = current_user
    return AccountOut(**platform_service.set_account_active(db, account_id, active=False))
