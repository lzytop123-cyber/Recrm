"""审批规则 CRUD 与发布。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ApprovalRuleCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    biz_type: str = Field(..., min_length=1, max_length=50)
    nodes_json: str = Field(..., min_length=2)
    conditions_json: Optional[str] = None
    timeout_hours: int = Field(72, ge=1, le=8760)
    remark: Optional[str] = None


class ApprovalRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    biz_type: Optional[str] = Field(None, min_length=1, max_length=50)
    nodes_json: Optional[str] = Field(None, min_length=2)
    conditions_json: Optional[str] = None
    timeout_hours: Optional[int] = Field(None, ge=1, le=8760)
    remark: Optional[str] = None


class ApprovalRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    biz_type: str
    nodes_json: str
    conditions_json: Optional[str] = None
    timeout_hours: int
    version: int
    status: str
    remark: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class ApprovalRuleListOut(BaseModel):
    total: int
    items: list[ApprovalRuleOut]
