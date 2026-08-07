"""
管人：资源排期 / 会议。
对齐 PRD 4.3、FR-055～064（创建、确认、冲突、完成工时；飞书同步字段预留）。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

SCHEDULE_RESOURCE_INSTRUCTOR = "instructor"
SCHEDULE_RESOURCE_STREAMER = "streamer"
SCHEDULE_RESOURCE_SHOOTING_EDIT = "shooting_edit"
SCHEDULE_RESOURCE_OTHER = "other"

SCHEDULE_RESOURCE_TYPES = {
    SCHEDULE_RESOURCE_INSTRUCTOR,
    SCHEDULE_RESOURCE_STREAMER,
    SCHEDULE_RESOURCE_SHOOTING_EDIT,
    SCHEDULE_RESOURCE_OTHER,
}

SCHEDULE_TYPE_INTERNAL = "internal_training"
SCHEDULE_TYPE_EXTERNAL = "external_salon"
SCHEDULE_TYPE_LIVE = "project_live"
SCHEDULE_TYPE_OTHER = "other"

SCHEDULE_TYPES = {
    SCHEDULE_TYPE_INTERNAL,
    SCHEDULE_TYPE_EXTERNAL,
    SCHEDULE_TYPE_LIVE,
    SCHEDULE_TYPE_OTHER,
}

SCHEDULE_STATUS_PENDING = "pending"
SCHEDULE_STATUS_CONFIRMED = "confirmed"
SCHEDULE_STATUS_IN_PROGRESS = "in_progress"
SCHEDULE_STATUS_COMPLETED = "completed"
SCHEDULE_STATUS_CANCELLED = "cancelled"

SCHEDULE_STATUSES = {
    SCHEDULE_STATUS_PENDING,
    SCHEDULE_STATUS_CONFIRMED,
    SCHEDULE_STATUS_IN_PROGRESS,
    SCHEDULE_STATUS_COMPLETED,
    SCHEDULE_STATUS_CANCELLED,
}

SCHEDULE_ACTIVE_STATUSES = {
    SCHEDULE_STATUS_PENDING,
    SCHEDULE_STATUS_CONFIRMED,
    SCHEDULE_STATUS_IN_PROGRESS,
}

FEISHU_SYNC_NONE = "none"
FEISHU_SYNC_PENDING = "pending"
FEISHU_SYNC_SYNCED = "synced"
FEISHU_SYNC_FAILED = "failed"


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="排期标题")
    schedule_type: Mapped[str] = mapped_column(
        String(30), default=SCHEDULE_TYPE_OTHER, index=True, comment="会议/活动类型"
    )
    resource_type: Mapped[str] = mapped_column(
        String(30),
        default=SCHEDULE_RESOURCE_OTHER,
        index=True,
        comment="instructor/streamer/shooting_edit/other",
    )
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="被排期人员"
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True, index=True, comment="关联项目"
    )
    project_task_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("project_tasks.id"), nullable=True, index=True, comment="关联项目任务"
    )
    ticket_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tickets.id"), nullable=True, index=True, comment="关联工单"
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, comment="开始时间"
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, comment="结束时间"
    )
    status: Mapped[str] = mapped_column(
        String(30), default=SCHEDULE_STATUS_PENDING, index=True, comment="状态"
    )
    creator_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="申请人"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, comment="申请人所在部门"
    )
    confirmed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="确认人"
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    location: Mapped[Optional[str]] = mapped_column(String(200), comment="地点/线上会议室")
    content: Mapped[Optional[str]] = mapped_column(Text, comment="排期说明")
    coordination_note: Mapped[Optional[str]] = mapped_column(Text, comment="协调说明")
    result: Mapped[Optional[str]] = mapped_column(Text, comment="完成结果")
    actual_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), comment="实际工时")
    timesheet_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("timesheets.id"), nullable=True, comment="关联工时"
    )
    feishu_sync_status: Mapped[str] = mapped_column(
        String(20), default=FEISHU_SYNC_NONE, comment="none/pending/synced/failed"
    )
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(500), comment="取消原因")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
