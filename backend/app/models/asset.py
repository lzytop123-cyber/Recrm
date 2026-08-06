"""
固定资产：台账、借用归还、盘点维保精简闭环。
对齐高保真原型 asset-management。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ASSET_STATUS_AVAILABLE = "available"
ASSET_STATUS_RESERVED = "reserved"
ASSET_STATUS_BORROWED = "borrowed"
ASSET_STATUS_PENDING_RETURN = "pending_return"
ASSET_STATUS_MAINTENANCE = "maintenance"
ASSET_STATUS_DISPOSED = "disposed"

ASSET_STATUSES = {
    ASSET_STATUS_AVAILABLE,
    ASSET_STATUS_RESERVED,
    ASSET_STATUS_BORROWED,
    ASSET_STATUS_PENDING_RETURN,
    ASSET_STATUS_MAINTENANCE,
    ASSET_STATUS_DISPOSED,
}

ASSET_CATEGORIES = {"相机", "镜头", "灯具", "收音", "稳定器", "其他"}

BORROW_PENDING = "pending"
BORROW_APPROVED = "approved"
BORROW_REJECTED = "rejected"
BORROW_IN_USE = "in_use"
BORROW_PENDING_RETURN = "pending_return"
BORROW_RETURNED = "returned"


class FixedAsset(Base):
    __tablename__ = "fixed_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    model: Mapped[Optional[str]] = mapped_column(String(80))
    serial_no: Mapped[Optional[str]] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default=ASSET_STATUS_AVAILABLE, index=True)
    holder_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"))
    location: Mapped[Optional[str]] = mapped_column(String(120))
    original_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    purchase_date: Mapped[Optional[date]] = mapped_column(Date)
    next_maintenance: Mapped[Optional[date]] = mapped_column(Date)
    qr_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    current_use: Mapped[Optional[str]] = mapped_column(String(200))
    schedule_ref: Mapped[Optional[str]] = mapped_column(String(40))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssetBorrowRequest(Base):
    __tablename__ = "asset_borrow_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    applicant_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schedule_ref: Mapped[Optional[str]] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default=BORROW_PENDING, index=True)
    reject_reason: Mapped[Optional[str]] = mapped_column(Text)
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssetBorrowItem(Base):
    __tablename__ = "asset_borrow_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("asset_borrow_requests.id"), nullable=False, index=True
    )
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixed_assets.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssetInventorySession(Base):
    __tablename__ = "asset_inventory_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_label: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, default=0)
    scanned_count: Mapped[int] = mapped_column(Integer, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="in_progress")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssetInventoryLine(Base):
    __tablename__ = "asset_inventory_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("asset_inventory_sessions.id"), nullable=False, index=True
    )
    asset_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("fixed_assets.id"), index=True)
    qr_code: Mapped[Optional[str]] = mapped_column(String(40))
    result: Mapped[str] = mapped_column(String(30), nullable=False, default="matched")
    scanned_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    remark: Mapped[Optional[str]] = mapped_column(Text)


class AssetMaintenance(Base):
    __tablename__ = "asset_maintenances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixed_assets.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    applicant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[Optional[str]] = mapped_column(Text)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssetDepreciationRule(Base):
    __tablename__ = "asset_depreciation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="1")
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    method: Mapped[str] = mapped_column(String(40), default="straight_line")
    useful_life_months: Mapped[int] = mapped_column(Integer, default=60)
    residual_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.05"))
    effective_from: Mapped[Optional[date]] = mapped_column(Date)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssetDepreciationSnapshot(Base):
    __tablename__ = "asset_depreciation_snapshots"
    __table_args__ = (UniqueConstraint("period_label", "asset_id", name="uq_depr_snapshot_period_asset"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_label: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixed_assets.id"), nullable=False, index=True)
    rule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("asset_depreciation_rules.id"))
    original_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    accumulated: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    net_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssetDisposal(Base):
    __tablename__ = "asset_disposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixed_assets.id"), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    applicant_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[Optional[str]] = mapped_column(Text)
    disposed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShootingSchedule(Base):
    __tablename__ = "shooting_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    shoot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShootingScheduleAsset(Base):
    __tablename__ = "shooting_schedule_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shooting_schedules.id"), nullable=False, index=True
    )
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixed_assets.id"), nullable=False, index=True)


class ShootingScheduleMember(Base):
    __tablename__ = "shooting_schedule_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shooting_schedules.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
