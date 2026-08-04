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
