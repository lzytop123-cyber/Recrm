"""
初始化种子数据：部门、权限、预置角色、管理员账号。
用法（在 backend 目录、已激活 venv）：
  python -m app.seed
默认管理员：admin / admin123
"""
import json

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import SessionLocal, engine
from app.models.approval_rule import RULE_STATUS_PUBLISHED, ApprovalRule
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

from app.seed_roles_v2 import bind_demo_approval_roles, migrate_user_roles_to_v2, seed_roles_v2

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
    ("目标绩效查看", "okr:view", "okr", "查看目标 OKR"),
    ("考核查看", "kpi:view", "kpi", "查看本人及直属下属的考核批次"),
    ("绩效模板管理", "kpi:template:manage", "kpi", "HR 建基础模板、审批部门模板、归档周期"),
    ("绩效模板编写", "kpi:template:write", "kpi", "部门 fork/编辑本部门绩效模板"),
    ("绩效周期管理", "kpi:cycle:manage", "kpi", "建周期、批量生成考核单、归档"),
    ("工时查看", "timesheet:view", "timesheet", "查看/填报工时；挂项目走 /directory"),
    ("工时审批", "timesheet:approve", "timesheet", "审批工时"),
    ("协作工单（使用）", "ticket:view", "ticket", "工单列表与处理；销售默认可接单但不进侧栏全量菜单"),
    ("排期会议（使用）", "schedule:view", "schedule", "排期申请与确认；选人走排期/目录接口"),
    ("排期管理", "schedule:manage", "schedule", "新建/编辑排期；未勾选仅能查看排期表"),
    ("固定资产（入口）", "asset:view", "asset", "侧栏「固定资产」；可申请借用"),
    ("固定资产管理", "asset:manage", "asset", "入库/审批借用/盘点/处置等资产管理"),
    ("知识库查看", "knowledge:view", "knowledge", "侧栏「知识库」提问与查阅"),
    ("知识库管理", "knowledge:manage", "knowledge", "接入飞书文档、录入条目"),
    ("员工管理（入口）", "org:view", "org", "侧栏「员工管理」与档案；业务选人勿勾此码，用 /directory"),
    ("员工管理（维护）", "org:manage", "org", "维护部门/员工/重置密码"),
    ("组织飞书同步", "org:sync", "org", "飞书通讯录/考勤同步"),
    ("系统管理（入口）", "system:view", "system", "侧栏「系统管理」只读查看"),
    ("系统管理（维护）", "system:manage", "system", "改角色权限、账号启停、配置与字典"),
]

