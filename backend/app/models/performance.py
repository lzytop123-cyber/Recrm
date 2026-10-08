"""
管人：绩效周期、月度考核、申诉、工资批次（精简闭环）。
对齐 PRD FR-070～079 骨架；KPI 运行期增量：指标库、范围、批次、材料与流转审计。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

CYCLE_STATUS_ASSESSING = "assessing"
CYCLE_STATUS_CALIBRATING = "calibrating"
CYCLE_STATUS_LOCKED = "locked"
CYCLE_STATUS_PAYROLL = "payroll"
CYCLE_STATUS_PUBLISHED = "published"

ASSESS_PENDING_SELF = "pending_self"
ASSESS_PENDING_MANAGER = "pending_manager"
ASSESS_PENDING_CALIBRATION = "pending_calibration"
ASSESS_APPEALING = "appealing"
ASSESS_COMPLETED = "completed"

# 简化考核流转（与旧 pending_self 等并存）
ASSESS_EMPLOYEE_PENDING = "employee_pending"
ASSESS_MANAGER_PENDING = "manager_pending"
ASSESS_HR_REVIEW_PENDING = "hr_review_pending"
# 入职考核专属：培训部评分节点（直属主管评完 → 培训部评分 → HR 复核）
ASSESS_TRAINING_PENDING = "training_pending"
ASSESS_EMPLOYEE_CONFIRM_PENDING = "employee_confirm_pending"
ASSESS_APPEAL_PENDING = "appeal_pending"

APPEAL_PENDING = "pending"
APPEAL_APPROVED = "approved"
APPEAL_REJECTED = "rejected"

TEMPLATE_STATUS_DRAFT = "draft"
TEMPLATE_STATUS_PENDING_REVIEW = "pending_review"
TEMPLATE_STATUS_RETURNED = "returned"
TEMPLATE_STATUS_APPROVED = "approved"
TEMPLATE_STATUS_PUBLISHED = "published"
TEMPLATE_STATUS_DISABLED = "disabled"
TEMPLATE_STATUS_ARCHIVED = "archived"

BATCH_STATUS_LAUNCHED = "launched"
BATCH_STATUS_COMPLETED = "completed"
BATCH_STATUS_CANCELLED = "cancelled"

MATERIAL_PENDING = "pending"
MATERIAL_DRAFT = "draft"
MATERIAL_SUBMITTED = "submitted"
MATERIAL_VERIFIED = "verified"
MATERIAL_RETURNED = "returned"


class PerformanceCycle(Base):
    __tablename__ = "performance_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_label: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    rule_version: Mapped[str] = mapped_column(String(30), default="V2026.07")
    status: Mapped[str] = mapped_column(String(30), default=CYCLE_STATUS_ASSESSING, index=True)
    calibration_started: Mapped[bool] = mapped_column(Boolean, default=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    payroll_batch_no: Mapped[Optional[str]] = mapped_column(String(50))
    payroll_created: Mapped[bool] = mapped_column(Boolean, default=False)
    payroll_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    payroll_published: Mapped[bool] = mapped_column(Boolean, default=False)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    cycle_type: Mapped[str] = mapped_column(
        String(20), default="monthly", index=True, comment="monthly | quarterly | yearly"
    )
    default_template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("performance_templates.id"), nullable=True
    )
    scope_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PerformanceAssessment(Base):
    __tablename__ = "performance_assessments"
    __table_args__ = (
        UniqueConstraint("cycle_id", "user_id", "instance_key", name="uq_assessment_instance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_cycles.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"))
    self_score: Mapped[Optional[int]] = mapped_column(Integer)
    okr_score: Mapped[Optional[int]] = mapped_column(Integer, comment="主管评：OKR达成 0-100")
    kpi_score: Mapped[Optional[int]] = mapped_column(Integer, comment="主管评：岗位KPI 0-100")
    behavior_score: Mapped[Optional[int]] = mapped_column(Integer, comment="主管评：协作与行为 0-100")
    manager_score: Mapped[Optional[int]] = mapped_column(Integer)
    final_score: Mapped[Optional[int]] = mapped_column(Integer)
    grade: Mapped[Optional[str]] = mapped_column(String(10))
    coefficient: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2))
    evidence_status: Mapped[str] = mapped_column(String(30), default="待补充")
    status: Mapped[str] = mapped_column(String(30), default=ASSESS_PENDING_SELF, index=True)
    template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("performance_templates.id"), nullable=True, index=True
    )
    approval_instance_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("approval_instances.id"), nullable=True, index=True
    )
    manager_comment: Mapped[Optional[str]] = mapped_column(Text)
    bonus_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    assessment_kind: Mapped[str] = mapped_column(String(30), default="monthly")
    instance_key: Mapped[str] = mapped_column(String(80), default="monthly_primary", nullable=False)
    engine_version: Mapped[str] = mapped_column(String(20), default="legacy")
    base_points: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    adjustment_points: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    total_points: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    grade_label: Mapped[Optional[str]] = mapped_column(String(20))
    performance_base_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    payroll_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    confirmed_revision: Mapped[Optional[int]] = mapped_column(Integer)
    template_snapshot_json: Mapped[Optional[str]] = mapped_column(Text)
    batch_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("performance_assessment_batches.id"), nullable=True, index=True
    )
    manager_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    current_handler_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    current_handler_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    person_snapshot_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PerformanceAppeal(Base):
    __tablename__ = "performance_appeals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_assessments.id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    request_score: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=APPEAL_PENDING, index=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text)
    resolved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approval_instance_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("approval_instances.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PerformanceTemplate(Base):
    """绩效指标模板（HR 基础 + 部门派生）"""

    __tablename__ = "performance_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    base_template_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("performance_templates.id"),
        nullable=True,
        comment="null=HR 基础模板；非 null=部门 fork 自哪份基础模板",
    )
    owner_type: Mapped[str] = mapped_column(
        String(20), default="hr", index=True, comment="hr | dept"
    )
    owner_dept_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True
    )
    cycle_type: Mapped[str] = mapped_column(
        String(20), default="monthly", comment="monthly | quarterly | yearly"
    )
    rules_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="HR 基础模板：权重上下限 / 数据源白名单 / 评分规则"
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="draft",
        index=True,
        comment="draft | pending_review | returned | approved | published | disabled | archived",
    )
    approval_instance_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("approval_instances.id"), nullable=True
    )
    remark: Mapped[Optional[str]] = mapped_column(Text)
    family_code: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("performance_templates.id"))
    engine_version: Mapped[str] = mapped_column(String(20), default="legacy")
    assessment_kind: Mapped[str] = mapped_column(String(30), default="monthly")
    scoring_mode: Mapped[str] = mapped_column(String(30), default="legacy_weighted")
    nominal_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    definition_json: Mapped[Optional[str]] = mapped_column(Text)
    blocking_issues_json: Mapped[Optional[str]] = mapped_column(Text)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    eligibility_policy_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PerformanceTemplateItem(Base):
    """模板下的一条指标定义"""

    __tablename__ = "performance_template_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_templates.id"), nullable=False, index=True
    )
    order_no: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    data_source: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, comment="system | okr | manual | self_manual"
    )
    source_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    target_value: Mapped[Optional[str]] = mapped_column(String(60))
    score_rule: Mapped[Optional[str]] = mapped_column(String(200))
    hint: Mapped[Optional[str]] = mapped_column(Text)
    metric_key: Mapped[Optional[str]] = mapped_column(String(80))
    max_points: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    rule_config_json: Mapped[Optional[str]] = mapped_column(Text)
    # 评分人标注：manager=直属主管 / training=培训部（空值按 manager 处理）
    evaluator: Mapped[Optional[str]] = mapped_column(String(20))
    indicator_definition_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("performance_indicator_definitions.id"), nullable=True, index=True
    )
    scoring_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    handling_mode: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    evidence_policy_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PerformanceAssessmentItem(Base):
    """一份考核单里的一条 KPI 项（从 template_item 复制 + 冻结实际值）"""

    __tablename__ = "performance_assessment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_assessments.id"), nullable=False, index=True
    )
    template_item_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("performance_template_items.id"),
        nullable=True,
        comment="追溯来源，只读",
    )
    order_no: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    data_source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_ref: Mapped[Optional[str]] = mapped_column(String(120))
    target_value: Mapped[Optional[str]] = mapped_column(String(60))
    score_rule: Mapped[Optional[str]] = mapped_column(String(200))
    actual_value: Mapped[Optional[str]] = mapped_column(String(60))
    system_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    self_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    self_comment: Mapped[Optional[str]] = mapped_column(Text)
    leader_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    leader_comment: Mapped[Optional[str]] = mapped_column(Text)
    final_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    metric_key: Mapped[Optional[str]] = mapped_column(String(80))
    max_points: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    awarded_points: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    data_state: Mapped[Optional[str]] = mapped_column(String(20))
    calculation_trace_json: Mapped[Optional[str]] = mapped_column(Text)
    # 评分人标注：manager=直属主管 / training=培训部（空值按 manager 处理）
    evaluator: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PerformanceTemplateAssignment(Base):
    __tablename__ = "performance_template_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("performance_templates.id"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"))
    job_title: Mapped[Optional[str]] = mapped_column(String(80))
    assessment_kind: Mapped[str] = mapped_column(String(30), default="monthly")
    priority: Mapped[int] = mapped_column(Integer, default=0)


class PerformanceMetricFact(Base):
    __tablename__ = "performance_metric_facts"
    __table_args__ = (
        UniqueConstraint("metric_key", "owner_id", "source_record_id", name="uq_metric_fact_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    occurred_on: Mapped[Optional[str]] = mapped_column(String(20))
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4))
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    source_record_id: Mapped[str] = mapped_column(String(80), nullable=False)
    project_ref: Mapped[Optional[str]] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    revision: Mapped[int] = mapped_column(Integer, default=1)


class PerformanceImportBatch(Base):
    __tablename__ = "performance_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="preview")
    rows_json: Mapped[Optional[str]] = mapped_column(Text)
    errors_json: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))


class PerformanceStageCase(Base):
    __tablename__ = "performance_stage_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    hire_event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(10), nullable=False)
    role_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    due_at: Mapped[Optional[str]] = mapped_column(String(20))
    assessment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("performance_assessments.id"))


class PerformanceObservationCase(Base):
    __tablename__ = "performance_observation_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="open")
    end_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    retriggered: Mapped[bool] = mapped_column(Boolean, default=False)
    hr_todo: Mapped[Optional[str]] = mapped_column(String(200))


class PerformanceFeedbackRecord(Base):
    __tablename__ = "performance_feedback_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    form_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    reviewer_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    status: Mapped[str] = mapped_column(String(20), default="pending")


class PerformanceIndicatorDefinition(Base):
    """可复用指标定义库；加入模板时复制快照到 template_item。"""

    __tablename__ = "performance_indicator_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    scoring_type: Mapped[str] = mapped_column(String(30), nullable=False)
    default_target: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    data_source_code: Mapped[str] = mapped_column(String(60), nullable=False)
    handling_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_policy_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PerformanceTemplateScope(Base):
    """模板适用部门/岗位范围（结构化，不依赖名称文字）。"""

    __tablename__ = "performance_template_scopes"
    __table_args__ = (
        UniqueConstraint("template_id", "department_id", "job_title", name="uq_template_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_templates.id"), nullable=False, index=True
    )
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False)
    job_title: Mapped[str] = mapped_column(String(80), nullable=False)


class PerformanceAssessmentBatch(Base):
    """按模板一次发起的考核批次。"""

    __tablename__ = "performance_assessment_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_cycles.id"), nullable=False, index=True
    )
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_templates.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default=BATCH_STATUS_LAUNCHED, index=True)
    employee_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    manager_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hr_review_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirm_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hr_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PerformanceMaterialTask(Base):
    """考核材料补充任务（由模板要求 + 事实缺失动态生成）。"""

    __tablename__ = "performance_material_tasks"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id",
            "assessment_item_id",
            "source_record_type",
            "source_record_id",
            name="uq_material_task_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_assessments.id"), nullable=False, index=True
    )
    assessment_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_assessment_items.id"), nullable=False, index=True
    )
    source_record_type: Mapped[str] = mapped_column(String(60), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    existing_data_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    missing_fields_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirement_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    employee_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=MATERIAL_PENDING, index=True)
    return_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class PerformanceActionLog(Base):
    """考核状态流转审计。"""

    __tablename__ = "performance_action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_assessments.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

