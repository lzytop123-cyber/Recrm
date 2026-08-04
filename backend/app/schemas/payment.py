"""收款管理请求/响应 Schema。"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    contract_id: int
    title: Optional[str] = Field(None, max_length=100, description="如：首付款/尾款")
    amount: Decimal = Field(..., gt=0)
    due_date: Optional[date] = None
    method: Optional[str] = None
    remark: Optional[str] = None


class PaymentClaimCreate(BaseModel):
    contract_id: int
    amount: Decimal = Field(..., gt=0)
    paid_date: date
    payer_name: str = Field(..., min_length=1, max_length=200)
    account_tail: Optional[str] = Field(None, max_length=10)
    proof_filename: str = Field(..., min_length=1, max_length=255)
    remark: Optional[str] = None


class PaymentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    amount: Optional[Decimal] = Field(None, gt=0)
    due_date: Optional[date] = None
    method: Optional[str] = None
    remark: Optional[str] = None


class PaymentConfirmRequest(BaseModel):
    paid_date: Optional[date] = None
    method: Optional[str] = None
    remark: Optional[str] = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_no: Optional[str] = None
    contract_id: int
    record_type: str = "plan"
    title: Optional[str] = None
    amount: Decimal
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    status: str
    method: Optional[str] = None
    payer_name: Optional[str] = None
    account_tail: Optional[str] = None
    proof_filename: Optional[str] = None
    owner_id: Optional[int] = None
    creator_id: Optional[int] = None
    department_id: Optional[int] = None
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # 展示辅助
    contract_no: Optional[str] = None
    contract_title: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    owner_name: Optional[str] = None
    creator_name: Optional[str] = None
    confirmed_by_name: Optional[str] = None
    due_status: Optional[str] = None  # not_due/due_soon/due/overdue/settled/refunded


class PaymentListOut(BaseModel):
    total: int
    items: List[PaymentOut]


class PaymentStatsOut(BaseModel):
    total: int
    pending: int
    confirmed: int
    refunded: int
    overdue: int
    pending_amount: Decimal
    confirmed_amount: Decimal
    mine: int
    pending_review: int = 0
    pending_review_amount: Decimal = Decimal("0")
    due_soon_amount: Decimal = Decimal("0")
    month_contract_amount: Decimal = Decimal("0")
    collection_rate: Decimal = Decimal("0")
    forecast_gross_margin: Decimal = Decimal("34.8")
