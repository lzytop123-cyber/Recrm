"""
协作：工单流转。
对齐 PRD 5.1（创建、分派、受理、转派、完成、关闭、评价、重开、SLA 提醒与升级）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

TICKET_TYPE_COLLAB = "collaboration"
TICKET_TYPE_FEEDBACK = "feedback"
TICKET_TYPE_SERVICE = "service"
TICKET_TYPE_URGENT = "urgent"

TICKET_TYPES = {
    TICKET_TYPE_COLLAB,
    TICKET_TYPE_FEEDBACK,
    TICKET_TYPE_SERVICE,
    TICKET_TYPE_URGENT,
}

# 处理时限（小时）
TICKET_SLA_HOURS = {
    TICKET_TYPE_URGENT: 4,
    TICKET_TYPE_FEEDBACK: 24,
    TICKET_TYPE_SERVICE: 48,
    TICKET_TYPE_COLLAB: 72,
}

TICKET_STATUS_PENDING_ASSIGN = "pending_assign"
TICKET_STATUS_PENDING_ACCEPT = "pending_accept"
TICKET_STATUS_PROCESSING = "processing"
TICKET_STATUS_PENDING_CONFIRM = "pending_confirm"
TICKET_STATUS_COMPLETED = "completed"
TICKET_STATUS_CLOSED = "closed"

TICKET_STATUSES = {
    TICKET_STATUS_PENDING_ASSIGN,
    TICKET_STATUS_PENDING_ACCEPT,
    TICKET_STATUS_PROCESSING,
    TICKET_STATUS_PENDING_CONFIRM,
    TICKET_STATUS_COMPLETED,
    TICKET_STATUS_CLOSED,
}

TICKET_PRIORITY_LOW = "low"
TICKET_PRIORITY_NORMAL = "normal"
TICKET_PRIORITY_HIGH = "high"
TICKET_PRIORITY_URGENT = "urgent"

TICKET_PRIORITIES = {
    TICKET_PRIORITY_LOW,
    TICKET_PRIORITY_NORMAL,
    TICKET_PRIORITY_HIGH,
    TICKET_PRIORITY_URGENT,
}

# 关闭后允许重开的工作日数
TICKET_REOPEN_BUSINESS_DAYS = 3


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, comment="工单编号"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="标题")
    ticket_type: Mapped[str] = mapped_column(
        String(30), default=TICKET_TYPE_COLLAB, index=True, comment="工单类型"
    )
    priority: Mapped[str] = mapped_column(
        String(20), default=TICKET_PRIORITY_NORMAL, comment="优先级"
    )
    status: Mapped[str] = mapped_column(
        String(30), default=TICKET_STATUS_PENDING_ASSIGN, index=True, comment="状态"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="问题描述")
    creator_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="发起人"
    )
    assignee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True, comment="处理人"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, comment="处理部门"
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True, comment="关联项目"
    )
    task_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("project_tasks.id"), nullable=True, index=True, comment="关联项目任务"
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="处理截止时间"
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    result: Mapped[Optional[str]] = mapped_column(Text, comment="处理结果")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")
    satisfaction: Mapped[Optional[int]] = mapped_column(Integer, comment="满意度 1-5")
    satisfaction_comment: Mapped[Optional[str]] = mapped_column(Text, comment="评价备注")
    sla_remind_level: Mapped[int] = mapped_column(
        Integer, default=0, comment="SLA提醒级别 0/1=50%/2=80%"
    )
    escalated_level: Mapped[int] = mapped_column(
        Integer, default=0, comment="升级级别 0/1部门负责人/2业务负责人"
    )
    sla_paused_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), comment="SLA暂停起点（待确认期间）"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    records: Mapped[list["TicketRecord"]] = relationship(
        "TicketRecord",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketRecord.id",
    )


class TicketRecord(Base):
    """工单处理记录（评论/动作日志）。"""

    __tablename__ = "ticket_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="create/assign/accept/transfer/comment/complete/confirm/close/rate/reopen/return/remind/escalate...",
    )
    content: Mapped[Optional[str]] = mapped_column(Text, comment="说明/评论")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="records")
