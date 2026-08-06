"""
初始化种子数据：部门、权限、预置角色、管理员账号。
用法（在 backend 目录、已激活 venv）：
  python -m app.seed
默认管理员：admin / admin123
"""
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import SessionLocal, engine
from app.models import (  # noqa: F401 — 确保 metadata 注册
    AuditLog,
    Contract,
    Customer,
    Department,
    KeyResult,
    Lead,
    LeadFollowUp,
    LeadLog,
    Okr,
    Opportunity,
    OpportunityActivity,
    Payment,
    Permission,
    Project,
    ProjectMilestone,
    Role,
    Schedule,
    Ticket,
    TicketRecord,
    Timesheet,
    User,
    Receipt,
    ReceiptAllocation,
    ReceivablePlan,
    Refund,
)
from app.database import Base

# 预置权限（骨架菜单 + 基础模块）
PERMISSIONS = [
    ("查看经营总览", "dashboard:view", "dashboard"),
    ("审批中心", "approval:center", "approval"),
    ("查看线索", "lead:view", "lead"),
    ("管理线索", "lead:manage", "lead"),
    ("查看客户", "customer:view", "customer"),
    ("管理客户", "customer:manage", "customer"),
    ("查看商机", "opportunity:view", "opportunity"),
    ("管理商机", "opportunity:manage", "opportunity"),
    ("查看合同", "contract:view", "contract"),
    ("管理合同", "contract:manage", "contract"),
    ("审批合同", "contract:approve", "contract"),
    ("完成合同", "contract:complete", "contract"),
    ("特批完成合同", "contract:force_complete", "contract"),
    ("查看收款", "payment:view", "payment"),
    ("管理收款", "payment:manage", "payment"),
    ("提交到款认领", "payment:claim", "payment"),
    ("复核到账", "payment:confirm", "payment"),
    ("执行收款核销", "payment:allocate", "payment"),
    ("管理退款", "payment:refund", "payment"),
    ("查看项目", "project:view", "project"),
    ("管理项目", "project:manage", "project"),
    ("发起项目验收", "project:accept_submit", "project"),
    ("审批项目验收", "project:accept_approve", "project"),
    ("提交财务核对", "project:finance_submit", "project"),
    ("审批财务核对", "project:finance_approve", "project"),
    ("项目结项", "project:complete", "project"),
    ("查看 OKR", "okr:view", "okr"),
    ("查看工时", "timesheet:view", "timesheet"),
    ("审批工时", "timesheet:approve", "timesheet"),
    ("查看工单", "ticket:view", "ticket"),
    ("查看排期", "schedule:view", "schedule"),
    ("查看固定资产", "asset:view", "asset"),
    ("查看知识库", "knowledge:view", "knowledge"),
    ("管理知识库", "knowledge:manage", "knowledge"),
    ("查看组织", "org:view", "org"),
    ("管理组织", "org:manage", "org"),
    ("同步组织", "org:sync", "org"),
    ("系统管理", "system:view", "system"),
]

