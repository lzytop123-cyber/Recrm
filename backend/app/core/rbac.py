"""
RBAC 辅助：权限码校验、数据可见范围（公司 / 部门 / 个人）。
支持角色默认范围 + 按模块覆盖（module_scopes）。
"""
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Set

from fastapi import HTTPException, status


class DataScope(str, Enum):
    """数据可见范围：与角色表 data_scope 字段对应。"""

    COMPANY = "company"  # 全公司
    DEPARTMENT = "department"  # 本部门（含下级，后续可扩展）
    PERSONAL = "personal"  # 仅本人


VALID_SCOPES = {DataScope.COMPANY.value, DataScope.DEPARTMENT.value, DataScope.PERSONAL.value}


def collect_permission_codes(user) -> Set[str]:
    """汇总用户所有角色下的权限码。"""
    codes: Set[str] = set()
    for role in getattr(user, "roles", []) or []:
        for perm in getattr(role, "permissions", []) or []:
            if perm.code:
                codes.add(perm.code)
    return codes


def collect_data_scopes(user) -> Set[str]:
    """汇总用户角色的默认数据范围；取最宽范围由调用方自行解释。"""
    scopes: Set[str] = set()
    for role in getattr(user, "roles", []) or []:
        if role.data_scope:
            scopes.add(role.data_scope)
    return scopes


def widest_data_scope(scopes: Iterable[str]) -> str:
    """从多个范围中取最宽：company > department > personal。"""
    scope_set = set(scopes)
    if DataScope.COMPANY.value in scope_set:
        return DataScope.COMPANY.value
    if DataScope.DEPARTMENT.value in scope_set:
        return DataScope.DEPARTMENT.value
    return DataScope.PERSONAL.value


def _role_module_scope(role, module: str) -> str:
    raw = getattr(role, "module_scopes", None) or {}
    if isinstance(raw, dict) and module in raw:
        value = raw.get(module)
        if value in VALID_SCOPES:
            return value
    return role.data_scope or DataScope.PERSONAL.value


def _role_has_module_permission(role, module: str) -> bool:
    for perm in getattr(role, "permissions", []) or []:
        if getattr(perm, "module", None) == module:
            return True
        code = getattr(perm, "code", None) or ""
        if code.split(":", 1)[0] == module:
            return True
    return False


def resolve_data_scope(user, module: str) -> str:
    """
    按业务模块解析数据范围。
    - admin → company
    - 仅统计拥有该模块权限的角色
    - 每角色取 module_scopes[module] 或 data_scope，再取最宽
    - 无匹配角色时回退 personal
    """
    role_codes = {r.code for r in (getattr(user, "roles", []) or [])}
    if "admin" in role_codes:
        return DataScope.COMPANY.value

    scopes: Set[str] = set()
    for role in getattr(user, "roles", []) or []:
        if not _role_has_module_permission(role, module):
            continue
        scopes.add(_role_module_scope(role, module))

    if not scopes:
        return DataScope.PERSONAL.value
    return widest_data_scope(scopes)


def require_permissions(user, required: Iterable[str], *, any_of: bool = False) -> None:
    """
    校验用户是否具备所需权限。
    - any_of=False：必须全部拥有
    - any_of=True：拥有其一即可
    系统管理员角色（code=admin）直接放行。
    """
    role_codes = {r.code for r in (getattr(user, "roles", []) or [])}
    if "admin" in role_codes:
        return

    owned = collect_permission_codes(user)
    required_set = set(required)
    if any_of:
        if owned.isdisjoint(required_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限（任一即可）: {', '.join(sorted(required_set))}",
            )
        return

    missing = required_set - owned
    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"缺少权限: {', '.join(sorted(missing))}",
        )


def user_can(user, permission_code: str) -> bool:
    """判断用户是否拥有某权限码（含 admin 放行）。"""
    role_codes = {r.code for r in (getattr(user, "roles", []) or [])}
    if "admin" in role_codes:
        return True
    return permission_code in collect_permission_codes(user)


def user_dept_scope(user) -> Set[int]:
    """返回请求入口预计算好的部门数据范围（本部门 + 全部子孙）。

    - 挂在 user.dept_scope_ids 上（deps.get_current_user 生成）
    - 无部门时返回空集
    - 未挂（如未经 deps 走的内部调用）回退到 {user.department_id}
    """
    scope = getattr(user, "dept_scope_ids", None)
    if isinstance(scope, set):
        return scope
    dept_id = getattr(user, "department_id", None)
    return {dept_id} if dept_id else set()


def resolve_owner_filter(user, module: Optional[str] = None) -> dict:
    """
    根据数据范围返回查询过滤提示。
    传入 module 时按模块解析；未传则用角色默认范围最宽值（兼容旧调用）。
    """
    if module:
        scope = resolve_data_scope(user, module)
    else:
        scope = widest_data_scope(collect_data_scopes(user))
    if scope == DataScope.COMPANY.value:
        return {"scope": scope}
    if scope == DataScope.DEPARTMENT.value:
        return {"scope": scope, "department_id": user.department_id}
    return {"scope": DataScope.PERSONAL.value, "owner_id": user.id}


def normalize_module_scopes(
    raw: Optional[Dict[str, Any]],
    *,
    known_modules: Optional[Set[str]] = None,
) -> Dict[str, str]:
    """校验并规范化 module_scopes；空/无效项丢弃。"""
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="module_scopes 必须为对象")
    out: Dict[str, str] = {}
    for key, value in raw.items():
        module = str(key).strip()
        if not module:
            continue
        if known_modules is not None and module not in known_modules:
            raise HTTPException(status_code=400, detail=f"未知权限模块: {module}")
        if value not in VALID_SCOPES:
            raise HTTPException(
                status_code=400,
                detail=f"模块 {module} 的数据范围无效，应为 company/department/personal",
            )
        out[module] = value
    return out