# 预置审批流规则（《审批流程配置表》v2，角色码对齐 15 岗）。
APPROVAL_RULES = [
    {
        "code": "AP-18",
        "name": "退款审批",
        "biz_type": "refund",
        "timeout_hours": 48,
        "conditions": None,
        "nodes": {
            "nodes": [
                {"name": "总经理审批", "type": "approve", "roles": ["gm", "chairman"]},
                {"name": "财务负责人执行退款", "type": "execute", "roles": ["finance"]},
            ],
            "cc": ["chairman", "finance"],
        },
        "remark": "AP-18 定版(2026-08-23)：财务专员提交 → 总经理审批 → 财务负责人执行；抄送董事长、财务；高风险不代理。",
    },
    {
        "code": "AP-01",
        "name": "合同审批·小额(<1万元)",
        "biz_type": "contract",
        "timeout_hours": 72,
        "conditions": {"when": {"field": "amount", "op": "lt", "value": 10000}},
        "nodes": {
            "nodes": [
                {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
                {"name": "法务审批", "type": "approve", "roles": ["legal"]},
                {"name": "财务审批", "type": "approve", "roles": ["finance"]},
                {"name": "中心负责人终审", "type": "approve", "roles": ["center_lead"]},
            ],
            "cc": ["gm"],
        },
        "remark": "AP-01：金额<1万元走本流程；高层节点知会。法务节点待 legal 角色建立后生效。",
    },
    {
        "code": "AP-02",
        "name": "合同审批·大额(≥1万元)",
        "biz_type": "contract",
        "timeout_hours": 72,
        "conditions": {"when": {"field": "amount", "op": "gte", "value": 10000}},
        "nodes": {
            "nodes": [
                {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
                {"name": "法务审批", "type": "approve", "roles": ["legal"]},
                {"name": "财务审批", "type": "approve", "roles": ["finance"]},
                {"name": "中心负责人审批", "type": "approve", "roles": ["center_lead"]},
                {"name": "总经理终审", "type": "approve", "roles": ["gm", "chairman"]},
            ],
            "cc": ["chairman"],
        },
        "remark": "AP-02：金额≥1万元走本流程，较 AP-01 多一级总经理终审；抄送董事长。",
    },
    {
        "code": "AP-21",
        "name": "资产赔偿审批(会签)",
        "biz_type": "asset_compensation",
        "timeout_hours": 72,
        "conditions": None,
        "nodes": {
            "nodes": [
                {
                    "name": "财务 + 行政主管会签",
                    "type": "countersign",
                    "groups": [
                        {"label": "财务", "roles": ["finance"]},
                        {"label": "行政主管", "roles": ["004"]},
                    ],
                }
            ],
            "cc": [],
        },
        "remark": "AP-21：资产遗失/损坏赔偿，财务+行政主管会签(串行规则的例外)，两方均通过才生效。",
    },
    # —— 合同类 ——
    {
        "code": "AP-03", "name": "合同签署与激活", "biz_type": "contract_activate",
        "timeout_hours": 48, "conditions": None,
        "nodes": {"nodes": [
            {"name": "财务确认激活", "type": "execute", "roles": ["finance"]},
        ], "cc": []},
        "remark": "AP-03：合同审批通过并上传双章合同图片+付款截图后，财务确认激活。",
    },
    {
        "code": "AP-04-A", "name": "合同修改重审·小额(<1万元)", "biz_type": "contract_modify",
        "timeout_hours": 72,
        "conditions": {"when": {"field": "amount", "op": "lt", "value": 10000}},
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "法务审批", "type": "approve", "roles": ["legal"]},
            {"name": "财务审批", "type": "approve", "roles": ["finance"]},
            {"name": "中心负责人终审", "type": "approve", "roles": ["center_lead"]},
        ], "cc": ["gm"]},
        "remark": "AP-04：已生效合同修改金额/条款，重新走 AP-01 链路；通过后新版本覆盖旧版。",
    },
    {
        "code": "AP-04-B", "name": "合同修改重审·大额(≥1万元)", "biz_type": "contract_modify",
        "timeout_hours": 72,
        "conditions": {"when": {"field": "amount", "op": "gte", "value": 10000}},
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "法务审批", "type": "approve", "roles": ["legal"]},
            {"name": "财务审批", "type": "approve", "roles": ["finance"]},
            {"name": "中心负责人审批", "type": "approve", "roles": ["center_lead"]},
            {"name": "总经理终审", "type": "approve", "roles": ["gm", "chairman"]},
        ], "cc": ["chairman"]},
        "remark": "AP-04：已生效合同修改金额/条款，重新走 AP-02 链路；通过后新版本覆盖旧版。",
    },
    {
        "code": "AP-05", "name": "合同终止审批", "biz_type": "contract_terminate",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "财务审批", "type": "approve", "roles": ["finance"]},
            {"name": "中心负责人审批", "type": "approve", "roles": ["center_lead"]},
            {"name": "总经理终审", "type": "approve", "roles": ["gm", "chairman"]},
        ], "cc": ["chairman"]},
        "remark": "AP-05：独立流程，终审通过后合同状态=终止；抄送董事长。",
    },
    # —— 立项/项目类 ——
    {
        "code": "AP-06", "name": "无合同立项特批", "biz_type": "project_no_contract",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "总经理审批", "type": "assignee", "assignee_id": 78},
        ], "cc": ["chairman"]},
        "remark": "AP-06：无合同/未到账先立项；部门负责人→总经理(刘鹏吉)；抄送董事长(张东霞)。",
    },
    {
        "code": "AP-07", "name": "项目立项审批", "biz_type": "project_initiation",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "中心负责人终审", "type": "approve", "roles": ["center_lead"]},
        ], "cc": ["chairman"]},
        "remark": "AP-07：审批目标/范围/预算/负责人/周期/资源/付款/交付标准；抄送董事会。",
    },
    {
        "code": "AP-08", "name": "项目交接与基线确认", "biz_type": "project_handover",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "中心负责人确认交接", "type": "approve", "roles": ["center_lead"]},
        ], "cc": []},
        "remark": "AP-08：中心负责人确认交接后由项目负责人制定基线；基线重大变更走 AP-07。",
    },
    {
        "code": "AP-10", "name": "项目结项归档", "biz_type": "project_settlement",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "中心负责人归档核验", "type": "approve", "roles": ["center_lead"]},
        ], "cc": []},
        "remark": "AP-10：归档核验(合同/收款/工单验收/工时/验收报告齐备)，不设财务检查环节。",
    },
    {
        "code": "AP-11", "name": "项目终止/重启", "biz_type": "project_terminate",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "中心负责人审批", "type": "approve", "roles": ["center_lead"]},
            {"name": "总经理终审", "type": "approve", "roles": ["gm", "chairman"]},
        ], "cc": ["chairman"]},
        "remark": "AP-11：终止/延期/范围变更/重启均走本流程，通过后重新立项；抄送董事长。",
    },
    {
        "code": "AP-09", "name": "项目验收", "biz_type": "project_acceptance",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "项目发起人验收", "type": "assignee", "assignee_key": "acceptor_id"},
        ], "cc": ["dept_head"]},
        "remark": "AP-09：项目负责人发起→项目发起人本人验收(指定人节点，发起时传 acceptor_id)。",
    },
    # —— 工时 ——
    {
        "code": "AP-15", "name": "工时月度审批", "biz_type": "timesheet",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
        ], "cc": []},
        "remark": "AP-15：工单/排期完成自动提交，部门负责人按月批量审批。",
    },
    # —— 收款 ——
    {
        "code": "AP-16", "name": "收款到账确认", "biz_type": "receipt",
        "timeout_hours": 48, "conditions": None,
        "nodes": {"nodes": [
            {"name": "财务确认到账", "type": "execute", "roles": ["finance"]},
        ], "cc": []},
        "remark": "AP-16：销售上传付款截图+合同，财务凭银行流水/回单确认到账并核销。",
    },
    {
        "code": "AP-17", "name": "收款金额差异审批", "biz_type": "receipt_diff",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "财务审批", "type": "approve", "roles": ["finance"]},
            {"name": "总经理终审", "type": "approve", "roles": ["gm", "chairman"]},
        ], "cc": ["finance"]},
        "remark": "AP-17：实收≠应收时按差异金额核销；抄送财务。",
    },
    # —— 资产 ——
    {
        "code": "AP-19", "name": "资产领用审批", "biz_type": "asset_borrow",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "行政部负责人终审(出库)", "type": "execute", "roles": ["004"]},
        ], "cc": []},
        "remark": "AP-19：不分级；行政部负责人终审并执行出库登记领用人/时间。",
    },
    {
        "code": "AP-20", "name": "资产归还确认", "biz_type": "asset_return",
        "timeout_hours": 48, "conditions": None,
        "nodes": {"nodes": [
            {"name": "行政确认归还", "type": "execute", "roles": ["004"]},
        ], "cc": []},
        "remark": "AP-20：行政确认归还与资产状态、情况说明(无需分级审批)；归还后自动清空持有人。",
    },
    {
        "code": "AP-22-B", "name": "资产维修费审批·大额(≥1万)", "biz_type": "asset_maintenance",
        "timeout_hours": 72, "conditions": {"when": {"field": "amount", "op": "gte", "value": 10000}},
        "nodes": {"nodes": [
            {"name": "董事会审批", "type": "approve", "roles": ["chairman"]},
        ], "cc": []},
        "remark": "AP-22：维修费≥1万元走董事会审批。⚠️董事会执行人(董事长/总经理)待确认。",
    },
    {
        "code": "AP-22-A", "name": "资产维修费审批·中额(≥3千)", "biz_type": "asset_maintenance",
        "timeout_hours": 72, "conditions": {"when": {"field": "amount", "op": "gte", "value": 3000}},
        "nodes": {"nodes": [
            {"name": "财务审批", "type": "approve", "roles": ["finance"]},
        ], "cc": []},
        "remark": "AP-22：维修费≥3千且<1万走财务审批(＜3千无需审批，业务侧不发起流程)。",
    },
    {
        "code": "AP-23", "name": "资产盘点差异审批", "biz_type": "asset_inventory_diff",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "总经理终审", "type": "approve", "roles": ["gm", "chairman"]},
        ], "cc": ["finance"]},
        "remark": "AP-23：行政部负责人发起，总经理终审；抄送财务。",
    },
    # —— 组织 ——
    {
        "code": "AP-24", "name": "角色权限调整审批", "biz_type": "role_change",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "中心负责人审批", "type": "approve", "roles": ["center_lead"]},
            {"name": "总经理终审", "type": "approve", "roles": ["gm", "chairman"]},
        ], "cc": ["hr", "admin"]},
        "remark": "AP-24：部门负责人发起→中心负责人→总经理终审；抄送人力资源+系统管理员。",
    },
    # —— 工单/排期（含"指定人确认"节点） ——
    {
        "code": "AP-12", "name": "工单审批与接单", "biz_type": "ticket",
        "timeout_hours": 48, "conditions": None,
        "nodes": {"nodes": [
            {"name": "执行部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "执行人确认接单", "type": "assignee", "assignee_key": "executor_id"},
        ], "cc": []},
        "remark": "AP-12：部门负责人审批→执行人本人确认接单(不可代接)→自动排期。执行人为指定人节点。",
    },
    {
        "code": "AP-13", "name": "跨部门工单验收", "biz_type": "ticket_cross_accept",
        "timeout_hours": 48, "conditions": None,
        "nodes": {"nodes": [
            {"name": "发起人验收", "type": "assignee", "assignee_key": "creator_id"},
        ], "cc": []},
        "remark": "AP-13：跨部门工单执行完成后由发起人本人验收关闭(指定人节点)。",
    },
    {
        "code": "AP-14", "name": "排期确认", "biz_type": "schedule",
        "timeout_hours": 48, "conditions": None,
        "nodes": {"nodes": [
            {"name": "执行人确认排期", "type": "assignee", "assignee_key": "owner_id"},
        ], "cc": []},
        "remark": "AP-14：工单确认后自动创建排期，由执行人本人确认(指定人节点)；排期全公司可见。",
    },
    # —— 绩效 KPI ——
    {
        "code": "AP-KPI-01",
        "name": "KPI 考核评分流程",
        "biz_type": "kpi_review",
        "timeout_hours": 72,
        "conditions": None,
        "nodes": {"nodes": [
            {"name": "员工自评", "type": "assignee", "assignee_key": "user_id",
             "assignee_expr": "biz.user_id"},
            {"name": "上级评分", "type": "assignee", "assignee_key": "manager_id",
             "assignee_expr": "biz.user.manager_id"},
            {"name": "隔级复核", "type": "assignee", "assignee_key": "skip_manager_id",
             "assignee_expr": "biz.user.manager.manager_id"},
            {"name": "HR 归档", "type": "approve", "roles": ["hr"]},
        ], "cc": []},
        "remark": "AP-KPI-01：自评→直属上级→隔级→HR 归档。指定人由发起时 assignees 传入。",
    },
    {
        "code": "AP-KPI-02",
        "name": "绩效模板审批",
        "biz_type": "performance_template_review",
        "timeout_hours": 48,
        "conditions": None,
        "nodes": {"nodes": [
            {"name": "HR 审核", "type": "approve", "roles": ["hr"]},
        ], "cc": []},
        "remark": "AP-KPI-02：部门 fork 模板提交后由人力资源审核。",
    },
    {
        "code": "AP-KPI-03",
        "name": "KPI 申诉流程",
        "biz_type": "kpi_appeal",
        "timeout_hours": 96,
        "conditions": None,
        "nodes": {"nodes": [
            {"name": "隔级复核", "type": "assignee", "assignee_key": "skip_manager_id",
             "assignee_expr": "biz.assessment.user.manager.manager_id"},
            {"name": "HR 决议", "type": "approve", "roles": ["hr"]},
        ], "cc": []},
        "remark": "AP-KPI-03：员工申诉→隔级复核→HR 决议。",
    },
    {
        "code": "AP-HR-01", "name": "劳动合同续签", "biz_type": "labor_contract_renew",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "人力资源审批", "type": "approve", "roles": ["hr"]},
        ], "cc": []},
        "remark": "劳动合同续签：部门负责人→人力资源。",
    },
    {
        "code": "AP-HR-02", "name": "转岗审批", "biz_type": "hr_transfer",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "现部门负责人", "type": "approve", "roles": ["dept_head"]},
            {"name": "目标部门负责人", "type": "approve", "roles": ["dept_head"]},
            {"name": "人力资源审批", "type": "approve", "roles": ["hr"]},
        ], "cc": []},
        "remark": "转岗：双方部门负责人→人力资源。测试环境无规则时业务侧直接生效。",
    },
    {
        "code": "AP-HR-03", "name": "离职审批", "biz_type": "hr_resignation",
        "timeout_hours": 72, "conditions": None,
        "nodes": {"nodes": [
            {"name": "部门负责人审批", "type": "approve", "roles": ["dept_head"]},
            {"name": "人力资源审批", "type": "approve", "roles": ["hr"]},
        ], "cc": []},
        "remark": "离职审批通过后进入交接单。",
    },
    {
        "code": "AP-HR-04", "name": "假勤审批", "biz_type": "hr_leave",
        "timeout_hours": 48, "conditions": None,
        "nodes": {"nodes": [
            {"name": "人力资源审批", "type": "approve", "roles": ["hr"]},
        ], "cc": []},
        "remark": "请假/加班/补卡/外勤由人力资源审批。",
    },
]