# 预置角色：(name, code, data_scope, permission_codes)
# data_scope: company / department / personal
ROLES = [
    ("系统管理员", "admin", "company", ["*"]),  # * 表示全部，种子时绑定全部权限
    ("董事会", "board", "company", [
        "dashboard:view", "approval:center",
        "lead:view", "customer:view", "opportunity:view",
        "contract:view", "contract:approve", "contract:force_complete", "payment:view",
        "project:view", "project:accept_approve", "project:complete",
        "ticket:view", "schedule:view", "org:view", "knowledge:view",
    ]),
    ("管理层", "executive", "company", [
        # lead:manage：可查看/分配待分配线索池（与中层一致；销售无此权限）
        "dashboard:view", "approval:center",
        "lead:view", "lead:manage", "customer:view", "opportunity:view",
        "contract:view", "contract:approve", "contract:complete", "contract:force_complete",
        "payment:view",
        "project:view", "project:manage",
        "project:accept_submit", "project:accept_approve",
        "project:finance_submit", "project:complete",
        "okr:view", "timesheet:view", "timesheet:approve",
        "ticket:view", "schedule:view", "asset:view",
        "knowledge:view", "org:view",
    ]),
    ("中层管理", "middle_manager", "department", [
        "dashboard:view", "approval:center",
        "lead:view", "lead:manage", "customer:view", "opportunity:view",
        "contract:view", "contract:approve", "contract:complete", "contract:force_complete",
        "payment:view",
        "project:view", "project:manage",
        "project:accept_submit", "project:accept_approve",
        "project:finance_submit", "project:complete",
        "okr:view", "timesheet:view", "timesheet:approve",
        "ticket:view", "schedule:view", "asset:view",
        "knowledge:view", "knowledge:manage", "org:view",
    ]),
    ("普通员工", "employee", "personal", [
        "lead:view", "okr:view", "timesheet:view", "ticket:view", "schedule:view", "asset:view",
        "knowledge:view",
    ]),
    ("销售", "sales", "department", [
        # 无 lead:manage：待分配线索池仅管理层/中层可看，销售只处理已分配线索
        # 无 contract:force_complete：回款未齐不可特批完成
        "dashboard:view",
        "lead:view", "customer:view", "customer:manage",
        "opportunity:view", "opportunity:manage",
        "contract:view", "contract:complete",
        "payment:view", "payment:claim",
        "knowledge:view",
    ]),
    ("交付负责人", "delivery_lead", "department", [
        "dashboard:view", "approval:center",
        "customer:view", "contract:view",
        "project:view", "project:manage",
        "project:accept_submit", "project:accept_approve",
        "project:finance_submit", "project:complete",
        "timesheet:view", "timesheet:approve",
        "ticket:view", "schedule:view", "knowledge:view",
    ]),
    ("运营", "operations", "department", [
        "dashboard:view", "approval:center",
        "customer:view", "project:view", "ticket:view", "timesheet:view", "schedule:view", "asset:view",
        "knowledge:view",
    ]),
    ("开发", "developer", "personal", [
        "dashboard:view", "project:view", "timesheet:view", "ticket:view", "knowledge:view",
    ]),
    ("讲师主播", "instructor", "personal", [
        "dashboard:view", "project:view", "timesheet:view", "schedule:view", "knowledge:view",
    ]),
    ("财务", "finance", "company", [
        "lead:view", "approval:center",
        "contract:view", "contract:approve", "contract:complete", "contract:force_complete",
        "payment:view", "payment:manage", "payment:claim",
        "payment:confirm", "payment:allocate", "payment:refund",
        "project:view", "project:finance_approve",
        "customer:view",
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
    ("品宣专员", "brand", "department", [
        "lead:view", "knowledge:view", "schedule:view",
    ]),
    ("综合管理主管", "hr_supervisor", "company", [
        "lead:view", "approval:center", "org:view", "okr:view", "ticket:view", "schedule:view", "knowledge:view",
    ]),
    ("资产管理员", "asset_admin", "company", [
        "lead:view", "approval:center", "asset:view", "knowledge:view",
    ]),
]


def seed(db: Session) -> None:
    # 1) 根部门
    root = db.query(Department).filter(Department.code == "ROOT").first()
    if not root:
        root = Department(name="总公司", code="ROOT", description="根部门")
        db.add(root)
        db.flush()
        print(f"[seed] 创建部门: {root.name}")

    # 2) 权限
    perm_map: dict[str, Permission] = {}
    for name, code, module in PERMISSIONS:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if not perm:
            perm = Permission(name=name, code=code, module=module)
            db.add(perm)
            db.flush()
            print(f"[seed] 创建权限: {code}")
        perm_map[code] = perm

    # 3) 角色
    for name, code, data_scope, perm_codes in ROLES:
        role = db.query(Role).filter(Role.code == code).first()
        if not role:
            role = Role(name=name, code=code, data_scope=data_scope, description=name)
            db.add(role)
            db.flush()
            print(f"[seed] 创建角色: {name}")

        if perm_codes == ["*"]:
            role.permissions = list(perm_map.values())
        else:
            role.permissions = [perm_map[c] for c in perm_codes if c in perm_map]

    # 4) 管理员
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin_role = db.query(Role).filter(Role.code == "admin").first()
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            real_name="系统管理员",
            department_id=root.id,
            is_active=True,
        )
        if admin_role:
            admin.roles.append(admin_role)
        db.add(admin)
        print("[seed] 创建管理员账号 admin / admin123")
    else:
        print("[seed] 管理员已存在，跳过")

    db.commit()
    print("[seed] 完成")


def main() -> None:
    # 开发期兜底建表（正式流程请用 alembic upgrade head）
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
