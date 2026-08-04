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
