"""
管人：OKR 目标与关键结果。
对齐 PRD 4.2（骨架期：制定、确认、进度更新、评估；对齐关系后续可扩展）。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

OKR_LEVEL_COMPANY = "company"
OKR_LEVEL_DEPARTMENT = "department"
OKR_LEVEL_PERSONAL = "personal"

OKR_LEVELS = {OKR_LEVEL_COMPANY, OKR_LEVEL_DEPARTMENT, OKR_LEVEL_PERSONAL}

OKR_PERIOD_YEARLY = "yearly"
OKR_PERIOD_QUARTERLY = "quarterly"
OKR_PERIOD_MONTHLY = "monthly"

OKR_PERIODS = {OKR_PERIOD_YEARLY, OKR_PERIOD_QUARTERLY, OKR_PERIOD_MONTHLY}

OKR_STATUS_PENDING = "pending"
OKR_STATUS_ACTIVE = "active"
OKR_STATUS_COMPLETED = "completed"
OKR_STATUS_ADJUSTED = "adjusted"
OKR_STATUS_TERMINATED = "terminated"

OKR_STATUSES = {
    OKR_STATUS_PENDING,
    OKR_STATUS_ACTIVE,
    OKR_STATUS_COMPLETED,
    OKR_STATUS_ADJUSTED,
    OKR_STATUS_TERMINATED,
}


class Okr(Base):
    __tablename__ = "okrs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="目标名称")
    level: Mapped[str] = mapped_column(
        String(20), default=OKR_LEVEL_PERSONAL, index=True, comment="company/department/personal"
    )
    period_type: Mapped[str] = mapped_column(
        String(20), default=OKR_PERIOD_QUARTERLY, comment="yearly/quarterly/monthly"
    )
    period_label: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, comment="如 2026-Q3 / 2026-07"
    )
    status: Mapped[str] = mapped_column(
        String(30), default=OKR_STATUS_PENDING, index=True, comment="目标状态"
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True, comment="负责人"
    )
    creator_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="创建人"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, index=True, comment="所属部门"
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("okrs.id"), nullable=True, comment="对齐的上级目标"
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="进度 0-100")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="目标说明")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    key_results: Mapped[list["KeyResult"]] = relationship(
        "KeyResult",
        back_populates="okr",
        cascade="all, delete-orphan",
    )


class KeyResult(Base):
    __tablename__ = "key_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    okr_id: Mapped[int] = mapped_column(Integer, ForeignKey("okrs.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="关键结果")
    target_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=100)
    current_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    unit: Mapped[Optional[str]] = mapped_column(String(30), comment="单位：%、元、个等")
    weight: Mapped[int] = mapped_column(Integer, default=1, comment="权重")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    okr: Mapped["Okr"] = relationship("Okr", back_populates="key_results")
