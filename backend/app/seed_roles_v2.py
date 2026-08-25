"""角色 v2（15 岗 + 系统管理员）种子与旧角色迁移。

对照《角色权限矩阵与审批流程配置表》v2：24 旧角色合并为 15 个正式岗位角色；
系统管理员仍用 code=admin（与全站 RBAC 放行一致）。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.user import User

# 旧 code -> 新 code（一人多旧角色时去重后替换）
LEGACY_ROLE_TO_V2: dict[str, str] = {
    "board": "chairman",
    "executive": "gm",
    "middle_manager": "center_lead",
    "delivery_lead": "pm",
    "operations": "ops",
    "developer": "ops",
    "instructor": "ops",
    "brand": "staff",
    "employee": "staff",
    "hr_supervisor": "hr",
    "asset_admin": "admin_office",
    # 以下 code 不变
    "dept_head": "dept_head",
    "sales": "sales",
    "finance": "finance",
    "admin": "admin",
}

# 预置 v2 角色：(name, code, data_scope, permission_codes)
# permission_codes 与旧种子对齐，按配置表裁剪/合并。
ROLES_V2: list[tuple[str, str, str, list[str]]] = [
    ("系统管理员", "admin", "company", ["*"]),
    ("董事长", "chairman", "company", [
        "dashboard:view", "approval:center",
        "lead:view", "customer:view", "opportunity:view",
        "contract:view", "contract:approve", "contract:complete", "payment:view",
        "project:view", "project:accept_approve", "project:complete",
        "ticket:view", "schedule:view", "org:view", "knowledge:view",
    ]),
    ("总经理", "gm", "company", [
        "dashboard:view", "approval:center",
        "lead:view", "lead:manage", "customer:view", "opportunity:view",
        "contract:view", "contract:approve", "contract:complete",
        "payment:view", "payment:refund",
        "project:view", "project:manage",
        "project:accept_submit", "project:accept_approve",
        "project:finance_submit", "project:complete",
        "okr:view", "timesheet:view", "timesheet:approve",
        "ticket:view", "schedule:view", "asset:view", "asset:manage",
        "knowledge:view", "org:view",
    ]),
    ("副总经理", "vp", "company", [
        "dashboard:view", "approval:center",
        "lead:view", "customer:view", "opportunity:view",
        "contract:view", "contract:approve", "payment:view",
        "project:view", "project:manage", "project:accept_approve",
        "ticket:view", "schedule:view", "knowledge:view",
    ]),
    ("中心负责人", "center_lead", "department", [
        "dashboard:view", "approval:center",
        "lead:view", "lead:manage", "customer:view", "opportunity:view",
        "contract:view", "contract:approve", "contract:complete",
        "payment:view",
        "project:view", "project:manage",
        "project:accept_submit", "project:accept_approve",
        "project:finance_submit", "project:complete",
        "okr:view", "timesheet:view", "timesheet:approve",
        "ticket:view", "schedule:view", "asset:view", "asset:manage",
        "knowledge:view", "knowledge:manage", "org:view",
    ]),
    ("部门负责人", "dept_head", "department", [
        "dashboard:view", "approval:center",
        "lead:view", "customer:view",
        "contract:view", "contract:approve", "contract:complete",
        "project:view", "project:accept_submit", "project:accept_approve",
        "project:finance_submit", "project:complete",
        "ticket:view", "schedule:view", "okr:view", "knowledge:view",
        "timesheet:view", "timesheet:approve",
    ]),
    ("销售", "sales", "department", [
        "dashboard:view",
        "lead:view", "customer:view", "customer:manage",
        "opportunity:view", "opportunity:manage",
        "contract:view", "contract:complete",
        "payment:view", "payment:claim",
        "ticket:view",
        "knowledge:view",
    ]),
    ("项目负责人", "pm", "department", [
        "dashboard:view", "approval:center",
        "customer:view", "contract:view",
        "project:view", "project:manage",
        "project:accept_submit", "project:accept_approve",
        "project:finance_submit", "project:complete",
        "timesheet:view", "timesheet:approve",
        "ticket:view", "schedule:view", "knowledge:view",
    ]),
    ("运营", "ops", "department", [
        "dashboard:view", "approval:center",
        "lead:view", "customer:view", "project:view",
        "ticket:view", "timesheet:view", "schedule:view",
        "asset:view", "asset:manage",
        "knowledge:view",
    ]),
    ("财务", "finance", "company", [
        "lead:view", "approval:center",
        "contract:view", "contract:approve", "contract:complete",
        "payment:view", "payment:manage", "payment:claim",
        "payment:confirm", "payment:allocate", "payment:refund",
        "project:view", "project:finance_approve",
        "customer:view",
    ]),
    ("法务", "legal", "company", [
        "approval:center",
        "contract:view", "contract:approve",
        "customer:view", "knowledge:view",
    ]),
    ("行政管理", "admin_office", "company", [
        "lead:view", "approval:center",
        "asset:view", "asset:manage", "knowledge:view",
        "ticket:view", "schedule:view",
    ]),
    ("行政专员", "admin_staff", "department", [
        "asset:view", "knowledge:view",
    ]),
    ("人力资源", "hr", "company", [
        "lead:view", "approval:center", "org:view", "org:manage",
        "okr:view", "ticket:view", "schedule:view", "knowledge:view",
    ]),
    ("普通员工", "staff", "personal", [
        "lead:view", "okr:view", "timesheet:view",
        "ticket:view", "schedule:view", "asset:view",
        "knowledge:view",
    ]),
]

DEPRECATED_ROLE_CODES = frozenset({
    "board", "executive", "middle_manager", "employee", "delivery_lead",
    "operations", "developer", "instructor", "brand", "hr_supervisor", "asset_admin",
})

# 开发/演示：给 admin 账号补齐审批链角色，避免无人审批挂起
DEMO_ADMIN_EXTRA_ROLES = (
    "chairman", "gm", "vp", "center_lead", "dept_head",
    "finance", "legal", "admin_office", "hr",
)


def seed_roles_v2(db: Session, perm_map: dict) -> None:
    """写入/同步 v2 角色权限包。"""
    for name, code, data_scope, perm_codes in ROLES_V2:
        role = db.query(Role).filter(Role.code == code).first()
        if not role:
            # 同名即认领（兼容自定义编码角色：董事长/001、总经理/002 等），
            # 避免 name 唯一约束冲突；编码自动升级为 v2 标准码（审批流依赖）。
            role = db.query(Role).filter(Role.name == name).first()
        if not role:
            role = Role(name=name, code=code, data_scope=data_scope, description=name)
            db.add(role)
            db.flush()
            print(f"[seed] 创建角色 v2: {name} ({code})")
        else:
            code_changed = role.code != code and role.code != "admin"
            role.name = name
            if code_changed:
                role.code = code
            # 已有角色保留其数据范围（尊重线上自定义配置），仅新角色用默认值
            if not role.data_scope:
                role.data_scope = data_scope
            if not role.description:
                role.description = name
            print(
                f"[seed] 更新角色 v2: {name} ({code})"
                + (" [编码已升级]" if code_changed else "")
            )
        if perm_codes == ["*"]:
            role.permissions = list(perm_map.values())
        else:
            role.permissions = [perm_map[c] for c in perm_codes if c in perm_map]


def migrate_user_roles_to_v2(db: Session) -> None:
    """将用户身上的旧角色码替换为 v2 码（保留已是 v2 的绑定）。"""
    v2_by_code = {r.code: r for r in db.query(Role).all()}
    migrated_users = 0
    for user in db.query(User).filter(User.is_active.is_(True)).all():
        new_codes: list[str] = []
        for role in user.roles or []:
            target = LEGACY_ROLE_TO_V2.get(role.code, role.code)
            if target not in new_codes:
                new_codes.append(target)
        new_roles = [v2_by_code[c] for c in new_codes if c in v2_by_code]
        if not new_roles:
            continue
        before = {r.code for r in user.roles}
        after = {r.code for r in new_roles}
        if before != after:
            user.roles = new_roles
            migrated_users += 1
    if migrated_users:
        print(f"[seed] 已迁移 {migrated_users} 个用户角色至 v2")


def bind_demo_approval_roles(db: Session) -> None:
    """演示环境：admin 账号绑定审批链关键角色，避免 dept_head 等无人挂起。"""
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        return
    by_code = {r.code: r for r in db.query(Role).filter(Role.code.in_(DEMO_ADMIN_EXTRA_ROLES)).all()}
    existing = {r.code for r in admin.roles}
    added = []
    for code in DEMO_ADMIN_EXTRA_ROLES:
        role = by_code.get(code)
        if role and code not in existing:
            admin.roles.append(role)
            added.append(code)
    if added:
        print(f"[seed] admin 演示绑定审批角色: {', '.join(added)}")
