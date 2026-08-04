"""员工档案扩展：任职经历、飞书考勤日事实、系统同步状态。"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class EmployeeHistoryEvent(Base):
    __tablename__ = "employee_history_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="hire/transfer/resign/regularize/other"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="history_events")


class FeishuAttendanceDaily(Base):
    __tablename__ = "feishu_attendance_daily"
    __table_args__ = (UniqueConstraint("user_id", "work_date", name="uq_feishu_attendance_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="正常/迟到/早退/缺卡/请假/外出/休息日/异常",
    )
    first_punch: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    last_punch: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    source: Mapped[str] = mapped_column(
        String(40), nullable=False, default="飞书同步", comment="飞书同步/日历规则"
    )
    raw_result: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="attendance_days")


class SystemSyncState(Base):
    __tablename__ = "system_sync_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", comment="ok/error/pending/unknown"
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
