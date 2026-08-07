"""工单请求/响应 Schema。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    ticket_type: str = Field(default="collaboration")
    priority: str = Field(default="normal")
    content: str = Field(..., min_length=1)
    assignee_id: Optional[int] = None
    assignee_ids: List[int] = []
    department_id: Optional[int] = None
    project_id: Optional[int] = None
    task_id: Optional[int] = None
    remark: Optional[str] = None


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    ticket_type: Optional[str] = None
    priority: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    remark: Optional[str] = None
    task_id: Optional[int] = None
    project_id: Optional[int] = None
    department_id: Optional[int] = None


class TicketAssignRequest(BaseModel):
    assignee_id: int
    remark: Optional[str] = None


class TicketTransferRequest(BaseModel):
    assignee_id: int
    reason: Optional[str] = None


class TicketCompleteRequest(BaseModel):
    result: str = Field(..., min_length=1)


class TicketConfirmRequest(BaseModel):
    satisfaction: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    close: bool = True


class TicketCloseRequest(BaseModel):
    satisfaction: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None


class TicketReopenRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class TicketReturnRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class TicketCommentRequest(BaseModel):
    content: str = Field(..., min_length=1)


class TicketRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    user_id: int
    action: str
    content: Optional[str] = None
    created_at: datetime
    user_name: Optional[str] = None


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_no: str
    title: str
    ticket_type: str
    priority: str
    status: str
    content: str
    creator_id: int
    assignee_id: Optional[int] = None
    department_id: Optional[int] = None
    project_id: Optional[int] = None
    task_id: Optional[int] = None
    due_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    result: Optional[str] = None
    remark: Optional[str] = None
    satisfaction: Optional[int] = None
    satisfaction_comment: Optional[str] = None
    sla_remind_level: int = 0
    escalated_level: int = 0
    sla_paused_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    creator_name: Optional[str] = None
    assignee_name: Optional[str] = None
    candidate_ids: List[int] = []
    candidate_names: List[str] = []
    department_name: Optional[str] = None
    project_name: Optional[str] = None
    task_no: Optional[str] = None
    task_title: Optional[str] = None
    is_overdue: bool = False
    is_near_sla: bool = False
    sla_used_ratio: Optional[float] = None
    can_reopen: bool = False
    can_assign: bool = False
    can_accept: bool = False
    can_transfer: bool = False
    can_complete: bool = False
    can_confirm: bool = False
    can_return: bool = False
    next_actor_hint: Optional[str] = None


class TicketDetailOut(TicketOut):
    records: List[TicketRecordOut] = []


class TicketListOut(BaseModel):
    total: int
    items: List[TicketOut]


class TicketStatsOut(BaseModel):
    total: int
    pending_assign: int
    pending_accept: int
    processing: int
    pending_confirm: int
    completed: int
    closed: int
    overdue: int
    near_sla: int
    mine_created: int
    mine_assigned: int
    satisfaction_avg: Optional[float] = None
    escalated: int = 0


class TicketSlaScanOut(BaseModel):
    scanned: int
    reminded_50: int
    reminded_80: int
    escalated_l1: int
    escalated_l2: int
