"""菜单与权限码映射：登录后返回给前端渲染左侧菜单。"""
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.core.rbac import collect_permission_codes, collect_data_scopes, widest_data_scope
from app.models.menu_visibility import MenuVisibility
from app.models.user import User
from app.schemas.auth import MenuItem, RoleBrief, UserInfoResponse

# 仅线索录入岗（非销售链路）
LEAD_ENTRY_ONLY_ROLE_CODES: Set[str] = {
    "dept_head",
    "admin_staff",
    "finance",
    "hr",
    "admin_office",
    "staff",
    "ops",
}

# 菜单定义：permission 为空表示登录即可见；有值则需具备对应权限（admin 角色放行）
# children 非空时为一级分组，侧栏以 el-sub-menu 展开
MENU_CATALOG: List[dict] = [
    {"path": "/dashboard", "title": "经营总览", "icon": "Odometer", "permission": "dashboard:view"},
    {"path": "/todos", "title": "我的待办", "icon": "Bell", "permission": None},
    {"path": "/approvals", "title": "审批中心", "icon": "CircleCheck", "permission": "approval:center"},
    {"path": "/lead-entry", "title": "线索录入", "icon": "EditPen", "permission": "lead:view"},
    {"path": "/sales", "title": "销售中心", "icon": "Promotion", "permission": "lead:view"},
    {"path": "/contracts", "title": "合同回款", "icon": "Wallet", "permission": "contract:view"},
    {"path": "/projects", "title": "项目管理", "icon": "Briefcase", "permission": "project:view"},
    {"path": "/tickets", "title": "协作工单", "icon": "Tickets", "permission": "ticket:view"},
    {"path": "/schedules", "title": "排期会议", "icon": "Calendar", "permission": "schedule:view"},
    {"path": "/okrs", "title": "目标绩效", "icon": "Flag", "permission": "okr:view"},
    {
        "path": "/group/performance",
        "title": "绩效管理",
        "icon": "Trophy",
        "permission": None,
        "children": [
            {"path": "/performance/mine", "title": "我的绩效", "icon": "Trophy", "permission": None},
            {
                "path": "/performance/team",
                "title": "团队绩效",
                "icon": "UserFilled",
                "permission": None,
                "requires_subordinates": True,
            },
            {
                "path": "/performance/admin/cycles",
                "title": "绩效中心",
                "icon": "DataAnalysis",
                "permission": "kpi:template:manage",
            },
        ],
    },
    {"path": "/assets", "title": "固定资产", "icon": "Box", "permission": "asset:view"},
    {"path": "/knowledge", "title": "知识库", "icon": "Reading", "permission": "knowledge:view"},
    {"path": "/org", "title": "员工管理", "icon": "OfficeBuilding", "permission": "org:view"},
    {
        "path": "/group/system",
        "title": "系统设置",
        "icon": "Setting",
        "permission": "system:view",
        "children": [
            {"path": "/system", "title": "系统管理", "icon": "Setting", "permission": "system:view"},
            {
                "path": "/system/dictionaries",
                "title": "字典管理",
                "icon": "Collection",
                "permission": "system:view",
            },
            {
                "path": "/system/approval-rules",
                "title": "审批规则",
                "icon": "SetUp",
                "permission": "system:view",
            },
        ],
    },
]

# 第二期再开放：菜单隐藏，路由/API 仍保留便于以后打开
PHASE2_HIDDEN_MENU_PATHS: Set[str] = {
    "/okrs",
}

# 这些角色有 ticket:view 时仍显示「协作工单」侧栏；纯销售有码可接单但不进全量菜单
TICKET_MENU_ROLE_CODES: Set[str] = {
    "admin",
    "chairman",
    "gm",
    "vp",
    "center_lead",
    "pm",
    "ops",
    "dept_head",
    "hr",
    "staff",
}


def iter_menu_leaves(catalog: Optional[List[dict]] = None) -> List[dict]:
    """展开目录叶子项（含权限/可见性校验用的真实 path）。"""
    leaves: List[dict] = []
    for item in catalog if catalog is not None else MENU_CATALOG:
        children = item.get("children") or []
        if children:
            leaves.extend(iter_menu_leaves(children))
        else:
            leaves.append(item)
    return leaves


def flatten_menu_paths(menus: List[MenuItem]) -> Set[str]:
    """收集用户可见菜单的全部 path（含分组节点与叶子）。"""
    out: Set[str] = set()
    for m in menus:
        out.add(m.path)
        if m.children:
            out |= flatten_menu_paths(m.children)
    return out


def _hide_tickets_menu(user: User) -> bool:
    """销售默认可接单（ticket:view + 待办），但不显示协作工单侧栏。"""
    role_codes = {r.code for r in user.roles}
    if role_codes & TICKET_MENU_ROLE_CODES:
        return False
    return "sales" in role_codes


