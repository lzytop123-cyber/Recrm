"""
RBAC 辅助：权限码校验、数据可见范围（公司 / 部门 / 个人）。
"""
from enum import Enum
from typing import Iterable, Optional, Set

from fastapi import HTTPException, status


class DataScope(str, Enum):
    """数据可见范围：与角色表 data_scope 字段对应。"""

    COMPANY = "company"  # 全公司
    DEPARTMENT = "department"  # 本部门（含下级，后续可扩展）
    PERSONAL = "personal"  # 仅本人


def collect_permission_codes(user) -> Set[str]:
    """汇总用户所有角色下的权限码。"""
    codes: Set[str] = set()
    for role in getattr(user, "roles", []) or []:
        for perm in getattr(role, "permissions", []) or []:
            if perm.code:
                codes.add(perm.code)
    return codes


def collect_data_scopes(user) -> Set[str]:
    """汇总用户角色的数据范围；取最宽范围由调用方自行解释。"""
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


def resolve_owner_filter(user) -> dict:
    """
    根据数据范围返回查询过滤提示（骨架用）。
    后续业务模块按此字典拼 SQLAlchemy filter。
    """
    scope = widest_data_scope(collect_data_scopes(user))
    if scope == DataScope.COMPANY.value:
        return {"scope": scope}
    if scope == DataScope.DEPARTMENT.value:
        return {"scope": scope, "department_id": user.department_id}
    return {"scope": DataScope.PERSONAL.value, "owner_id": user.id}
