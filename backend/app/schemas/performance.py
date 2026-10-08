"""绩效 Schema。"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.approval import ApprovalTimelineNode


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
    cycle_type: str = "monthly"
    default_template_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    pending_manager: int = 0
    pending_self: int = 0
    pending_appeals: int = 0
    completed_count: int = 0
    total_assessments: int = 0


class CycleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=30, description="period_label，如 2026-07")
    template_id: int
    cycle_type: str = Field("monthly", pattern="^(monthly|quarterly|yearly)$")
    scope: Optional[Dict[str, Any]] = None


class CycleGenerateRequest(BaseModel):
    scope: Optional[Dict[str, Any]] = None


class ItemRateIn(BaseModel):
    item_id: int
    self_score: Optional[Decimal] = Field(None, ge=0, le=120)
    self_comment: Optional[str] = None
    leader_score: Optional[Decimal] = Field(None, ge=0, le=120)
    leader_comment: Optional[str] = None


class ManagerRateRequest(BaseModel):
    okr_score: int = Field(..., ge=0, le=100)
    kpi_score: int = Field(..., ge=0, le=100)
    behavior_score: int = Field(..., ge=0, le=100)
    comment: str = Field(..., min_length=1)
    items: Optional[List[ItemRateIn]] = None


class SelfRateRequest(BaseModel):
    self_score: int = Field(..., ge=0, le=100)
    items: Optional[List[ItemRateIn]] = None


class AppealCreate(BaseModel):
    reason: str = Field(..., min_length=1)
    request_score: int = Field(..., ge=0, le=100)


class AppealResolveRequest(BaseModel):
    approve: bool
    resolution: str = Field(..., min_length=1)
    final_score: Optional[int] = Field(None, ge=0, le=100)


class AssessmentItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    template_item_id: Optional[int] = None
    order_no: int = 0
    name: str
    weight: Decimal
    data_source: str
    source_ref: Optional[str] = None
    target_value: Optional[str] = None
    score_rule: Optional[str] = None
    actual_value: Optional[str] = None
    display_actual: Optional[str] = None
    material_task_id: Optional[int] = None
    material_status: Optional[str] = None
    material_content: Optional[str] = None
    system_score: Optional[Decimal] = None
    self_score: Optional[Decimal] = None
    self_comment: Optional[str] = None
    leader_score: Optional[Decimal] = None
    leader_comment: Optional[str] = None
    final_score: Optional[Decimal] = None
    score_label: Optional[str] = None
    awarded_points: Optional[Decimal] = None
    handling_mode: Optional[str] = None
    scoring_type: Optional[str] = None


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_id: int
    user_id: int
    department_id: Optional[int] = None
    template_id: Optional[int] = None
    approval_instance_id: Optional[int] = None
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
    assessment_kind: str = "monthly"
    manager_comment: Optional[str] = None
    bonus_amount: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    user_name: Optional[str] = None
    department_name: Optional[str] = None
    job_title: Optional[str] = None
    adjustment_type: Optional[str] = None
    adjustment_reason: Optional[str] = None
    match_label: Optional[str] = None
    period_label: Optional[str] = None
    suggested_okr_score: Optional[int] = None
    suggested_okr_count: int = 0
    suggested_okr_period: Optional[str] = None
    items: List[AssessmentItemOut] = Field(default_factory=list)


class AssessmentDetailOut(AssessmentOut):
    timeline: List[ApprovalTimelineNode] = Field(default_factory=list)


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
    approval_instance_id: Optional[int] = None
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


class CycleDetailOut(BaseModel):
    cycle: PerformanceCycleOut
    assessments: List[AssessmentOut]
    grade_distribution: dict


class MineAssessmentsOut(BaseModel):
    assessments: List[AssessmentOut]
    trend: List[Dict[str, Any]] = Field(default_factory=list)


class TemplateItemIn(BaseModel):
    order_no: int = 0
    name: str = Field(..., min_length=1, max_length=120)
    # 旧模式：百分比权重（合计 100）；新模式：常镜像 max_points（可为 0，单值也可 >100）
    weight: Decimal = Field(..., ge=0)
    data_source: str
    source_ref: Optional[str] = None
    target_value: Optional[str] = None
    score_rule: Optional[str] = None
    hint: Optional[str] = None
    metric_key: Optional[str] = None
    max_points: Optional[Decimal] = None
    rule_config_json: Optional[str] = None
    indicator_definition_id: Optional[int] = None
    scoring_type: Optional[str] = None
    unit: Optional[str] = None
    handling_mode: Optional[str] = None
    evidence_policy_json: Optional[str] = None


class TemplateItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    order_no: int = 0
    name: str
    weight: Decimal
    data_source: str
    source_ref: Optional[str] = None
    target_value: Optional[str] = None
    score_rule: Optional[str] = None
    hint: Optional[str] = None
    metric_key: Optional[str] = None
    max_points: Optional[Decimal] = None
    rule_config_json: Optional[str] = None
    indicator_definition_id: Optional[int] = None
    scoring_type: Optional[str] = None
    unit: Optional[str] = None
    handling_mode: Optional[str] = None
    evidence_policy_json: Optional[str] = None


class TemplateScopeIn(BaseModel):
    department_id: int
    # 空字符串 = 该部门（及下级）全部岗位
    job_title: str = Field("", max_length=80)


class TemplateScopeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    department_id: int
    job_title: str = ""
    department_name: Optional[str] = None


class TemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    code: str = Field(..., min_length=1, max_length=60)
    cycle_type: str = Field("monthly", pattern="^(monthly|quarterly|yearly)$")
    rules_json: Optional[str] = None
    remark: Optional[str] = None
    items: List[TemplateItemIn]
    scopes: Optional[List[TemplateScopeIn]] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    eligibility_policy_json: Optional[str] = None
    scoring_mode: str = "legacy_weighted"
    engine_version: str = "legacy"
    nominal_total: Optional[Decimal] = None


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    remark: Optional[str] = None
    rules_json: Optional[str] = None
    items: Optional[List[TemplateItemIn]] = None
    scopes: Optional[List[TemplateScopeIn]] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    eligibility_policy_json: Optional[str] = None


class TemplateForkRequest(BaseModel):
    owner_dept_id: int
    name: Optional[str] = None
    code: Optional[str] = None


class TemplateApproveRequest(BaseModel):
    approve: bool = True
    comment: Optional[str] = None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    base_template_id: Optional[int] = None
    owner_type: str
    owner_dept_id: Optional[int] = None
    cycle_type: str
    rules_json: Optional[str] = None
    status: str
    approval_instance_id: Optional[int] = None
    remark: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    family_code: Optional[str] = None
    version: int = 1
    engine_version: str = "legacy"
    assessment_kind: str = "monthly"
    scoring_mode: str = "legacy_weighted"
    nominal_total: Optional[Decimal] = None
    definition_json: Optional[str] = None
    blocking_issues_json: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    published_at: Optional[datetime] = None
    published_by: Optional[int] = None
    eligibility_policy_json: Optional[str] = None
    items: List[TemplateItemOut] = Field(default_factory=list)
    scopes: List[TemplateScopeOut] = Field(default_factory=list)
    all_blocked: bool = False
