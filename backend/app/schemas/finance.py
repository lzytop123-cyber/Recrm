"""合同财务闭环 API Schema。"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReceivableCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0)
    due_date: date
    sequence_no: Optional[int] = Field(None, ge=1)
    remark: Optional[str] = None


class ReceivableUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    amount: Optional[Decimal] = Field(None, gt=0)
    due_date: Optional[date] = None
    remark: Optional[str] = None
    version: int = Field(..., ge=1)


class ReceivableCancelRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
    version: int = Field(..., ge=1)


class ReceivableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    contract_id: int
    sequence_no: int
    title: str
    amount: Decimal
    due_date: date
    currency: str
    status: str
    allocated_amount: Decimal = Decimal("0")
    outstanding_amount: Decimal = Decimal("0")
    effective_status: str = "unpaid"
    contract_no: Optional[str] = None
    contract_title: Optional[str] = None
    customer_name: Optional[str] = None
    owner_name: Optional[str] = None
    version: int
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReceivableListOut(BaseModel):
    total: int
    items: list[ReceivableOut]


class ReceiptCreate(BaseModel):
    contract_id: int
    amount: Decimal = Field(..., gt=0)
    paid_date: date
    payer_name: str = Field(..., min_length=1, max_length=200)
    payment_method: Optional[str] = Field(None, max_length=50)
    bank_reference: Optional[str] = Field(None, max_length=100)
    proof_filename: Optional[str] = Field(None, max_length=255)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=100)
    remark: Optional[str] = None


class ReceiptReviewRequest(BaseModel):
    remark: Optional[str] = None
    version: int = Field(..., ge=1)


class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    receipt_no: str
    contract_id: int
    amount: Decimal
    paid_date: date
    payer_name: str
    payment_method: Optional[str] = None
    bank_reference: Optional[str] = None
    proof_filename: Optional[str] = None
    status: str
    submitted_by: Optional[int] = None
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    allocated_amount: Decimal = Decimal("0")
    pending_allocation_amount: Decimal = Decimal("0")
    refunded_amount: Decimal = Decimal("0")
    available_amount: Decimal = Decimal("0")
    contract_no: Optional[str] = None
    contract_title: Optional[str] = None
    customer_name: Optional[str] = None
    submitted_by_name: Optional[str] = None
    confirmed_by_name: Optional[str] = None
    version: int
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReceiptListOut(BaseModel):
    total: int
    items: list[ReceiptOut]


class AllocationCreate(BaseModel):
    receivable_plan_id: int
    amount: Decimal = Field(..., gt=0)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=100)


class AllocationReverseRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
    version: int = Field(..., ge=1)


class AllocationReviewRequest(BaseModel):
    remark: Optional[str] = None
    version: int = Field(..., ge=1)


class AllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    receipt_id: int
    receivable_plan_id: int
    amount: Decimal
    status: str
    allocated_by: Optional[int] = None
    allocated_at: datetime
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    review_remark: Optional[str] = None
    reversed_by: Optional[int] = None
    reversed_at: Optional[datetime] = None
    reverse_reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    version: int


class RefundCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=100)


class RefundReviewRequest(BaseModel):
    remark: Optional[str] = None
    version: int = Field(..., ge=1)


class RefundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    refund_no: str
    receipt_id: int
    amount: Decimal
    reason: str
    review_remark: Optional[str] = None
    status: str
    requested_by: Optional[int] = None
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class ContractFinancialSummary(BaseModel):
    contract_id: int
    contract_amount: Decimal
    receivable_total: Decimal
    confirmed_receipt_total: Decimal
    refunded_total: Decimal
    allocated_total: Decimal
    outstanding_receivable: Decimal
    unallocated_receipt_balance: Decimal
    overdue_receivable: Decimal


class FinanceStatsOut(BaseModel):
    month_contract_amount: Decimal
    confirmed_receipt_amount: Decimal
    receivable_total: Decimal
    outstanding_receivable_amount: Decimal
    allocated_amount: Decimal
    unallocated_receipt_amount: Decimal
    pending_review_count: int
    pending_review_amount: Decimal
    overdue_count: int
    overdue_amount: Decimal
    collection_rate: Decimal
    forecast_gross_margin: Decimal = Decimal("34.8")
