"""工时请求/响应 Schema。"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TimesheetCreate(BaseModel):
    work_date: date
    hours: Decimal = Field(..., gt=0, le=24)
    work_type: str = Field(default="project")
    project_id: Optional[int] = None
    content: str = Field(..., min_length=1)
    remark: Optional[str] = None


class TimesheetUpdate(BaseModel):
    work_date: Optional[date] = None
    hours: Optional[Decimal] = Field(None, gt=0, le=24)
    work_type: Optional[str] = None
    project_id: Optional[int] = None
    content: Optional[str] = Field(None, min_length=1)
    remark: Optional[str] = None


class TimesheetRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class TimesheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    work_date: date
    hours: Decimal
    work_type: str
    project_id: Optional[int] = None
    content: str
    status: str
    department_id: Optional[int] = None
    approver_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    user_name: Optional[str] = None
    project_no: Optional[str] = None
    project_name: Optional[str] = None
    approver_name: Optional[str] = None
    approval_in_center: bool = False


class TimesheetListOut(BaseModel):
    total: int
    items: List[TimesheetOut]


class TimesheetStatsOut(BaseModel):
    total: int
    draft: int
    submitted: int
    approved: int
    rejected: int
    mine: int
    my_hours: Decimal
    approved_hours: Decimal
