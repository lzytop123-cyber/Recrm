"""合同财务闭环：应收计划、实际收款、核销和退款事实。"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

RECEIVABLE_STATUS_UNPAID = "unpaid"
RECEIVABLE_STATUS_PARTIALLY_PAID = "partially_paid"
RECEIVABLE_STATUS_PAID = "paid"
RECEIVABLE_STATUS_CANCELLED = "cancelled"

RECEIPT_STATUS_PENDING_REVIEW = "pending_review"
RECEIPT_STATUS_CONFIRMED = "confirmed"
RECEIPT_STATUS_REJECTED = "rejected"
RECEIPT_STATUS_CANCELLED = "cancelled"

ALLOCATION_STATUS_PENDING = "pending"
ALLOCATION_STATUS_ACTIVE = "active"
ALLOCATION_STATUS_REJECTED = "rejected"
ALLOCATION_STATUS_REVERSED = "reversed"

REFUND_STATUS_PENDING = "pending"
REFUND_STATUS_CONFIRMED = "confirmed"
REFUND_STATUS_REJECTED = "rejected"
REFUND_STATUS_CANCELLED = "cancelled"


class ReceivablePlan(Base):
    __tablename__ = "receivable_plans"
    __table_args__ = (
        UniqueConstraint("contract_id", "sequence_no", name="uq_receivable_contract_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contracts.id"), nullable=False, index=True
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=RECEIVABLE_STATUS_UNPAID, index=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contracts.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    paid_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    payer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    bank_reference: Mapped[Optional[str]] = mapped_column(String(100))
    proof_filename: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=RECEIPT_STATUS_PENDING_REVIEW, index=True
    )
    submitted_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    confirmed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"))
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReceiptAllocation(Base):
    __tablename__ = "receipt_allocations"
    __table_args__ = (
        UniqueConstraint(
            "receipt_id", "idempotency_key",
            name="uq_allocation_business_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("receipts.id"), nullable=False, index=True
    )
    receivable_plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("receivable_plans.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ALLOCATION_STATUS_PENDING, index=True
    )
    allocated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    review_remark: Mapped[Optional[str]] = mapped_column(String(500))
    reversed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    reversed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reverse_reason: Mapped[Optional[str]] = mapped_column(String(500))
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    refund_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    receipt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("receipts.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    review_remark: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=REFUND_STATUS_PENDING, index=True
    )
    requested_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    confirmed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