def seed_approval_rules(db: Session) -> None:
    """写入/更新首批审批流规则并置为已发布（引擎按 biz_type + 条件命中）。"""
    for spec in APPROVAL_RULES:
        nodes_json = json.dumps(spec["nodes"], ensure_ascii=False)
        conditions_json = (
            json.dumps(spec["conditions"], ensure_ascii=False) if spec["conditions"] else None
        )
        rule = db.query(ApprovalRule).filter(ApprovalRule.code == spec["code"]).first()
        if not rule:
            rule = ApprovalRule(
                code=spec["code"],
                name=spec["name"],
                biz_type=spec["biz_type"],
                nodes_json=nodes_json,
                conditions_json=conditions_json,
                timeout_hours=spec["timeout_hours"],
                version=1,
                status=RULE_STATUS_PUBLISHED,
                remark=spec["remark"],
            )
            db.add(rule)
            print(f"[seed] 创建审批规则: {spec['code']} {spec['name']}")
        else:
            rule.name = spec["name"]
            rule.biz_type = spec["biz_type"]
            rule.nodes_json = nodes_json
            rule.conditions_json = conditions_json
            rule.timeout_hours = spec["timeout_hours"]
            rule.status = RULE_STATUS_PUBLISHED
            rule.remark = spec["remark"]
            print(f"[seed] 更新审批规则: {spec['code']} {spec['name']}")


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

    # 3) 角色 v2（15 岗 + admin）
    seed_roles_v2(db, perm_map)
    migrate_user_roles_to_v2(db)
    bind_demo_approval_roles(db)

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

    # 5) 审批流规则（首批：AP-18/AP-01/AP-02/AP-21）
    seed_approval_rules(db)

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
