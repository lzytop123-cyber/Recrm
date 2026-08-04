"""
管人：工时记录。
对齐 PRD 4.3（登记、审批、按项目/类型统计；排期后续单独做）。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

TIMESHEET_TYPE_PROJECT = "project"
TIMESHEET_TYPE_DAILY = "daily"
TIMESHEET_TYPE_TRAINING = "training"
TIMESHEET_TYPE_LEAVE = "leave"

TIMESHEET_TYPES = {
    TIMESHEET_TYPE_PROJECT,
    TIMESHEET_TYPE_DAILY,
    TIMESHEET_TYPE_TRAINING,
    TIMESHEET_TYPE_LEAVE,
}

TIMESHEET_STATUS_DRAFT = "draft"
TIMESHEET_STATUS_SUBMITTED = "submitted"
TIMESHEET_STATUS_APPROVED = "approved"
TIMESHEET_STATUS_REJECTED = "rejected"

TIMESHEET_STATUSES = {
    TIMESHEET_STATUS_DRAFT,
    TIMESHEET_STATUS_SUBMITTED,
    TIMESHEET_STATUS_APPROVED,
    TIMESHEET_STATUS_REJECTED,
}


class Timesheet(Base):
    __tablename__ = "timesheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="填报人"
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="工作日期")
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, comment="工时小时数")
    work_type: Mapped[str] = mapped_column(
        String(30), default=TIMESHEET_TYPE_PROJECT, comment="project/daily/training/leave"
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True, index=True, comment="关联项目"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="工作内容")
    status: Mapped[str] = mapped_column(
        String(30), default=TIMESHEET_STATUS_DRAFT, index=True, comment="状态"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, comment="所属部门"
    )
    approver_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="审批人"
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[Optional[str]] = mapped_column(String(500), comment="驳回原因")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
