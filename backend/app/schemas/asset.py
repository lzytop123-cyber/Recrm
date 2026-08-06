"""固定资产 Schema。"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: str = Field(..., min_length=1, max_length=40)
    model: Optional[str] = None
    serial_no: Optional[str] = None
    location: Optional[str] = None
    original_value: Decimal = Field(default=Decimal("0"), ge=0)
    purchase_date: Optional[date] = None
    next_maintenance: Optional[date] = None
    department_id: Optional[int] = None
    remark: Optional[str] = None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_no: str
    name: str
    category: str
    model: Optional[str] = None
    serial_no: Optional[str] = None
    status: str
    holder_id: Optional[int] = None
    department_id: Optional[int] = None
    location: Optional[str] = None
    original_value: Decimal
    purchase_date: Optional[date] = None
    next_maintenance: Optional[date] = None
    qr_code: str
    current_use: Optional[str] = None
    schedule_ref: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    holder_name: Optional[str] = None
    department_name: Optional[str] = None
    monthly_depreciation: Optional[Decimal] = None
    accumulated_depreciation: Optional[Decimal] = None
    net_value: Optional[Decimal] = None


class BorrowCreate(BaseModel):
    purpose: str = Field(..., min_length=1, max_length=200)
    asset_ids: List[int] = Field(..., min_length=1)
    start_time: datetime
    end_time: datetime
    schedule_ref: Optional[str] = None
    remark: Optional[str] = None


class BorrowRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class BorrowItemOut(BaseModel):
    asset_id: int
    asset_no: str
    name: str
    category: str
    status: str


class BorrowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_no: str
    purpose: str
    applicant_id: int
    start_time: datetime
    end_time: datetime
    schedule_ref: Optional[str] = None
    status: str
    reject_reason: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    applicant_name: Optional[str] = None
    assets: List[BorrowItemOut] = []
    asset_count: int = 0


class InventorySessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period_label: str
    title: str
    target_count: int
    scanned_count: int
    matched_count: int
    anomaly_count: int
    status: str


class ScanRequest(BaseModel):
    qr_code: Optional[str] = None
    asset_id: Optional[int] = None
    mode: str = Field(default="inventory")  # inventory / checkout / return


class ScanResultOut(BaseModel):
    ok: bool
    message: str
    asset: Optional[AssetOut] = None
    inventory: Optional[InventorySessionOut] = None


class AssetStatsOut(BaseModel):
    total: int
    available: int
    available_rate: int
    borrowed_or_reserved: int
    due_today: int
    alerts: int
    maintenance: int
    overdue: int
    original_value_sum: Decimal
    net_value_sum: Decimal
    utilization_rate: int
    on_time_return_rate: int
    maintenance_cost: Decimal


class CategoryUsageOut(BaseModel):
    category: str
    count: int
    utilization: int


class AlertOut(BaseModel):
    kind: str
    title: str
    detail: str
    tag: str
    asset_id: Optional[int] = None
    request_id: Optional[int] = None


class TopBorrowOut(BaseModel):
    asset_id: int
    name: str
    count: int
    score: int


class AssetWorkbenchOut(BaseModel):
    stats: AssetStatsOut
    assets: List[AssetOut]
    borrows: List[BorrowOut]
    inventory: Optional[InventorySessionOut] = None
    category_usage: List[CategoryUsageOut]
    alerts: List[AlertOut]
    top_borrows: List[TopBorrowOut]
    can_manage: bool


class InventoryCreate(BaseModel):
    period_label: Optional[str] = None
    title: Optional[str] = Field(None, max_length=120)


class InventoryLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    asset_id: Optional[int] = None
    qr_code: Optional[str] = None
    result: str
    scanned_by: Optional[int] = None
    scanned_at: Optional[datetime] = None
    remark: Optional[str] = None


class InventoryDetailOut(InventorySessionOut):
    lines: List[InventoryLineOut] = []


class InventoryDifferenceOut(BaseModel):
    missing: List[InventoryLineOut] = []
    extra: List[InventoryLineOut] = []
    anomaly: List[InventoryLineOut] = []
    matched_count: int = 0


class MaintenanceCreate(BaseModel):
    asset_id: int
    title: str = Field(..., min_length=1, max_length=120)
    plan_date: Optional[date] = None
    cost: Optional[Decimal] = None
    remark: Optional[str] = None


class MaintenanceRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class MaintenanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    title: str
    plan_date: Optional[date] = None
    status: str
    applicant_id: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    cost: Optional[Decimal] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    asset_name: Optional[str] = None
    applicant_name: Optional[str] = None


class DepreciationRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    version: str = Field(default="1", max_length=40)
    status: str = Field(default="draft")
    method: str = Field(default="straight_line")
    useful_life_months: int = Field(default=60, ge=1)
    residual_rate: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)
    effective_from: Optional[date] = None


class DepreciationRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: str
    status: str
    method: str
    useful_life_months: int
    residual_rate: Decimal
    effective_from: Optional[date] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class DepreciationRunRequest(BaseModel):
    period_label: Optional[str] = None


class DepreciationSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period_label: str
    asset_id: int
    rule_id: Optional[int] = None
    original_value: Decimal
    monthly_amount: Decimal
    accumulated: Decimal
    net_value: Decimal
    created_at: datetime
    asset_name: Optional[str] = None


class DisposeRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class DisposalRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class DisposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    reason: str
    status: str
    applicant_id: int
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    disposed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    asset_name: Optional[str] = None
    applicant_name: Optional[str] = None


class AssetReportOut(BaseModel):
    total: int
    by_status: dict
    by_category: dict
    original_value_sum: Decimal
    net_value_sum: Decimal
    maintenance_open: int
    disposal_pending: int


class ShootingScheduleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    shoot_date: date
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    asset_ids: List[int] = []
    member_ids: List[int] = []
    remark: Optional[str] = None


class ShootingScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    shoot_date: date
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    owner_id: int
    status: str
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    owner_name: Optional[str] = None
    asset_ids: List[int] = []
    member_ids: List[int] = []
    conflicts: List[str] = []
