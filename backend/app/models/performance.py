"""
管人：绩效周期、月度考核、申诉、工资批次（精简闭环）。
对齐 PRD FR-070～079 骨架。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

CYCLE_STATUS_ASSESSING = "assessing"
CYCLE_STATUS_CALIBRATING = "calibrating"
CYCLE_STATUS_LOCKED = "locked"
CYCLE_STATUS_PAYROLL = "payroll"
CYCLE_STATUS_PUBLISHED = "published"

ASSESS_PENDING_SELF = "pending_self"
ASSESS_PENDING_MANAGER = "pending_manager"
ASSESS_PENDING_CALIBRATION = "pending_calibration"
ASSESS_APPEALING = "appealing"
ASSESS_COMPLETED = "completed"

APPEAL_PENDING = "pending"
APPEAL_APPROVED = "approved"
APPEAL_REJECTED = "rejected"


class PerformanceCycle(Base):
    __tablename__ = "performance_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_label: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    rule_version: Mapped[str] = mapped_column(String(30), default="V2026.07")
    status: Mapped[str] = mapped_column(String(30), default=CYCLE_STATUS_ASSESSING, index=True)
    calibration_started: Mapped[bool] = mapped_column(Boolean, default=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    payroll_batch_no: Mapped[Optional[str]] = mapped_column(String(50))
    payroll_created: Mapped[bool] = mapped_column(Boolean, default=False)
    payroll_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    payroll_published: Mapped[bool] = mapped_column(Boolean, default=False)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PerformanceAssessment(Base):
    __tablename__ = "performance_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_cycles.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"))
    self_score: Mapped[Optional[int]] = mapped_column(Integer)
    okr_score: Mapped[Optional[int]] = mapped_column(Integer, comment="主管评：OKR达成 0-100")
    kpi_score: Mapped[Optional[int]] = mapped_column(Integer, comment="主管评：岗位KPI 0-100")
    behavior_score: Mapped[Optional[int]] = mapped_column(Integer, comment="主管评：协作与行为 0-100")
    manager_score: Mapped[Optional[int]] = mapped_column(Integer)
    final_score: Mapped[Optional[int]] = mapped_column(Integer)
    grade: Mapped[Optional[str]] = mapped_column(String(10))
    coefficient: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2))
    evidence_status: Mapped[str] = mapped_column(String(30), default="待补充")
    status: Mapped[str] = mapped_column(String(30), default=ASSESS_PENDING_SELF, index=True)
    manager_comment: Mapped[Optional[str]] = mapped_column(Text)
    bonus_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PerformanceAppeal(Base):
    __tablename__ = "performance_appeals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_assessments.id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    request_score: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=APPEAL_PENDING, index=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text)
    resolved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
