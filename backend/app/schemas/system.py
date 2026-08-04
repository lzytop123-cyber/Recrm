"""系统管理 Schema。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    module: Optional[str] = None
    description: Optional[str] = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None
    data_scope: str
    created_at: datetime
    updated_at: datetime
    permission_ids: List[int] = []
    permission_codes: List[str] = []
    user_count: int = 0


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    data_scope: Optional[str] = Field(None, pattern="^(company|department|personal)$")
    permission_ids: Optional[List[int]] = None


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    data_scope: str = Field(default="personal", pattern="^(company|department|personal)$")
    permission_ids: List[int] = []


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    module: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    ip: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime


class AuditLogListOut(BaseModel):
    total: int
    items: List[AuditLogOut]


class SystemStatsOut(BaseModel):
    roles: int
    permissions: int
    audit_logs: int
    users: int
