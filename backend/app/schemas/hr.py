"""人事闭环 schemas。"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LaborContractCreate(BaseModel):
    employee_id: int
    contract_type: str = Field(..., min_length=1, max_length=30)
    signed_on: date
    start_date: date
    end_date: Optional[date] = None
    trial_start: Optional[date] = None
    trial_end: Optional[date] = None
    status: str = "pending_sign"
    file_path: Optional[str] = None
    attachment: Optional[str] = Field(None, max_length=255, description="扫描件文件名，展示用")
    attachment_path: Optional[str] = Field(None, max_length=500, description="扫描件存储路径，等同 file_path")
    remark: Optional[str] = Field(None, max_length=300)


class LaborContractUpdate(BaseModel):
    contract_type: Optional[str] = Field(None, max_length=30)
    signed_on: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    trial_start: Optional[date] = None
    trial_end: Optional[date] = None
    status: Optional[str] = None
    file_path: Optional[str] = None
    attachment: Optional[str] = Field(None, max_length=255)
    attachment_path: Optional[str] = Field(None, max_length=500)
    remark: Optional[str] = Field(None, max_length=300)


class LaborContractRenew(BaseModel):
    signed_on: date
    start_date: date
    end_date: Optional[date] = None
    contract_type: Optional[str] = None
    file_path: Optional[str] = None
    attachment: Optional[str] = Field(None, max_length=255)
    attachment_path: Optional[str] = Field(None, max_length=500)
    remark: Optional[str] = Field(None, max_length=300)


class LaborContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_name: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    contract_type: str
    signed_on: date
    start_date: date
    end_date: Optional[date] = None
    trial_start: Optional[date] = None
    trial_end: Optional[date] = None
    status: str
    file_path: Optional[str] = None
    attachment: Optional[str] = None
    attachment_path: Optional[str] = None
    version: int
    supersedes_id: Optional[int] = None
    remark: Optional[str] = None
    warn_kind: Optional[str] = None
    days_left: Optional[int] = None
    renew_pending: bool = False
    created_at: datetime

    @model_validator(mode="after")
    def fill_attachment_fields(self):
        path = (self.attachment_path or self.file_path or "").strip() or None
        name = (self.attachment or "").strip() or None
        if path and not name:
            name = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or None
        if name and not path:
            # 仅有文件名时仍返回展示名，路径留给前端走 /contracts/{id}/file
            pass
        self.attachment = name
        self.attachment_path = path
        if path and not self.file_path:
            self.file_path = path
        return self


class LaborContractListOut(BaseModel):
    total: int
    items: List[LaborContractOut]


class TransferCreate(BaseModel):
    employee_id: int
    to_department_id: int
    effective_on: date
    reason: str = Field(..., min_length=1, max_length=300)
    job_title: Optional[str] = Field(None, max_length=100)


class TransferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_name: Optional[str] = None
    from_department_id: Optional[int] = None
    to_department_id: int
    effective_on: date
    reason: str
    job_title: Optional[str] = None
    status: str
    approval_instance_id: Optional[int] = None
    created_at: datetime


class TransferListOut(BaseModel):
    total: int
    items: List[TransferOut]


class ResignationCreate(BaseModel):
    employee_id: int
    last_working_day: date
    reason: str = Field(..., min_length=1, max_length=300)


class HandoverItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    ref_id: int
    title: str
    status: str
    assignee_id: Optional[int] = None
    confirmed_at: Optional[datetime] = None


class HandoverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resignation_id: int
    employee_id: int
    status: str
    items: List[HandoverItemOut] = []
    open_items: List[dict] = []
    can_complete: bool = False
    signed_by: Optional[int] = None
    signed_at: Optional[datetime] = None


class HandoverAssignIn(BaseModel):
    assignee_id: int


class ResignationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_name: Optional[str] = None
    last_working_day: date
    reason: str
    status: str
    approval_instance_id: Optional[int] = None
    handover_id: Optional[int] = None
    created_at: datetime


class ResignationListOut(BaseModel):
    total: int
    items: List[ResignationOut]


class LeaveRequestCreate(BaseModel):
    leave_type: str = Field(..., min_length=1, max_length=30)
    start_date: date
    end_date: date
    days: Decimal = Field(..., gt=0)
    reason: Optional[str] = Field(None, max_length=300)
    employee_id: Optional[int] = None


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_name: Optional[str] = None
    leave_type: str
    start_date: date
    end_date: date
    days: Decimal
    reason: Optional[str] = None
    status: str
    approval_instance_id: Optional[int] = None
    created_at: datetime


class LeaveRequestListOut(BaseModel):
    total: int
    items: List[LeaveRequestOut]


class LeaveBalancePatch(BaseModel):
    quota: Optional[Decimal] = None
    used: Optional[Decimal] = None
    remaining: Optional[Decimal] = None
    remark: Optional[str] = Field(None, max_length=300)


class LeaveBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_name: Optional[str] = None
    leave_type: str
    year: int
    quota: Decimal
    used: Decimal
    remaining: Decimal
    remark: Optional[str] = None


class AttendanceMonthlyOut(BaseModel):
    month: str
    user_id: int
    expected_days: int = 0
    actual_days: int = 0
    leave_days: int = 0
    overtime_days: Decimal = Decimal("0")
    field_days: int = 0
    makeup_days: int = 0
    exception_pending: int = 0
    approved_leaves: List[LeaveRequestOut] = []


class PayslipItem(BaseModel):
    name: str
    amount: Decimal


class PayslipCorrectIn(BaseModel):
    base_amount: Optional[Decimal] = None
    performance_amount: Optional[Decimal] = None
    adjustment_amount: Optional[Decimal] = None
    items: Optional[List[PayslipItem]] = None
    remark: Optional[str] = None


class PayslipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_name: Optional[str] = None
    cycle_id: Optional[int] = None
    period_label: str
    version: int
    status: str
    base_amount: Decimal
    performance_amount: Decimal
    adjustment_amount: Decimal
    total_amount: Decimal
    items: List[PayslipItem] = []
    supersedes_id: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: datetime


class PayslipListOut(BaseModel):
    total: int
    items: List[PayslipOut]


class PayslipDownloadOut(BaseModel):
    expires_in: int
    filename: str
    content: str


class HrDashboardOut(BaseModel):
    headcount: int = 0
    hired_this_month: int = 0
    resigned_this_month: int = 0
    contracts_expiring_90: int = 0
    contracts_expiring_30: int = 0
    contracts_expiring_7: int = 0
    timesheet_hours: Decimal = Decimal("0")
    open_handovers: int = 0
    payslip_total: Decimal = Decimal("0")
