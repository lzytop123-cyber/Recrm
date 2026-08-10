"""
售后：项目交付表 + 里程碑 + 任务。
对齐 PRD 4.1 / 原型「项目交付」工作台。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 项目状态（PRD：立项 → 计划中 → 执行中 → 验收中 → 已验收 → 已完成/已终止）
PROJECT_STATUS_INITIATING = "initiating"
PROJECT_STATUS_PLANNING = "planning"
PROJECT_STATUS_EXECUTING = "executing"
PROJECT_STATUS_ACCEPTING = "accepting"
PROJECT_STATUS_ACCEPTED = "accepted"
PROJECT_STATUS_COMPLETED = "completed"
PROJECT_STATUS_TERMINATED = "terminated"

PROJECT_STATUSES = {
    PROJECT_STATUS_INITIATING,
    PROJECT_STATUS_PLANNING,
    PROJECT_STATUS_EXECUTING,
    PROJECT_STATUS_ACCEPTING,
    PROJECT_STATUS_ACCEPTED,
    PROJECT_STATUS_COMPLETED,
    PROJECT_STATUS_TERMINATED,
}

PROJECT_STATUS_LABEL = {
    PROJECT_STATUS_INITIATING: "立项",
    PROJECT_STATUS_PLANNING: "计划中",
    PROJECT_STATUS_EXECUTING: "执行中",
    PROJECT_STATUS_ACCEPTING: "验收中",
    PROJECT_STATUS_ACCEPTED: "已验收",
    PROJECT_STATUS_COMPLETED: "已完成",
    PROJECT_STATUS_TERMINATED: "已终止",
}

PROJECT_TYPES = {
    "ai_product": "AI产品销售",
    "ai_custom": "AI定制开发",
    "media_ops": "自媒体代运营",
    "other": "其他",
}

MILESTONE_STATUS_PENDING = "pending"
MILESTONE_STATUS_DOING = "doing"
MILESTONE_STATUS_DONE = "done"

MILESTONE_STATUSES = {
    MILESTONE_STATUS_PENDING,
    MILESTONE_STATUS_DOING,
    MILESTONE_STATUS_DONE,
}

EVIDENCE_STATUS_NONE = "none"
EVIDENCE_STATUS_PENDING = "pending"
EVIDENCE_STATUS_CONFIRMED = "confirmed"
EVIDENCE_STATUS_REJECTED = "rejected"
EVIDENCE_STATUSES = {
    EVIDENCE_STATUS_NONE,
    EVIDENCE_STATUS_PENDING,
    EVIDENCE_STATUS_CONFIRMED,
    EVIDENCE_STATUS_REJECTED,
}

TASK_STATUS_PENDING = "pending"
TASK_STATUS_DOING = "doing"
TASK_STATUS_DONE = "done"

TASK_STATUSES = {
    TASK_STATUS_PENDING,
    TASK_STATUS_DOING,
    TASK_STATUS_DONE,
}

TASK_STATUS_LABEL = {
    TASK_STATUS_PENDING: "待排期",
    TASK_STATUS_DOING: "进行中",
    TASK_STATUS_DONE: "已完成",
}

ACCEPTANCE_RESULTS = {"pass", "conditional", "fail"}

ACCEPTANCE_APPROVAL_NONE = "none"
ACCEPTANCE_APPROVAL_PENDING = "pending"
ACCEPTANCE_APPROVAL_APPROVED = "approved"
ACCEPTANCE_APPROVAL_REJECTED = "rejected"

PAYMENT_DEFER_NONE = "none"
PAYMENT_DEFER_PENDING = "pending"
PAYMENT_DEFER_APPROVED = "approved"
PAYMENT_DEFER_REJECTED = "rejected"
ACCEPTANCE_APPROVAL_STATUSES = {
    ACCEPTANCE_APPROVAL_NONE,
    ACCEPTANCE_APPROVAL_PENDING,
    ACCEPTANCE_APPROVAL_APPROVED,
    ACCEPTANCE_APPROVAL_REJECTED,
}

FINANCE_CHECK_NONE = "none"
FINANCE_CHECK_PENDING = "pending"
FINANCE_CHECK_APPROVED = "approved"
FINANCE_CHECK_REJECTED = "rejected"
FINANCE_CHECK_STATUSES = {
    FINANCE_CHECK_NONE,
    FINANCE_CHECK_PENDING,
    FINANCE_CHECK_APPROVED,
    FINANCE_CHECK_REJECTED,
}


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, comment="项目编号"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="项目名称")
    contract_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("contracts.id"), nullable=True, index=True, comment="关联合同"
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("customers.id"), nullable=True, index=True, comment="客户"
    )
    project_type: Mapped[str] = mapped_column(
        String(30), default="other", comment="ai_product/ai_custom/media_ops/other"
    )
    status: Mapped[str] = mapped_column(
        String(30), default=PROJECT_STATUS_INITIATING, index=True, comment="项目状态"
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="进度 0-100")
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True, comment="项目负责人"
    )
    creator_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="创建人"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, comment="所属部门"
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, comment="计划开始")
    end_date: Mapped[Optional[date]] = mapped_column(Date, comment="计划结束")
    actual_end_date: Mapped[Optional[date]] = mapped_column(Date, comment="实际结束")
    scope_desc: Mapped[Optional[str]] = mapped_column(Text, comment="交付范围")
    terminate_reason: Mapped[Optional[str]] = mapped_column(String(500), comment="终止原因")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")

    # 立项前确认（商务交接检查项）
    payment_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="收款条件已核验"
    )
    payment_deferred: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        comment="无到款立项（先干活后付款）",
    )
    payment_deferred_reason: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="无到款立项原因"
    )
    payment_defer_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PAYMENT_DEFER_NONE,
        server_default=PAYMENT_DEFER_NONE,
        index=True,
        comment="none/pending/approved/rejected",
    )
    payment_defer_submitted_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    payment_defer_submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_defer_approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    payment_defer_approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_defer_reject_reason: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    handoff_complete: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="线索交接已完整"
    )
    contact_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="客户联系人已确认"
    )
    business_owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="商务责任人"
    )
    baseline_version: Mapped[Optional[str]] = mapped_column(
        String(30), default="V1", comment="计划基线版本"
    )

    # 内部验收
    acceptance_result: Mapped[Optional[str]] = mapped_column(
        String(20), comment="pass/conditional/fail"
    )
    accepted_at: Mapped[Optional[date]] = mapped_column(Date, comment="验收日期")
    acceptance_method: Mapped[Optional[str]] = mapped_column(String(50), comment="验收方式")
    acceptance_owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="验收负责人"
    )
    acceptance_conclusion: Mapped[Optional[str]] = mapped_column(Text, comment="验收结论")
    leftover_summary: Mapped[Optional[str]] = mapped_column(Text, comment="遗留问题摘要")
    acceptance_approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ACCEPTANCE_APPROVAL_NONE,
        server_default=ACCEPTANCE_APPROVAL_NONE,
        index=True,
        comment="none/pending/approved/rejected",
    )
    acceptance_submitted_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    acceptance_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    acceptance_approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    acceptance_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    acceptance_reject_reason: Mapped[Optional[str]] = mapped_column(String(500))
    acceptance_attachment: Mapped[Optional[str]] = mapped_column(
        String(255), comment="验收附件文件名"
    )
    acceptance_attachment_path: Mapped[Optional[str]] = mapped_column(
        String(500), comment="验收附件存储路径"
    )
    finance_check_passed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="财务核对已通过"
    )
    finance_check_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=FINANCE_CHECK_NONE,
        server_default=FINANCE_CHECK_NONE,
        index=True,
        comment="none/pending/approved/rejected",
    )
    finance_check_submitted_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    finance_check_submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    finance_check_approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    finance_check_approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    finance_check_reject_reason: Mapped[Optional[str]] = mapped_column(String(500))
    leftover_closed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="遗留问题已关闭"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    milestones: Mapped[list["ProjectMilestone"]] = relationship(
        "ProjectMilestone",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectMilestone.sort_order",
    )
    tasks: Mapped[list["ProjectTask"]] = relationship(
        "ProjectTask",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    resource_needs: Mapped[list["ProjectResourceNeed"]] = relationship(
        "ProjectResourceNeed",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectResourceNeed.id",
    )


RESOURCE_NEED_PENDING = "pending"
RESOURCE_NEED_ACCEPTED = "accepted"
RESOURCE_NEED_REJECTED = "rejected"
RESOURCE_NEED_STATUSES = {RESOURCE_NEED_PENDING, RESOURCE_NEED_ACCEPTED, RESOURCE_NEED_REJECTED}

SCHEDULE_CHECK_PENDING = "pending"
SCHEDULE_CHECK_CLEAR = "clear"
SCHEDULE_CHECK_CONFLICT = "conflict"
SCHEDULE_CHECK_STATUSES = {SCHEDULE_CHECK_PENDING, SCHEDULE_CHECK_CLEAR, SCHEDULE_CHECK_CONFLICT}


class ProjectResourceNeed(Base):
    """立项资源需求：部门确认成员、投入与排期。"""

    __tablename__ = "project_resource_needs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True
    )
    role_name: Mapped[str] = mapped_column(String(80), nullable=False, comment="需求角色")
    department_name: Mapped[str] = mapped_column(String(80), nullable=False, comment="涉及部门")
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True
    )
    suggested_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True, comment="建议成员"
    )
    confirmed_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="确认后成员"
    )
    planned_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=0, comment="计划投入小时"
    )
    status: Mapped[str] = mapped_column(
        String(30), default=RESOURCE_NEED_PENDING, index=True, comment="pending/accepted/rejected"
    )
    schedule_status: Mapped[str] = mapped_column(
        String(30),
        default=SCHEDULE_CHECK_PENDING,
        comment="pending/clear/conflict",
    )
    note: Mapped[Optional[str]] = mapped_column(Text, comment="确认说明")
    confirmed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="resource_needs")


class ProjectMilestone(Base):
    """项目里程碑（PRD 4.1.5）。"""

    __tablename__ = "project_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date, comment="计划开始")
    deadline: Mapped[Optional[date]] = mapped_column(Date, comment="计划结束")
    actual_date: Mapped[Optional[date]] = mapped_column(Date, comment="实际/预测完成日")
    role: Mapped[Optional[str]] = mapped_column(String(50), comment="责任角色")
    deliverable: Mapped[Optional[str]] = mapped_column(String(200), comment="必交成果")
    evidence: Mapped[Optional[str]] = mapped_column(Text, comment="完成证据说明")
    evidence_link: Mapped[Optional[str]] = mapped_column(String(500), comment="完成证据链接")
    evidence_attachment: Mapped[Optional[str]] = mapped_column(
        String(255), comment="完成证据附件文件名"
    )
    evidence_attachment_path: Mapped[Optional[str]] = mapped_column(
        String(500), comment="完成证据附件存储路径"
    )
    evidence_status: Mapped[str] = mapped_column(
        String(30), default=EVIDENCE_STATUS_NONE, server_default="none", comment="none/pending/confirmed/rejected"
    )
    evidence_confirmed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="证据确认人"
    )
    evidence_confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="证据确认时间"
    )
    evidence_reject_reason: Mapped[Optional[str]] = mapped_column(String(200), comment="证据驳回原因")
    status: Mapped[str] = mapped_column(String(30), default=MILESTONE_STATUS_PENDING)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="milestones")


class ProjectTask(Base):
    """项目任务与计划工时。"""

    __tablename__ = "project_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="任务编号")
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True
    )
    milestone_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("project_milestones.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    criteria: Mapped[Optional[str]] = mapped_column(Text, comment="完成标准")
    assignee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, comment="计划开始")
    due_date: Mapped[Optional[date]] = mapped_column(Date, index=True, comment="计划结束")
    planned_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0)
    actual_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0)
    status: Mapped[str] = mapped_column(
        String(30), default=TASK_STATUS_PENDING, index=True, comment="pending/doing/done"
    )
    ticket_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    creator_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
