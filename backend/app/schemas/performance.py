"""绩效 Schema。"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PerformanceCycleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period_label: str
    rule_version: str
    status: str
    calibration_started: bool
    locked: bool
    locked_at: Optional[datetime] = None
    payroll_batch_no: Optional[str] = None
    payroll_created: bool
    payroll_reviewed: bool
    payroll_published: bool
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    pending_manager: int = 0
    pending_self: int = 0
    pending_appeals: int = 0
    completed_count: int = 0
    total_assessments: int = 0


class ManagerRateRequest(BaseModel):
    okr_score: int = Field(..., ge=0, le=100)
    kpi_score: int = Field(..., ge=0, le=100)
    behavior_score: int = Field(..., ge=0, le=100)
    comment: str = Field(..., min_length=1)


class SelfRateRequest(BaseModel):
    self_score: int = Field(..., ge=0, le=100)


class AppealCreate(BaseModel):
    reason: str = Field(..., min_length=1)
    request_score: int = Field(..., ge=0, le=100)


class AppealResolveRequest(BaseModel):
    approve: bool
    resolution: str = Field(..., min_length=1)
    final_score: Optional[int] = Field(None, ge=0, le=100)


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_id: int
    user_id: int
    department_id: Optional[int] = None
    self_score: Optional[int] = None
    okr_score: Optional[int] = None
    kpi_score: Optional[int] = None
    behavior_score: Optional[int] = None
    manager_score: Optional[int] = None
    final_score: Optional[int] = None
    grade: Optional[str] = None
    coefficient: Optional[Decimal] = None
    evidence_status: str
    status: str
    manager_comment: Optional[str] = None
    bonus_amount: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    user_name: Optional[str] = None
    department_name: Optional[str] = None
    suggested_okr_score: Optional[int] = None
    suggested_okr_count: int = 0
    suggested_okr_period: Optional[str] = None


class AppealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    reason: str
    request_score: int
    status: str
    resolution: Optional[str] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    user_name: Optional[str] = None
    department_name: Optional[str] = None
    current_score: Optional[int] = None


class PerformanceWorkbenchOut(BaseModel):
    cycle: PerformanceCycleOut
    assessments: List[AssessmentOut]
    appeals: List[AppealOut]
    grade_distribution: dict
