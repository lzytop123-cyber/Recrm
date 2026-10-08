"""人事闭环：劳动合同、转岗离职、假勤、工资条。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

CONTRACT_PENDING = "pending_sign"
CONTRACT_SIGNED = "signed"
CONTRACT_RENEWED = "renewed"
CONTRACT_TERMINATED = "terminated"
CONTRACT_CANCELLED = "cancelled"

TRANSFER_PENDING = "pending"
TRANSFER_APPROVED = "approved"
TRANSFER_REJECTED = "rejected"
TRANSFER_APPLIED = "applied"

RESIGN_PENDING = "pending_approval"
RESIGN_HANDING = "handing_over"
RESIGN_COMPLETED = "completed"
RESIGN_REJECTED = "rejected"

HANDOVER_OPEN = "open"
HANDOVER_DONE = "completed"

ITEM_PENDING = "pending"
ITEM_ASSIGNED = "assigned"
ITEM_CONFIRMED = "confirmed"

LEAVE_PENDING = "pending"
LEAVE_APPROVED = "approved"
LEAVE_REJECTED = "rejected"

PAYSLIP_PUBLISHED = "published"
PAYSLIP_CORRECTED = "corrected"


class LaborContract(Base):
    __tablename__ = "hr_labor_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    contract_type: Mapped[str] = mapped_column(String(30), nullable=False)
    signed_on: Mapped[date] = mapped_column(Date, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    trial_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    trial_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CONTRACT_PENDING, index=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("hr_labor_contracts.id"), nullable=True
    )
    remark: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HrTransfer(Base):
    __tablename__ = "hr_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    from_department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"))
    to_department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False)
    effective_on: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TRANSFER_PENDING, index=True)
    approval_instance_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("approval_instances.id"))
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HrResignation(Base):
    __tablename__ = "hr_resignations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    last_working_day: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RESIGN_PENDING, index=True)
    approval_instance_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("approval_instances.id"))
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    handover: Mapped[Optional["HrHandover"]] = relationship(
        "HrHandover", back_populates="resignation", uselist=False
    )


class HrHandover(Base):
    __tablename__ = "hr_handovers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resignation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hr_resignations.id"), nullable=False, unique=True
    )
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=HANDOVER_OPEN, index=True)
    signed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    resignation: Mapped["HrResignation"] = relationship("HrResignation", back_populates="handover")
    items: Mapped[List["HrHandoverItem"]] = relationship(
        "HrHandoverItem", back_populates="handover", cascade="all, delete-orphan"
    )


class HrHandoverItem(Base):
    __tablename__ = "hr_handover_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    handover_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hr_handovers.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    ref_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ITEM_PENDING, index=True)
    assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    handover: Mapped["HrHandover"] = relationship("HrHandover", back_populates="items")


class HrLeaveRequest(Base):
    __tablename__ = "hr_leave_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    leave_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=LEAVE_PENDING, index=True)
    approval_instance_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("approval_instances.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HrLeaveBalance(Base):
    __tablename__ = "hr_leave_balances"
    __table_args__ = (UniqueConstraint("employee_id", "leave_type", "year", name="uq_hr_leave_balance"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    leave_type: Mapped[str] = mapped_column(String(30), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quota: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("0"))
    used: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("0"))
    remaining: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("0"))
    remark: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HrPayslip(Base):
    __tablename__ = "hr_payslips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    cycle_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("performance_cycles.id"))
    period_label: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PAYSLIP_PUBLISHED, index=True)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    performance_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    adjustment_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    items_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supersedes_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("hr_payslips.id"))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
