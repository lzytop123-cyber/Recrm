"""菜单与权限码映射：登录后返回给前端渲染左侧菜单。"""
from typing import List, Set

from app.core.rbac import collect_permission_codes, collect_data_scopes, widest_data_scope
from app.models.user import User
from app.schemas.auth import MenuItem, RoleBrief, UserInfoResponse

# 仅线索录入岗（非销售链路）
LEAD_ENTRY_ONLY_ROLE_CODES: Set[str] = {
    "dept_head",  # 部门负责人
    "brand",  # 品宣专员
    "finance",  # 财务
    "hr_supervisor",  # 综合管理主管
    "asset_admin",  # 资产管理员
    "employee",  # 普通员工：也可录入，但不进销售全链路
}

# 菜单定义：permission 为空表示登录即可见；有值则需具备对应权限（admin 角色放行）
MENU_CATALOG: List[dict] = [
    {"path": "/dashboard", "title": "经营总览", "icon": "Odometer", "permission": "dashboard:view"},
    {"path": "/todos", "title": "我的待办", "icon": "Bell", "permission": None},
    {"path": "/approvals", "title": "审批中心", "icon": "CircleCheck", "permission": "approval:center"},
    {"path": "/lead-entry", "title": "线索录入", "icon": "EditPen", "permission": "lead:view"},
    {"path": "/sales", "title": "销售中心", "icon": "Promotion", "permission": "lead:view"},
    {"path": "/contracts", "title": "合同回款", "icon": "Wallet", "permission": "contract:view"},
    {"path": "/projects", "title": "项目台账", "icon": "Briefcase", "permission": "project:view"},
    {"path": "/projects/delivery", "title": "交付执行", "icon": "Finished", "permission": "project:view"},
    {"path": "/tickets", "title": "协作工单", "icon": "Tickets", "permission": "ticket:view"},
    {"path": "/schedules", "title": "排期会议", "icon": "Calendar", "permission": "schedule:view"},
    {"path": "/okrs", "title": "目标绩效", "icon": "Flag", "permission": "okr:view"},
    {"path": "/assets", "title": "固定资产", "icon": "Box", "permission": "asset:view"},
    {"path": "/org", "title": "员工管理", "icon": "OfficeBuilding", "permission": "org:view"},
    {"path": "/system", "title": "系统管理", "icon": "Setting", "permission": "system:view"},
]

# 第二期再开放：菜单隐藏，路由/API 仍保留便于以后打开
PHASE2_HIDDEN_MENU_PATHS: Set[str] = {
    "/okrs",
}


def is_lead_entry_only(user: User) -> bool:
    """无销售全链路权限的岗位：登录后走线索录入页。"""
    role_codes = {r.code for r in user.roles}
    if role_codes & {"admin", "sales", "executive", "middle_manager", "board"}:
        return False
    if role_codes & LEAD_ENTRY_ONLY_ROLE_CODES:
        return True
    perms = set(collect_permission_codes(user))
    if "lead:view" not in perms and "*" not in perms:
        return False
    # 有线索查看但没有客户/商机/分配 → 视为仅录入
    return not (perms & {"customer:view", "opportunity:view", "lead:manage", "*"})


def build_menus_for_user(user: User) -> List[MenuItem]:
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    owned = collect_permission_codes(user)
    entry_only = is_lead_entry_only(user)
    menus: List[MenuItem] = []
    for item in MENU_CATALOG:
        path = item["path"]
        if path in PHASE2_HIDDEN_MENU_PATHS:
            continue
        # 仅录入岗：显示线索录入，不显示完整销售中心
        if entry_only:
            if path == "/sales":
                continue
        else:
            if path == "/lead-entry":
                continue
        perm = item.get("permission")
        if perm is None or is_admin or perm in owned:
            menus.append(MenuItem(**item))
    return menus


def _resolve_home_path(user: User, *, entry_only: bool, permissions: List[str]) -> str:
    """首页：有经营总览权限优先；仅录入岗回线索录入；否则取首个可见菜单。"""
    perm_set = set(permissions)
    is_admin = any(r.code == "admin" for r in user.roles)
    if is_admin or "dashboard:view" in perm_set or "*" in perm_set:
        return "/dashboard"
    if entry_only:
        return "/lead-entry"
    menus = build_menus_for_user(user)
    if menus:
        return menus[0].path
    return "/lead-entry"


def build_user_info(user: User) -> UserInfoResponse:
    permissions = sorted(collect_permission_codes(user))
    scopes = collect_data_scopes(user)
    data_scope = widest_data_scope(scopes) if scopes else "personal"
    entry_only = is_lead_entry_only(user)
    # admin 默认公司级
    if any(r.code == "admin" for r in user.roles):
        data_scope = "company"
        if "*" not in permissions:
            permissions = ["*"] + permissions
        entry_only = False

    return UserInfoResponse(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        email=user.email,
        phone=user.phone,
        department_id=user.department_id,
        is_active=user.is_active,
        roles=[RoleBrief.model_validate(r) for r in user.roles],
        permissions=permissions,
        data_scope=data_scope,
        menus=build_menus_for_user(user),
        lead_entry_only=entry_only,
        home_path=_resolve_home_path(user, entry_only=entry_only, permissions=permissions),
    )
