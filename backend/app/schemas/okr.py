"""OKR 请求/响应 Schema。"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class KeyResultCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    target_value: Decimal = Field(default=Decimal("100"), gt=0)
    current_value: Decimal = Field(default=Decimal("0"), ge=0)
    unit: Optional[str] = "%"
    weight: int = Field(default=1, ge=1)
    sort_order: int = 0
    remark: Optional[str] = None


class KeyResultUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    target_value: Optional[Decimal] = Field(None, gt=0)
    current_value: Optional[Decimal] = Field(None, ge=0)
    unit: Optional[str] = None
    weight: Optional[int] = Field(None, ge=1)
    sort_order: Optional[int] = None
    remark: Optional[str] = None


class OkrCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    level: str = Field(default="personal")
    period_type: str = Field(default="quarterly")
    period_label: str = Field(..., min_length=1, max_length=30)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    remark: Optional[str] = None
    key_results: List[KeyResultCreate] = []


class OkrUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    level: Optional[str] = None
    period_type: Optional[str] = None
    period_label: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    remark: Optional[str] = None


class KeyResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    okr_id: int
    title: str
    target_value: Decimal
    current_value: Decimal
    unit: Optional[str] = None
    weight: int
    sort_order: int
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    progress: int = 0


class OkrOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    level: str
    period_type: str
    period_label: str
    status: str
    owner_id: Optional[int] = None
    creator_id: Optional[int] = None
    department_id: Optional[int] = None
    parent_id: Optional[int] = None
    progress: int
    description: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    owner_name: Optional[str] = None
    creator_name: Optional[str] = None
    parent_title: Optional[str] = None
    kr_count: int = 0


class OkrDetailOut(OkrOut):
    key_results: List[KeyResultOut] = []


class OkrListOut(BaseModel):
    total: int
    items: List[OkrOut]


class OkrStatsOut(BaseModel):
    total: int
    pending: int
    active: int
    completed: int
    terminated: int
    mine: int
    avg_progress: int = 0
    unaligned: int = 0
    company_count: int = 0
    department_count: int = 0
    personal_count: int = 0
    risk_count: int = 0
