"""排期请求/响应 Schema。"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScheduleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    schedule_type: str = Field(default="other")
    resource_type: str = Field(default="other")
    employee_id: int
    project_id: Optional[int] = None
    project_task_id: Optional[int] = None
    ticket_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    remark: Optional[str] = None


class ScheduleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    schedule_type: Optional[str] = None
    resource_type: Optional[str] = None
    employee_id: Optional[int] = None
    project_id: Optional[int] = None
    project_task_id: Optional[int] = None
    ticket_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    remark: Optional[str] = None


class ScheduleCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class ScheduleCoordinateRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=500)


class ScheduleCompleteRequest(BaseModel):
    result: str = Field(..., min_length=1)
    actual_hours: Decimal = Field(..., gt=0, le=24)
    create_timesheet: bool = True


class ScheduleConflictOut(BaseModel):
    id: int
    title: str
    start_time: datetime
    end_time: datetime
    status: str


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    schedule_type: str = "other"
    resource_type: str
    employee_id: int
    project_id: Optional[int] = None
    project_task_id: Optional[int] = None
    ticket_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    status: str
    creator_id: int
    department_id: Optional[int] = None
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    location: Optional[str] = None
    content: Optional[str] = None
    coordination_note: Optional[str] = None
    result: Optional[str] = None
    actual_hours: Optional[Decimal] = None
    timesheet_id: Optional[int] = None
    feishu_sync_status: str = "none"
    cancel_reason: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None
    creator_name: Optional[str] = None
    confirmed_by_name: Optional[str] = None
    project_name: Optional[str] = None
    project_no: Optional[str] = None
    task_no: Optional[str] = None
    task_title: Optional[str] = None
    ticket_no: Optional[str] = None
    has_conflict: bool = False
    conflicts: List[ScheduleConflictOut] = []
    planned_hours: Optional[float] = None


class ScheduleListOut(BaseModel):
    total: int
    items: List[ScheduleOut]


class ScheduleStatsOut(BaseModel):
    total: int
    pending: int
    confirmed: int
    in_progress: int
    completed: int
    cancelled: int
    conflict_count: int
    mine: int


class ResourceLoadOut(BaseModel):
    employee_id: int
    employee_name: str
    resource_type: str
    planned_hours: float
    load_percent: int
    item_count: int


class ResourceLoadListOut(BaseModel):
    items: List[ResourceLoadOut]
