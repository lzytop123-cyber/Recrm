"""立项资源确认 schemas。"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ResourceConfirmRequest(BaseModel):
    action: str = Field(..., description="accept / adjust / reject")
    confirmed_user_id: Optional[int] = None
    planned_hours: Optional[Decimal] = Field(None, gt=0, le=9999)
    note: Optional[str] = Field(None, max_length=500)


class ResourceRoleMemberOut(BaseModel):
    id: int
    name: str
    department_name: Optional[str] = None
    job_title: Optional[str] = None


class ResourceRoleOptionOut(BaseModel):
    role_name: str
    department_id: Optional[int] = None
    member_count: int = 0
    members: List[ResourceRoleMemberOut] = Field(default_factory=list)


class ResourceRoleOptionsOut(BaseModel):
    roles: List[ResourceRoleOptionOut]
    employees: List[ResourceRoleMemberOut]
    source: str = Field(description="feishu_department / catalog_fallback")
    hint: Optional[str] = None


class ResourceRoleAssignment(BaseModel):
    role_name: str = Field(..., min_length=1, max_length=80)
    suggested_user_id: Optional[int] = None
    planned_hours: Optional[Decimal] = Field(None, gt=0, le=9999)


class ProjectResourceNeedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    project_no: Optional[str] = None
    project_name: Optional[str] = None
    role_name: str
    department_name: str
    department_id: Optional[int] = None
    suggested_user_id: Optional[int] = None
    suggested_user_name: Optional[str] = None
    confirmed_user_id: Optional[int] = None
    confirmed_user_name: Optional[str] = None
    planned_hours: Decimal
    status: str
    schedule_status: str
    note: Optional[str] = None
    handler_role: Optional[str] = None
    confirmed_by: Optional[int] = None
    confirmed_by_name: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ProjectResourceNeedListOut(BaseModel):
    items: List[ProjectResourceNeedOut]
    total: int
    pending_count: int


class ProjectHoursBudgetOut(BaseModel):
    """资源承诺工时 vs 任务计划/实际工时。"""

    project_id: int
    resource_budget_hours: Decimal = Field(description="未拒绝的资源计划投入合计")
    resource_accepted_hours: Decimal = Field(description="已确认的资源计划投入合计")
    task_planned_hours: Decimal = Field(description="任务计划工时合计")
    task_actual_hours: Decimal = Field(description="任务实际工时合计")
    remaining_hours: Decimal = Field(description="资源预算剩余（可再拆任务）")
    over_budget: bool = Field(description="任务计划是否已超过资源承诺")
