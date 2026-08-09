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


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    is_read: bool
    category: Optional[str] = None
    created_at: datetime


class SystemConfigCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: Optional[str] = None
    description: Optional[str] = None


class SystemConfigUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None


class SystemConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: Optional[str] = None
    description: Optional[str] = None
    updated_at: datetime
    updated_by: Optional[int] = None


class SystemDictionaryCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=80)
    name: str = Field(..., min_length=1, max_length=120)
    items_json: Optional[str] = None


class SystemDictionaryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    items_json: Optional[str] = None


class DictionaryItemOut(BaseModel):
    value: str
    label: str
    enabled: bool = True
    sort: int = 100


class SystemDictionaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    items_json: Optional[str] = None
    updated_at: datetime
    items: list[DictionaryItemOut] = []


class DelegationCreate(BaseModel):
    grantee_id: int
    scope: str = Field(default="all", max_length=120)
    reason: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None


class DelegationUpdate(BaseModel):
    scope: Optional[str] = Field(None, max_length=120)
    reason: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class DelegationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    granter_id: int
    grantee_id: int
    scope: str
    reason: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: datetime
    granter_name: Optional[str] = None
    grantee_name: Optional[str] = None


class ExportJobCreate(BaseModel):
    type: str = Field(..., min_length=1, max_length=80)


class ExportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    status: str
    file_path: Optional[str] = None
    requested_by: int
    created_at: datetime
    finished_at: Optional[datetime] = None
    error: Optional[str] = None


class ExportDownloadOut(BaseModel):
    id: int
    status: str
    download_url: Optional[str] = None
    message: str


class AccountOut(BaseModel):
    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    role_codes: List[str] = []
    department_id: Optional[int] = None


class AccountUpdate(BaseModel):
    real_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
