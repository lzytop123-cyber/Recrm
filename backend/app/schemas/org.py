"""组织员工 Schema。"""
from datetime import date, datetime, time
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    parent_id: Optional[int] = None
    description: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    parent_id: Optional[int] = None
    description: Optional[str] = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: Optional[str] = None
    parent_id: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    user_count: int = 0
    children: List["DepartmentOut"] = []


DepartmentOut.model_rebuild()


class EmployeeCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    real_name: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    department_id: Optional[int] = None
    role_ids: List[int] = []
    is_active: bool = True
    job_title: Optional[str] = Field(None, max_length=100)
    employee_no: Optional[str] = Field(None, max_length=50)
    hire_date: Optional[date] = None
    employment_status: Optional[str] = Field(None, max_length=20)
    manager_id: Optional[int] = None
    contract_type: Optional[str] = Field(None, max_length=50)
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    contract_status: Optional[str] = Field(None, max_length=30)
    archive_status: Optional[str] = Field(None, max_length=20)


class EmployeeUpdate(BaseModel):
    real_name: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    department_id: Optional[int] = None
    role_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None
    feishu_open_id: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    employee_no: Optional[str] = Field(None, max_length=50)
    hire_date: Optional[date] = None
    employment_status: Optional[str] = Field(None, max_length=20)
    manager_id: Optional[int] = None
    contract_type: Optional[str] = Field(None, max_length=50)
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    contract_status: Optional[str] = Field(None, max_length=30)
    archive_status: Optional[str] = Field(None, max_length=20)


class EmployeeResetPassword(BaseModel):
    password: str = Field(..., min_length=6, max_length=128)


class RoleBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    data_scope: str


class EmployeeTodoOut(BaseModel):
    key: str
    label: str
    status: str
    detail: Optional[str] = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    employee_no: Optional[str] = None
    department_id: Optional[int] = None
    is_active: bool
    feishu_open_id: Optional[str] = None
    feishu_user_id: Optional[str] = None
    hire_date: Optional[date] = None
    employment_status: Optional[str] = None
    manager_id: Optional[int] = None
    contract_type: Optional[str] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    contract_status: Optional[str] = None
    archive_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    department_name: Optional[str] = None
    manager_name: Optional[str] = None
    feishu_bound: bool = False
    identity_sync: str = "未绑定"
    today_status: Optional[str] = None
    todos: List[EmployeeTodoOut] = []
    roles: List[RoleBriefOut] = []


class EmployeeListOut(BaseModel):
    total: int
    items: List[EmployeeOut]


class OrgStatsOut(BaseModel):
    departments: int
    employees: int
    active_employees: int
    inactive_employees: int
    pending_onboard: int = 0
    contract_expiring_30d: int = 0
    today_attendance_ok: int = 0
    today_attendance_total: int = 0


class FeishuContactSyncResult(BaseModel):
    departments_created: int = 0
    departments_updated: int = 0
    employees_created: int = 0
    employees_updated: int = 0
    employees_bound: int = 0
    employees_matched: int = 0
    skipped: int = 0
    warnings: list[str] = []


class EmployeeHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    title: str
    detail: Optional[str] = None
    occurred_at: datetime
    created_at: datetime


class AttendanceDayOut(BaseModel):
    work_date: date
    status: str
    first_punch: Optional[time] = None
    last_punch: Optional[time] = None
    source: str = "飞书同步"


class AttendanceSummaryOut(BaseModel):
    month: str
    expected_days: int = 0
    actual_days: int = 0
    leave_days: int = 0
    out_days: int = 0
    exception_pending: int = 0
    today_status: Optional[str] = None
    days: List[AttendanceDayOut] = []


class FeishuAttendanceSyncRequest(BaseModel):
    user_id: Optional[int] = None
    month: Optional[str] = Field(None, description="YYYY-MM，默认当月")


class FeishuAttendanceSyncResult(BaseModel):
    users_synced: int = 0
    days_upserted: int = 0
    warnings: list[str] = []


class SyncStateItemOut(BaseModel):
    key: str
    status: str
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None


class FeishuSyncStatusOut(BaseModel):
    overall_status: str
    overall_label: str
    last_sync_at: Optional[datetime] = None
    items: List[SyncStateItemOut] = []
