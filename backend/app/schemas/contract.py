"""合同管理请求/响应 Schema。"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ContractProofFile(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    path: str = Field(..., min_length=1, max_length=500)
    url: Optional[str] = None


class ContractCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    customer_id: int
    opportunity_id: Optional[int] = None
    contract_type: str = Field(default="other")
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="CNY", max_length=10)
    payment_method: Optional[str] = None
    effective_date: Optional[date] = None
    expire_date: Optional[date] = None
    remark: Optional[str] = None
    # 起草页必传；商机一键发起可后补，提交审批时校验
    proof_filename: Optional[str] = Field(None, min_length=1, max_length=255)
    proof_path: Optional[str] = Field(None, min_length=1, max_length=500)
    proofs: Optional[List[ContractProofFile]] = Field(
        None, description="合同证明多文件；优先于单文件字段"
    )


class ContractUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    customer_id: Optional[int] = None
    contract_type: Optional[str] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    effective_date: Optional[date] = None
    expire_date: Optional[date] = None
    signed_date: Optional[date] = None
    remark: Optional[str] = None
    proof_filename: Optional[str] = Field(None, min_length=1, max_length=255)
    proof_path: Optional[str] = Field(None, min_length=1, max_length=500)
    proofs: Optional[List[ContractProofFile]] = Field(
        None, description="合同证明多文件；传入则整体覆盖"
    )


class ContractModifyRequest(BaseModel):
    """已生效合同修改重审（AP-04）。"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    contract_type: Optional[str] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    effective_date: Optional[date] = None
    expire_date: Optional[date] = None
    remark: Optional[str] = None
    proofs: Optional[List[ContractProofFile]] = None
    reason: str = Field(..., min_length=1, max_length=500)


class ContractTerminateRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class ContractSignRequest(BaseModel):
    signed_date: Optional[date] = None
    effective_date: Optional[date] = None
    expire_date: Optional[date] = None


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_no: str
    title: str
    customer_id: int
    opportunity_id: Optional[int] = None
    contract_type: str
    amount: Decimal
    currency: str
    payment_method: Optional[str] = None
    status: str
    signed_date: Optional[date] = None
    effective_date: Optional[date] = None
    expire_date: Optional[date] = None
    owner_id: Optional[int] = None
    creator_id: Optional[int] = None
    department_id: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    terminate_reason: Optional[str] = None
    remark: Optional[str] = None
    revision: int = 1
    modification_pending: bool = False
    approval_in_center: bool = False
    open_approval_id: Optional[str] = None
    proof_filename: Optional[str] = None
    proof_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    customer_name: Optional[str] = None
    owner_name: Optional[str] = None
    creator_name: Optional[str] = None
    approved_by_name: Optional[str] = None
    paid_amount: Decimal = Decimal("0")
    next_due_date: Optional[date] = None
    collection_status: Optional[str] = None  # collecting / collected
    proof_url: Optional[str] = None
    proofs: List[ContractProofFile] = Field(default_factory=list)


class ContractListOut(BaseModel):
    total: int
    items: List[ContractOut]


class ContractStatsOut(BaseModel):
    total: int
    draft: int
    pending_approval: int
    approved: int
    signed: int
    active: int
    completed: int
    terminated: int
    mine: int
