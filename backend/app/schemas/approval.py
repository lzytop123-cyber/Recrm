"""审批中心：聚合各业务待办审批项。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ApprovalFact(BaseModel):
    label: str
    value: str


class ApprovalItemOut(BaseModel):
    id: str
    type: str
    category: str
    source: str
    source_id: str
    title: str
    applicant_name: str = "—"
    department_name: str = "—"
    submitted_at: Optional[datetime] = None
    status: str
    status_label: str
    node: str
    summary: str = ""
    facts: list[ApprovalFact] = Field(default_factory=list)
    deep_link: str
    can_act: bool = False
    actions: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class ApprovalListOut(BaseModel):
    total: int
    items: list[ApprovalItemOut]


class ApprovalStatsOut(BaseModel):
    pending: int = 0
    initiated: int = 0
    processed: int = 0
    cc: int = 0
