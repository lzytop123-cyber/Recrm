"""客户管理请求/响应 Schema。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    short_name: Optional[str] = Field(None, max_length=100)
    contact_name: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    address: Optional[str] = None
    source: Optional[str] = Field(None, description="官网/转介绍/展会/线上广告/线索转化等")
    status: str = Field(default="potential")
    remark: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    short_name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    address: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    owner_id: Optional[int] = None
    remark: Optional[str] = None


class CustomerFollowUpCreate(BaseModel):
    follow_at: Optional[datetime] = None
    method: str = Field(default="phone")
    content: str = Field(..., min_length=1)
    next_follow_at: Optional[datetime] = None


class CustomerFollowUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    user_id: int
    follow_at: datetime
    method: str
    content: str
    next_follow_at: Optional[datetime] = None
    created_at: datetime
    user_name: Optional[str] = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    address: Optional[str] = None
    source: Optional[str] = None
    status: str
    owner_id: Optional[int] = None
    creator_id: Optional[int] = None
    department_id: Optional[int] = None
    source_lead_id: Optional[int] = None
    last_followed_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    owner_name: Optional[str] = None
    creator_name: Optional[str] = None


class CustomerOpportunityBrief(BaseModel):
    id: int
    opportunity_no: str
    title: str
    stage: str
    expected_amount: float = 0
    owner_name: Optional[str] = None
    next_action_at: Optional[datetime] = None
    updated_at: datetime


class CustomerTimelineItem(BaseModel):
    """客户页统一轨迹：线索跟进 / 商机活动 / 客户级跟进。"""

    key: str
    source: str  # lead | opportunity | customer
    occurred_at: datetime
    title: str
    content: str
    user_name: Optional[str] = None
    method: Optional[str] = None
    lead_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    opportunity_title: Optional[str] = None
    activity_type: Optional[str] = None
    evidence: Optional[str] = None
    next_action_at: Optional[datetime] = None


class CustomerDetailOut(CustomerOut):
    follow_ups: List[CustomerFollowUpOut] = []
    opportunities: List[CustomerOpportunityBrief] = []
    timeline: List[CustomerTimelineItem] = []
    last_activity_at: Optional[datetime] = None


class CustomerListOut(BaseModel):
    total: int
    items: List[CustomerOut]


class CustomerStatsOut(BaseModel):
    total: int
    potential: int
    active: int
    paused: int
    terminated: int
    mine: int
