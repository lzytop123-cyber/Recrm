"""通用审批流引擎：审批实例（ApprovalInstance）+ 节点任务（ApprovalTask）。

对齐《审批流程配置表》通用规则：
- 逐级串行（G-03），节点按 seq 递增激活
- 按角色解析审批人（RISK-2：链路配角色不写死人名）
- 会签节点（A-07/AP-21）：同一 seq 下多个任务，全部通过才进入下一节点
- 禁止自审（G-08）：发起人不能处理自己单据的节点
- 撤回留痕（G-05）、驳回退回发起人（G-06）

规则本身存 approval_rules.nodes_json / conditions_json（见 services/approval_flow.py）。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# —— 审批实例状态 ——
INSTANCE_PENDING = "pending"  # 审批中
INSTANCE_APPROVED = "approved"  # 全部通过
INSTANCE_REJECTED = "rejected"  # 被驳回
INSTANCE_WITHDRAWN = "withdrawn"  # 发起人撤回
INSTANCE_CANCELLED = "cancelled"  # 系统取消
INSTANCE_BLOCKED = "blocked"  # 无可用审批人，挂起等待配置

INSTANCE_STATUSES = {
    INSTANCE_PENDING,
    INSTANCE_APPROVED,
    INSTANCE_REJECTED,
    INSTANCE_WITHDRAWN,
    INSTANCE_CANCELLED,
    INSTANCE_BLOCKED,
}
INSTANCE_OPEN_STATUSES = {INSTANCE_PENDING, INSTANCE_BLOCKED}

# —— 节点任务状态 ——
TASK_WAITING = "waiting"  # 未轮到
TASK_ACTIVE = "active"  # 当前待处理
TASK_APPROVED = "approved"
TASK_REJECTED = "rejected"
TASK_SKIPPED = "skipped"  # 自审跳过 / 无候选人跳过

# —— 节点类型 ——
NODE_APPROVE = "approve"  # 普通审批节点（按角色）
NODE_EXECUTE = "execute"  # 执行节点（如财务负责人执行退款），语义等同审批
NODE_COUNTERSIGN = "countersign"  # 会签节点（同 seq 多任务需全部通过）
NODE_ASSIGNEE = "assignee"  # 指定人确认节点（某个具体的人，如工单执行人/排期本人/验收发起人）

ACTOR_NODE_TYPES = {NODE_APPROVE, NODE_EXECUTE, NODE_COUNTERSIGN, NODE_ASSIGNEE}


class ApprovalInstance(Base):
    """一次审批发起，绑定一条已发布规则与一个业务实体。"""

    __tablename__ = "approval_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True, comment="审批单号")

    rule_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("approval_rules.id"), nullable=True, comment="命中的审批规则"
    )
    rule_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="规则编码快照，如 AP-18")
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="业务类型")
    biz_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="业务实体 id")

    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="审批标题")
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="摘要")
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True, comment="金额（用于分级路由展示）")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=INSTANCE_PENDING, index=True
    )
    current_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="当前激活节点序号")

    initiator_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    initiator_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="发起人姓名快照")
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True
    )

    cc_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="抄送角色码 JSON 快照")
    context_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="发起时业务事实快照 JSON")
    deep_link: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="跳转业务详情")
    reject_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tasks: Mapped[list["ApprovalTask"]] = relationship(
        "ApprovalTask",
        back_populates="instance",
        cascade="all, delete-orphan",
        order_by="ApprovalTask.seq, ApprovalTask.id",
    )


class ApprovalTask(Base):
    """审批实例下的一个节点任务；会签时同一 seq 会有多条。"""

    __tablename__ = "approval_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("approval_instances.id"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="节点序号，从 1 起")
    name: Mapped[str] = mapped_column(String(120), nullable=False, comment="节点名称")
    node_type: Mapped[str] = mapped_column(String(20), nullable=False, default=NODE_APPROVE)
    group_label: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, comment="会签分组名")
    roles_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="可处理角色码 JSON 列表")
    assignee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="指定人节点的处理人（assignee 类型）"
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TASK_WAITING, index=True
    )
    acted_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    acted_by_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    acted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="审批意见（G-10 必填）")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    instance: Mapped["ApprovalInstance"] = relationship("ApprovalInstance", back_populates="tasks")
