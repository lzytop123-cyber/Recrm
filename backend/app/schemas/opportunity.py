"""商机请求/响应 Schema。"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class OpportunityCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    customer_id: int
    business_type: str = "other"
    stage: str = "need_confirm"
    expected_amount: Optional[Decimal] = None
    requirement_summary: str = Field(..., min_length=1, description="需求与成交依据")
    next_action_at: Optional[datetime] = None
    next_action_note: Optional[str] = None
    remark: Optional[str] = None
    source_lead_id: Optional[int] = None


class OpportunityUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    business_type: Optional[str] = None
    expected_amount: Optional[Decimal] = None
    requirement_summary: Optional[str] = None
    next_action_at: Optional[datetime] = None
    next_action_note: Optional[str] = None
    remark: Optional[str] = None


class OpportunityStageChange(BaseModel):
    stage: str = Field(..., description="目标阶段")
    evidence: Optional[str] = Field(None, description="阶段变更依据")
    lost_reason: Optional[str] = None


class OpportunityActivityCreate(BaseModel):
    content: str = Field(..., min_length=1)
    evidence: Optional[str] = None
    next_action_at: Optional[datetime] = None
    next_action_note: Optional[str] = None


class OpportunityActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_id: int
    user_id: Optional[int] = None
    activity_type: str
    content: Optional[str] = None
    evidence: Optional[str] = None
    from_stage: Optional[str] = None
    to_stage: Optional[str] = None
    next_action_at: Optional[datetime] = None
    created_at: datetime
    user_name: Optional[str] = None


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_no: str
    title: str
    customer_id: int
    source_lead_id: Optional[int] = None
    business_type: str
    stage: str
    expected_amount: Decimal
    currency: str
    owner_id: Optional[int] = None
    creator_id: Optional[int] = None
    department_id: Optional[int] = None
    requirement_summary: Optional[str] = None
    next_action_at: Optional[datetime] = None
    next_action_note: Optional[str] = None
    lost_reason: Optional[str] = None
    won_at: Optional[datetime] = None
    lost_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    owner_name: Optional[str] = None
    creator_name: Optional[str] = None
    customer_name: Optional[str] = None


class OpportunityDetailOut(OpportunityOut):
    activities: List[OpportunityActivityOut] = []
    linked_contract_id: Optional[int] = None
    linked_contract_no: Optional[str] = None
    linked_contract_status: Optional[str] = None


class OpportunityListOut(BaseModel):
    total: int
    items: List[OpportunityOut]


class OpportunityStatsOut(BaseModel):
    total: int
    open_count: int
    open_amount: Decimal = Decimal("0")
    won: int
    lost: int
    negotiation: int
    overdue_actions: int = 0
    pending_contract: int = 0
    customer_count: int = 0
    won_amount: Decimal = Decimal("0")
