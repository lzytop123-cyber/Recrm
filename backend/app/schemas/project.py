"""项目管理请求/响应 Schema。"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.project_resource import ResourceRoleAssignment


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    contract_id: int
    customer_id: Optional[int] = None
    project_type: str = Field(default="other")
    manager_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    scope_desc: Optional[str] = None
    remark: Optional[str] = None
    payment_verified: bool = False
    handoff_complete: bool = False
    contact_confirmed: bool = False
    business_owner_id: Optional[int] = None
    # 立项所需角色（飞书职位 + 指定人）；空则按交付类型默认
    resource_roles: Optional[List[ResourceRoleAssignment]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    contract_id: Optional[int] = None
    customer_id: Optional[int] = None
    project_type: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    manager_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    scope_desc: Optional[str] = None
    remark: Optional[str] = None
    payment_verified: Optional[bool] = None
    handoff_complete: Optional[bool] = None
    contact_confirmed: Optional[bool] = None
    business_owner_id: Optional[int] = None
    baseline_version: Optional[str] = None


class ProjectTerminateRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class ProjectAcceptRequest(BaseModel):
    result: str = Field(..., description="pass/conditional/fail")
    accepted_at: Optional[date] = None
    method: str = Field(..., min_length=1, max_length=50)
    owner_id: Optional[int] = None
    conclusion: str = Field(..., min_length=1)
    leftover_summary: Optional[str] = None
    attachment: str = Field(..., min_length=1, max_length=255)
    attachment_path: Optional[str] = Field(None, max_length=500)


class ProjectAcceptanceReviewRequest(BaseModel):
    remark: Optional[str] = None


class ProjectFinanceCheckRequest(BaseModel):
    remark: Optional[str] = None


class ProjectFinanceCheckReviewRequest(BaseModel):
    remark: Optional[str] = None


class ProjectLeftoverCloseRequest(BaseModel):
    closed: bool = True


class MilestoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    deadline: Optional[date] = None
    actual_date: Optional[date] = None
    role: Optional[str] = Field(None, max_length=50)
    deliverable: Optional[str] = Field(None, max_length=200)
    evidence: Optional[str] = Field(None, max_length=200)
    sort_order: int = 0
    remark: Optional[str] = None


class MilestoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    deadline: Optional[date] = None
    actual_date: Optional[date] = None
    role: Optional[str] = None
    deliverable: Optional[str] = None
    evidence: Optional[str] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None
    remark: Optional[str] = None


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    deadline: Optional[date] = None
    actual_date: Optional[date] = None
    role: Optional[str] = None
    deliverable: Optional[str] = None
    evidence: Optional[str] = None
    evidence_status: str = "none"
    evidence_confirmed_by: Optional[int] = None
    evidence_confirmed_at: Optional[datetime] = None
    evidence_reject_reason: Optional[str] = None
    evidence_confirmed_by_name: Optional[str] = None
    status: str
    sort_order: int
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    task_total: int = 0
    task_done: int = 0
    can_complete: bool = False
    next_action: Optional[str] = None


class MilestoneEvidenceReview(BaseModel):
    action: str = Field(..., description="confirm/reject")
    reason: Optional[str] = Field(None, max_length=200)


class ProjectTaskCreate(BaseModel):
    project_id: int
    title: str = Field(..., min_length=1, max_length=200)
    criteria: Optional[str] = None
    milestone_id: Optional[int] = None
    assignee_id: Optional[int] = None
    due_date: Optional[date] = None
    planned_hours: Optional[Decimal] = Field(default=Decimal("0"), ge=0)
    remark: Optional[str] = None


class ProjectTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    criteria: Optional[str] = None
    milestone_id: Optional[int] = None
    assignee_id: Optional[int] = None
    due_date: Optional[date] = None
    planned_hours: Optional[Decimal] = Field(None, ge=0)
    actual_hours: Optional[Decimal] = Field(None, ge=0)
    status: Optional[str] = None
    remark: Optional[str] = None


class ProjectTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_no: str
    project_id: int
    milestone_id: Optional[int] = None
    title: str
    criteria: Optional[str] = None
    assignee_id: Optional[int] = None
    department_id: Optional[int] = None
    due_date: Optional[date] = None
    planned_hours: Optional[Decimal] = None
    actual_hours: Optional[Decimal] = None
    status: str
    ticket_id: Optional[int] = None
    remark: Optional[str] = None
    creator_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    project_no: Optional[str] = None
    project_name: Optional[str] = None
    milestone_name: Optional[str] = None
    assignee_name: Optional[str] = None
    department_name: Optional[str] = None
    due_status: Optional[str] = None  # ok/overdue/done
    schedule_booked: int = 0  # 待确认/已确认/进行中
    schedule_completed: int = 0  # 已完成排期数


class ProjectTaskListOut(BaseModel):
    total: int
    items: List[ProjectTaskOut]


class ProjectTaskStatsOut(BaseModel):
    mine: int
    overdue: int
    planned_hours: Decimal
    actual_hours: Decimal
    linked_tickets: int = 0


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_no: str
    name: str
    contract_id: Optional[int] = None
    customer_id: Optional[int] = None
    project_type: str
    status: str
    progress: int
    manager_id: Optional[int] = None
    creator_id: Optional[int] = None
    department_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    scope_desc: Optional[str] = None
    terminate_reason: Optional[str] = None
    remark: Optional[str] = None
    payment_verified: bool = False
    handoff_complete: bool = False
    contact_confirmed: bool = False
    business_owner_id: Optional[int] = None
    baseline_version: Optional[str] = None
    acceptance_result: Optional[str] = None
    accepted_at: Optional[date] = None
    acceptance_method: Optional[str] = None
    acceptance_owner_id: Optional[int] = None
    acceptance_conclusion: Optional[str] = None
    leftover_summary: Optional[str] = None
    acceptance_approval_status: str = "none"
    acceptance_submitted_by: Optional[int] = None
    acceptance_submitted_at: Optional[datetime] = None
    acceptance_approved_by: Optional[int] = None
    acceptance_approved_at: Optional[datetime] = None
    acceptance_reject_reason: Optional[str] = None
    acceptance_attachment: Optional[str] = None
    acceptance_attachment_path: Optional[str] = None
    finance_check_passed: bool = False
    finance_check_status: str = "none"
    finance_check_submitted_by: Optional[int] = None
    finance_check_submitted_at: Optional[datetime] = None
    finance_check_approved_by: Optional[int] = None
    finance_check_approved_at: Optional[datetime] = None
    finance_check_reject_reason: Optional[str] = None
    leftover_closed: bool = False
    created_at: datetime
    updated_at: datetime
    contract_no: Optional[str] = None
    contract_title: Optional[str] = None
    customer_name: Optional[str] = None
    manager_name: Optional[str] = None
    creator_name: Optional[str] = None
    business_owner_name: Optional[str] = None
    acceptance_owner_name: Optional[str] = None
    acceptance_submitted_by_name: Optional[str] = None
    acceptance_approved_by_name: Optional[str] = None
    # 派生
    contract_active_ok: bool = False
    payment_received_ok: bool = False
    health: Optional[str] = None  # normal/attention/risk
    next_node: Optional[str] = None
    milestone_done: int = 0
    milestone_total: int = 0


class ProjectDetailOut(ProjectOut):
    milestones: List[MilestoneOut] = []


class ProjectListOut(BaseModel):
    total: int
    items: List[ProjectOut]


class ProjectStatsOut(BaseModel):
    total: int
    initiating: int
    planning: int
    executing: int
    accepting: int
    accepted: int
    completed: int
    terminated: int
    mine: int
    high_risk: int = 0
    leftover: int = 0


class DepartmentMonitorMember(BaseModel):
    user_id: int
    name: str
    planned_tasks: int = 0
    done_tasks: int = 0
    overdue_tasks: int = 0
    planned_hours: Decimal = Decimal("0")
    actual_hours: Decimal = Decimal("0")
    hours_complete_rate: Decimal = Decimal("0")
    open_tickets: int = 0


class DepartmentMonitorOut(BaseModel):
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    health_score: int = 0
    on_time_rate: Decimal = Decimal("0")
    hours_complete_rate: Decimal = Decimal("0")
    overdue_tasks: int = 0
    missing_hours: int = 0
    members: List[DepartmentMonitorMember] = []