def is_lead_entry_only(user: User) -> bool:
    """无销售全链路权限的岗位：登录后走线索录入页。"""
    role_codes = {r.code for r in user.roles}
    if role_codes & {"admin", "sales", "gm", "vp", "center_lead", "chairman"}:
        return False
    if role_codes & LEAD_ENTRY_ONLY_ROLE_CODES:
        return True
    perms = set(collect_permission_codes(user))
    if "lead:view" not in perms and "*" not in perms:
        return False
    # 有线索查看但没有客户/商机/分配 → 视为仅录入
    return not (perms & {"customer:view", "opportunity:view", "lead:manage", "*"})


def _load_visibility_overrides(
    db: Optional[Session], role_codes: Set[str]
) -> Dict[str, bool]:
    """
    返回 {menu_path: visible}。同一菜单若被多个角色覆盖，可见性取 OR：任一角色 True 即显示。
    未命中的路径不出现在结果里，走默认逻辑。
    表尚未建立时静默降级为空覆盖，避免阻塞登录。
    """
    if db is None or not role_codes:
        return {}
    try:
        rows = (
            db.query(MenuVisibility)
            .filter(MenuVisibility.role_code.in_(role_codes))
            .all()
        )
    except Exception:
        # 表未建 / DB 未就绪 → 退回默认菜单，不影响登录
        try:
            db.rollback()
        except Exception:
            pass
        return {}
    merged: Dict[str, bool] = {}
    for row in rows:
        prev = merged.get(row.menu_path)
        merged[row.menu_path] = bool(row.visible) if prev is None else (prev or bool(row.visible))
    return merged


def _filter_menu_item(
    item: dict,
    *,
    user: User,
    is_admin: bool,
    owned: Set[str],
    entry_only: bool,
    overrides: Dict[str, bool],
    has_subordinates: bool,
) -> Optional[MenuItem]:
    path = item["path"]
    children_raw = item.get("children") or []

    if children_raw:
        kids: List[MenuItem] = []
        for child in children_raw:
            filtered = _filter_menu_item(
                child,
                user=user,
                is_admin=is_admin,
                owned=owned,
                entry_only=entry_only,
                overrides=overrides,
                has_subordinates=has_subordinates,
            )
            if filtered is not None:
                kids.append(filtered)
        if not kids:
            return None
        # 分组节点本身不做 permission 拦截；有可见子项即展示
        return MenuItem(
            path=path,
            title=item["title"],
            icon=item.get("icon"),
            permission=item.get("permission"),
            children=kids,
        )

    if path in PHASE2_HIDDEN_MENU_PATHS:
        return None
    perm = item.get("permission")
    if not (perm is None or is_admin or perm in owned):
        return None
    if item.get("requires_subordinates") and not (is_admin or has_subordinates):
        return None

    payload = {k: v for k, v in item.items() if k not in ("requires_subordinates", "children")}
    if path in overrides:
        if overrides[path]:
            return MenuItem(**payload)
        return None

    if path == "/tickets" and _hide_tickets_menu(user):
        return None
    # 仅录入岗：显示线索录入，不显示完整销售中心
    if entry_only:
        if path == "/sales":
            return None
    else:
        if path == "/lead-entry":
            return None
    return MenuItem(**payload)


def build_menus_for_user(user: User, db: Optional[Session] = None) -> List[MenuItem]:
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    owned = collect_permission_codes(user)
    entry_only = is_lead_entry_only(user)
    overrides = _load_visibility_overrides(db, role_codes)
    has_subordinates = False
    if db is not None:
        has_subordinates = (
            db.query(User.id).filter(User.manager_id == user.id, User.is_active.is_(True)).first()
            is not None
        )
    menus: List[MenuItem] = []
    for item in MENU_CATALOG:
        filtered = _filter_menu_item(
            item,
            user=user,
            is_admin=is_admin,
            owned=owned,
            entry_only=entry_only,
            overrides=overrides,
            has_subordinates=has_subordinates,
        )
        if filtered is not None:
            menus.append(filtered)
    return menus


def _first_menu_path(menus: List[MenuItem]) -> Optional[str]:
    for m in menus:
        if m.children:
            child = _first_menu_path(m.children)
            if child:
                return child
        elif not m.path.startswith("/group/"):
            return m.path
    return None


def _resolve_home_path(
    user: User,
    *,
    entry_only: bool,
    permissions: List[str],
    db: Optional[Session] = None,
) -> str:
    """首页：有经营总览权限优先；仅录入岗回线索录入；否则取首个可见菜单。"""
    perm_set = set(permissions)
    is_admin = any(r.code == "admin" for r in user.roles)
    if is_admin or "dashboard:view" in perm_set or "*" in perm_set:
        return "/dashboard"
    if entry_only:
        return "/lead-entry"
    menus = build_menus_for_user(user, db)
    return _first_menu_path(menus) or "/lead-entry"


def build_user_info(user: User, db: Optional[Session] = None) -> UserInfoResponse:
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

    has_subordinates = False
    if db is not None:
        has_subordinates = (
            db.query(User.id).filter(User.manager_id == user.id, User.is_active.is_(True)).first()
            is not None
        )

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
        menus=build_menus_for_user(user, db),
        lead_entry_only=entry_only,
        home_path=_resolve_home_path(user, entry_only=entry_only, permissions=permissions, db=db),
        has_subordinates=has_subordinates,
    )
