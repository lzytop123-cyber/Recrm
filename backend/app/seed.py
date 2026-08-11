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

# 预置权限：(name, code, module, description)
# name/description 用于系统管理「权限目录」；入口 ≠ 业务下拉（下拉走 /directory）
PERMISSIONS = [
    ("经营总览（入口）", "dashboard:view", "dashboard", "侧栏「经营总览」；与选人/挂接无关"),
    ("审批中心（入口）", "approval:center", "approval", "侧栏「审批中心」与待办中的审批聚合；具体审批另需合同/项目等审批码"),
    ("线索查看/录入", "lead:view", "lead", "录入与查看线索；销售中心或线索录入页入口"),
    ("线索池分配", "lead:manage", "lead", "分配待分配线索池；不是线索录入本身"),
    ("客户查看", "customer:view", "customer", "查看客户；业务下拉选客户不依赖此码"),
    ("客户管理", "customer:manage", "customer", "新建/编辑客户等写操作"),
    ("商机查看", "opportunity:view", "opportunity", "查看商机"),
    ("商机管理", "opportunity:manage", "opportunity", "新建/推进商机等写操作"),
    ("合同查看（入口）", "contract:view", "contract", "侧栏「合同回款」；挂接选合同走 /directory"),
    ("合同管理", "contract:manage", "contract", "合同超级写权限（含部分审批/完成兜底）"),
    ("合同审批", "contract:approve", "contract", "审批通过/驳回合同"),
    ("合同完成", "contract:complete", "contract", "正常完成合同"),
    ("收款查看", "payment:view", "payment", "查看收款/财务工作台"),
    ("收款管理", "payment:manage", "payment", "收款写操作总码（可覆盖认领/复核等）"),
    ("到款认领", "payment:claim", "payment", "提交到款认领"),
    ("到账复核", "payment:confirm", "payment", "复核到账"),
    ("收款核销", "payment:allocate", "payment", "执行核销"),
    ("退款管理", "payment:refund", "payment", "管理退款"),
    ("项目管理（入口）", "project:view", "project", "侧栏「项目管理」；工单/排期挂项目走 /directory"),
    ("项目写操作", "project:manage", "project", "立项/计划/成员等项目管理写权限"),
    ("发起项目验收", "project:accept_submit", "project", "发起内部验收"),
    ("审批项目验收", "project:accept_approve", "project", "审批内部验收"),
    ("提交财务核对", "project:finance_submit", "project", "提交财务核对"),
    ("审批财务核对", "project:finance_approve", "project", "审批财务核对"),
    ("项目结项", "project:complete", "project", "项目结项"),
    ("目标绩效查看", "okr:view", "okr", "OKR/绩效（二期侧栏隐藏）"),
    ("工时查看", "timesheet:view", "timesheet", "查看/填报工时；挂项目走 /directory"),
    ("工时审批", "timesheet:approve", "timesheet", "审批工时"),
    ("协作工单（使用）", "ticket:view", "ticket", "工单列表与处理；销售默认可接单但不进侧栏全量菜单"),
    ("排期会议（使用）", "schedule:view", "schedule", "排期申请与确认；选人走排期/目录接口"),
    ("固定资产（入口）", "asset:view", "asset", "侧栏「固定资产」；可申请借用"),
    ("固定资产管理", "asset:manage", "asset", "入库/审批借用/盘点/处置等资产管理"),
    ("知识库查看", "knowledge:view", "knowledge", "查看知识库（暂无独立侧栏）"),
    ("知识库管理", "knowledge:manage", "knowledge", "维护知识源与空间"),
    ("员工管理（入口）", "org:view", "org", "侧栏「员工管理」与档案；业务选人勿勾此码，用 /directory"),
    ("员工管理（维护）", "org:manage", "org", "维护部门/员工/重置密码"),
    ("组织飞书同步", "org:sync", "org", "飞书通讯录/考勤同步"),
    ("系统管理（入口）", "system:view", "system", "侧栏「系统管理」只读查看"),
    ("系统管理（维护）", "system:manage", "system", "改角色权限、账号启停、配置与字典"),
]

# 预置角色：(name, code, data_scope, permission_codes)
# data_scope: company / department / personal
ROLES = [
    ("系统管理员", "admin", "company", ["*"]),  # * 表示全部，种子时绑定全部权限
    ("董事会", "board", "company", [
        "dashboard:view", "approval:center",
        "lead:view", "customer:view", "opportunity:view",
        "contract:view", "contract:approve", "contract:complete", "payment:view",
        "project:view", "project:accept_approve", "project:complete",
        "ticket:view", "schedule:view", "org:view", "knowledge:view",
    ]),
    ("管理层", "executive", "company", [
        "dashboard:view", "approval:center",
        "lead:view", "lead:manage", "customer:view", "opportunity:view",
        "contract:view", "contract:approve", "contract:complete",
        "payment:view",
        "project:view", "project:manage",
        "project:accept_submit", "project:accept_approve",
        "project:finance_submit", "project:complete",
        "okr:view", "timesheet:view", "timesheet:approve",
        "ticket:view", "schedule:view", "asset:view", "asset:manage",
        "knowledge:view", "org:view",
    ]),
    ("中层管理", "middle_manager", "department", [
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
    ("普通员工", "employee", "personal", [
        "lead:view", "okr:view", "timesheet:view", "ticket:view", "schedule:view", "asset:view",
        "knowledge:view",
    ]),
    ("销售", "sales", "department", [
        # 无 lead:manage：待分配线索池仅管理层/中层可看
        # ticket:view：待办可接单；侧栏「协作工单」对纯销售隐藏（见 menu.py）
        "dashboard:view",
        "lead:view", "customer:view", "customer:manage",
        "opportunity:view", "opportunity:manage",
        "contract:view", "contract:complete",
        "payment:view", "payment:claim",
        "ticket:view",
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
        "customer:view", "project:view", "ticket:view", "timesheet:view", "schedule:view",
        "asset:view", "asset:manage",
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
        "contract:view", "contract:approve", "contract:complete",
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
        "lead:view", "approval:center", "asset:view", "asset:manage", "knowledge:view",
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

    # 2) 权限（已存在则同步名称/说明）
    perm_map: dict[str, Permission] = {}
    for name, code, module, description in PERMISSIONS:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if not perm:
            perm = Permission(name=name, code=code, module=module, description=description)
            db.add(perm)
            db.flush()
            print(f"[seed] 创建权限: {code}")
        else:
            changed = False
            if perm.name != name:
                perm.name = name
                changed = True
            if perm.module != module:
                perm.module = module
                changed = True
            if (perm.description or "") != description:
                perm.description = description
                changed = True
            if changed:
                print(f"[seed] 更新权限: {code}")
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
        db.add(admin)
        db.flush()
        if admin_role:
            admin.roles.append(admin_role)
        print("[seed] 创建管理员: admin / admin123")

    db.commit()
    print("[seed] 完成")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
