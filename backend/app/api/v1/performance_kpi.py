"""七类考核接口。旧加权模板仍走原路由。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_current_user
from app.core.rbac import collect_permission_codes
from app.database import get_db
from app.models.user import User
from app.services import performance_kpi

router = APIRouter(prefix="/performance", tags=["绩效KPI"])
MANAGE = PermissionChecker(["kpi:template:manage"])
# 入职考核：培训部负责人(kpi:onboarding:manage)或 HR/管理员均可开案
ONBOARD_MANAGE = PermissionChecker(["kpi:onboarding:manage", "kpi:template:manage"], any_of=True)
BATCH_VIEW = PermissionChecker(["kpi:template:manage", "kpi:view"], any_of=True)
HISTORY_VIEW = PermissionChecker(["kpi:template:manage", "kpi:view", "okr:view"], any_of=True)


class ImportIn(BaseModel):
    csv_text: str
    employees: dict[str, int]


class ActualsIn(BaseModel):
    actuals: dict[str, str]


class AssignmentIn(BaseModel):
    template_id: int
    user_id: Optional[int] = None
    department_id: Optional[int] = None
    job_title: Optional[str] = None
    assessment_kind: str = "monthly"


class ReviewIn(BaseModel):
    status: str


class StageIn(BaseModel):
    user_id: int
    stage: str
    role_kind: str
    hire_event_id: Optional[int] = None
    cycle_id: Optional[int] = None
    due_at: Optional[str] = None


class ObservationIn(BaseModel):
    user_id: int
    end_score: Optional[str] = None
    retriggered: bool = False


class FeedbackIn(BaseModel):
    form_type: str
    subject_user_id: int
    reviewer_user_id: Optional[int] = None
    anonymous: bool = False
    score: Optional[str] = None


class ArchiveIn(BaseModel):
    fraud: bool = False


class IndicatorCreateIn(BaseModel):
    metric_key: str
    name: str
    department_id: Optional[int] = None
    job_title: Optional[str] = None
    scoring_type: str
    default_target: Optional[str] = None
    unit: str = ""
    data_source_code: str
    handling_mode: str
    rule_config: Optional[dict] = None
    evidence_policy: Optional[dict] = None
    status: str = "draft"


class IndicatorUpdateIn(BaseModel):
    name: Optional[str] = None
    department_id: Optional[int] = None
    job_title: Optional[str] = None
    scoring_type: Optional[str] = None
    default_target: Optional[str] = None
    unit: Optional[str] = None
    data_source_code: Optional[str] = None
    handling_mode: Optional[str] = None
    rule_config: Optional[dict] = None
    evidence_policy: Optional[dict] = None
    status: Optional[str] = None


class AddIndicatorToTemplateIn(BaseModel):
    indicator_definition_id: int
    weight: str = "10"
    order_no: int = 0


class MatchPersonnelIn(BaseModel):
    cycle_id: int
    template_id: int


class MatchPersonnelMultiIn(BaseModel):
    cycle_id: int
    template_ids: list[int]


class BatchPersonIn(BaseModel):
    user_id: int
    selected: bool = True
    adjustment_reason: Optional[str] = None


class AssessmentBatchIn(BaseModel):
    cycle_id: int
    template_id: int
    people: list[BatchPersonIn]
    employee_due_at: str
    manager_due_at: str
    hr_review_required: bool = False
    hr_review_due_at: Optional[str] = None
    confirm_due_at: str


class MultiBatchItemIn(BaseModel):
    template_id: int
    people: list[BatchPersonIn]


class AssessmentMultiBatchIn(BaseModel):
    cycle_id: int
    batches: list[MultiBatchItemIn]
    employee_due_at: str
    manager_due_at: str
    hr_review_required: bool = False
    hr_review_due_at: Optional[str] = None
    confirm_due_at: str


class AssessmentBatchLaunchIn(BaseModel):
    """兼容单模板与多模板两种发起体。

    - 单模板：{cycle_id, template_id, people, ...}
    - 多模板：{cycle_id, batches:[{template_id, people}], ...}（也可用 /assessment-batches/multi）
    """

    cycle_id: int
    employee_due_at: str
    manager_due_at: str
    confirm_due_at: str
    hr_review_required: bool = False
    hr_review_due_at: Optional[str] = None
    template_id: Optional[int] = None
    people: Optional[list[BatchPersonIn]] = None
    batches: Optional[list[MultiBatchItemIn]] = None

    def as_single(self) -> AssessmentBatchIn:
        if self.template_id is None or self.people is None:
            raise HTTPException(
                status_code=422,
                detail="单模板发起需要 template_id 与 people",
            )
        return AssessmentBatchIn(
            cycle_id=self.cycle_id,
            template_id=self.template_id,
            people=self.people,
            employee_due_at=self.employee_due_at,
            manager_due_at=self.manager_due_at,
            hr_review_required=self.hr_review_required,
            hr_review_due_at=self.hr_review_due_at,
            confirm_due_at=self.confirm_due_at,
        )

    def as_multi(self) -> AssessmentMultiBatchIn:
        if not self.batches:
            raise HTTPException(status_code=422, detail="多模板发起需要 batches")
        return AssessmentMultiBatchIn(
            cycle_id=self.cycle_id,
            batches=self.batches,
            employee_due_at=self.employee_due_at,
            manager_due_at=self.manager_due_at,
            hr_review_required=self.hr_review_required,
            hr_review_due_at=self.hr_review_due_at,
            confirm_due_at=self.confirm_due_at,
        )


@router.get("/configuration", summary="绩效前端配置元数据")
def performance_configuration(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_indicator_catalog as catalog

    return catalog.build_configuration(db, user)


@router.post("/assessments/match-personnel", summary="按模板匹配考核人员")
def match_personnel(
    payload: MatchPersonnelIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    from app.services import performance_personnel_matcher as matcher

    return matcher.match_personnel(db, cycle_id=payload.cycle_id, template_id=payload.template_id)


@router.post("/assessments/match-personnel-multi", summary="按多个模板匹配考核人员")
def match_personnel_multi(
    payload: MatchPersonnelMultiIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    from app.services import performance_assessment_batch as batch_svc

    return batch_svc.match_personnel_multi(
        db, cycle_id=payload.cycle_id, template_ids=payload.template_ids
    )


@router.post("/assessment-batches", summary="批量发起考核（单模板，兼容多模板 batches）")
def create_assessment_batch(
    payload: AssessmentBatchLaunchIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(MANAGE)],
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
) -> dict:
    from app.services import performance_assessment_batch as batch_svc

    key = idempotency_key or ""
    # 前端若误把多模板体打到本接口，按 batches 自动走 multi
    if payload.batches:
        return batch_svc.create_multi_assessment_batches(
            db,
            user,
            payload.as_multi().model_dump(),
            idempotency_key=key,
        )
    return batch_svc.create_assessment_batch(
        db,
        user,
        payload.as_single().model_dump(),
        idempotency_key=key,
    )


@router.post("/assessment-batches/multi", summary="多部门一次发起考核")
def create_assessment_batches_multi(
    payload: AssessmentMultiBatchIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(MANAGE)],
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
) -> dict:
    from app.services import performance_assessment_batch as batch_svc

    return batch_svc.create_multi_assessment_batches(
        db,
        user,
        payload.model_dump(),
        idempotency_key=idempotency_key or "",
    )


@router.get("/assessment-batches", summary="周期内批次进度看板")
def list_assessment_batches(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(BATCH_VIEW)],
    cycle_id: Optional[int] = Query(None, description="不传时优先本月周期，没有则取最近一条"),
) -> dict:
    from app.services import performance_assessment_batch as batch_svc

    resolved = batch_svc.resolve_list_cycle_id(db, cycle_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="没有可用的考核周期")
    return batch_svc.list_cycle_batch_progress(db, resolved, user)


@router.get("/assessment-history", summary="往期考核")
def list_assessment_history(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(HISTORY_VIEW)],
    cycle_id: Optional[int] = Query(None, description="不传时取可见范围内最近一期"),
    department: Optional[str] = Query(None, description="按考核时部门快照筛选"),
    q: Optional[str] = Query(None, description="搜索员工、岗位或主管"),
    sort: str = Query("default", pattern="^(default|high|low)$"),
) -> dict:
    from app.services import performance_assessment_batch as batch_svc

    return batch_svc.list_assessment_history(
        db, user, cycle_id=cycle_id, department=department, q=q, sort=sort
    )


@router.get("/assessment-batches/{batch_id}", summary="批次进度与人员名单")
def get_assessment_batch(
    batch_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(BATCH_VIEW)],
) -> dict:
    from app.services import performance_assessment_batch as batch_svc

    return batch_svc.get_batch_progress(db, batch_id, user)


@router.get("/indicator-definitions", summary="指标库列表")
def list_indicator_definitions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
    department_id: Optional[int] = None,
    job_title: Optional[str] = None,
    status: Optional[str] = "active",
) -> list:
    from app.services import performance_indicator_catalog as catalog

    rows = catalog.list_indicators(db, department_id=department_id, job_title=job_title, status=status)
    return [catalog.indicator_out(r) for r in rows]


@router.post("/indicator-definitions", summary="新建指标定义")
def create_indicator_definition(
    payload: IndicatorCreateIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(MANAGE)],
) -> dict:
    from app.services import performance_indicator_catalog as catalog

    row = catalog.create_indicator(db, user, payload.model_dump())
    return catalog.indicator_out(row)


@router.patch("/indicator-definitions/{indicator_id}", summary="更新指标定义")
def patch_indicator_definition(
    indicator_id: int,
    payload: IndicatorUpdateIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    from app.services import performance_indicator_catalog as catalog

    row = catalog.update_indicator(db, indicator_id, payload.model_dump(exclude_unset=True))
    return catalog.indicator_out(row)


@router.post("/indicator-definitions/{indicator_id}/disable", summary="停用指标定义")
def disable_indicator_definition(
    indicator_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    from app.services import performance_indicator_catalog as catalog

    row = catalog.disable_indicator(db, indicator_id)
    return catalog.indicator_out(row)


@router.delete("/indicator-definitions/{indicator_id}", summary="删除指标定义")
def delete_indicator_definition(
    indicator_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    from app.services import performance_indicator_catalog as catalog

    catalog.delete_indicator(db, indicator_id)
    return {"ok": True}


@router.post("/templates/{template_id}/items/from-indicator", summary="从指标库加入模板项快照")
def add_template_item_from_indicator(
    template_id: int,
    payload: AddIndicatorToTemplateIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    from decimal import Decimal

    from app.services import performance_indicator_catalog as catalog

    item = catalog.add_indicator_to_template(
        db,
        template_id=template_id,
        indicator_id=payload.indicator_definition_id,
        weight=Decimal(payload.weight),
        order_no=payload.order_no,
    )
    return {
        "id": item.id,
        "template_id": item.template_id,
        "order_no": item.order_no,
        "name": item.name,
        "metric_key": item.metric_key,
        "indicator_definition_id": item.indicator_definition_id,
        "scoring_type": item.scoring_type,
        "handling_mode": item.handling_mode,
        "max_points": str(item.max_points) if item.max_points is not None else None,
        "weight": str(item.weight),
        "target_value": item.target_value,
        "unit": item.unit,
        "score_rule": item.score_rule,
        "hint": item.hint,
    }


@router.post("/templates/{template_id}/validate", summary="校验新规则模板")
def validate_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.validate_template(db, template_id)


@router.post("/templates/{template_id}/revise", summary="从当前版生成下一草稿")
def revise_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.revise_template(db, template_id)


@router.post("/templates/{template_id}/preview", summary="样例实际值试算")
def preview_template(
    template_id: int,
    payload: ActualsIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.preview_template(db, template_id, payload.actuals)


@router.get("/template-assignments", summary="模板分配")
def list_assignments(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> list:
    return performance_kpi.list_assignments(db)


@router.post("/template-assignments", summary="新增模板分配")
def create_assignment(
    payload: AssignmentIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.create_assignment(db, payload.model_dump())


@router.get("/metric-sources", summary="指标数据源目录")
def metric_sources(_: Annotated[User, Depends(MANAGE)]) -> list:
    return performance_kpi.METRIC_SOURCES


@router.get("/metric-facts", summary="指标事实")
def list_facts(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list:
    codes = collect_permission_codes(user)
    manage = "*" in codes or "kpi:template:manage" in codes
    return performance_kpi.list_facts(db, user, manage=manage)


@router.post("/metric-facts/{fact_id}/review", summary="审核指标事实")
def review_fact(
    fact_id: int,
    payload: ReviewIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.review_fact(db, fact_id, payload.status)


@router.post("/imports/preview", summary="CSV 导入预览")
def preview_import(
    payload: ImportIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.preview_import(db, user, payload.csv_text, users_by_name=payload.employees)


@router.post("/imports/{batch_id}/confirm", summary="确认导入")
def confirm_import(
    batch_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.confirm_import(db, user, batch_id)


@router.post("/assessments/{assessment_id}/preview-score", summary="考核单试算")
def preview_score(
    assessment_id: int,
    payload: ActualsIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.preview_assessment(db, assessment_id, payload.actuals)


@router.post("/assessments/{assessment_id}/refresh-data", summary="刷新数据版本")
def refresh_data(
    assessment_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.refresh_assessment(db, assessment_id)


@router.post("/assessments/{assessment_id}/confirm", summary="确认当前版本")
def confirm_assessment(
    assessment_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    codes = collect_permission_codes(user)
    manage = "*" in codes or "kpi:template:manage" in codes
    return performance_kpi.confirm_assessment(db, user, assessment_id, manage=manage)


@router.post("/assessments/{assessment_id}/archive", summary="归档并生成薪酬依据")
def archive_assessment(
    assessment_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
    payload: Annotated[Optional[ArchiveIn], Body()] = None,
) -> dict:
    return performance_kpi.archive_assessment(db, assessment_id, fraud=bool(payload and payload.fraud))


@router.get("/feedback-records", summary="反馈记录")
def list_feedback(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list:
    codes = collect_permission_codes(user)
    see = "*" in codes or "kpi:template:manage" in codes
    return performance_kpi.list_feedback(db, see_identity=see)


@router.post("/feedback-records", summary="登记反馈")
def create_feedback(
    payload: FeedbackIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.create_feedback(db, payload.model_dump())


@router.get("/lecturer-status/{user_id}", summary="讲师有效投诉是否超过 3 次")
def lecturer_status(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.lecturer_status(db, user_id)


@router.get("/stage-cases", summary="入职阶段考核")
def list_stage_cases(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(ONBOARD_MANAGE)],
) -> list:
    return performance_kpi.list_stage_cases(db, user)


@router.get("/stage-cases/candidates", summary="入职考核待开案候选(近 N 天入职员工)")
def list_onboarding_candidates(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(ONBOARD_MANAGE)],
    within_days: int = 180,
) -> dict:
    return performance_kpi.list_onboarding_candidates_api(db, within_days=within_days)


@router.post("/stage-cases", summary="开立入职阶段考核")
def open_stage_case(
    payload: StageIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(ONBOARD_MANAGE)],
) -> dict:
    return performance_kpi.open_stage_case(db, payload.model_dump())


@router.get("/observation-cases", summary="观察期")
def list_observations(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> list:
    return performance_kpi.list_observations(db)


@router.post("/observation-cases", summary="登记观察期结论")
def open_observation(
    payload: ObservationIn,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(MANAGE)],
) -> dict:
    return performance_kpi.open_observation(db, payload.model_dump())


class MaterialDraftIn(BaseModel):
    content: str


class MaterialReturnIn(BaseModel):
    reason: str


class RevisionIn(BaseModel):
    revision: int


class ItemActualIn(BaseModel):
    item_id: int
    actual: str


class EmployeeSubmitIn(BaseModel):
    revision: int
    actuals: Optional[list[ItemActualIn]] = None
    self_comment: Optional[str] = None
    draft: bool = False


class ManagerSubmitIn(BaseModel):
    revision: int
    comment: Optional[str] = None
    scores: Optional[list[dict]] = None
    actuals: Optional[list[ItemActualIn]] = None


class HrReviewIn(BaseModel):
    revision: int
    approve: bool = True
    note: Optional[str] = None


class AppealIn(BaseModel):
    revision: int
    reason: str
    request_score: int


class ResolveAppealIn(BaseModel):
    revision: int
    approve: bool = True
    resolution: str
    final_score: Optional[int] = None
    scores: Optional[list[dict]] = None
    return_to_manager: bool = False


@router.get("/assessments/{assessment_id}/material-tasks", summary="材料任务列表")
def list_material_tasks(
    assessment_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list:
    from app.services import performance_assessment_flow as flow
    from app.services import performance_materials as mat_svc

    # 与 runtime-detail / 流转动作一致：admin、hr 角色或 KPI 管理权限可查看
    return mat_svc.list_material_tasks(db, assessment_id, user, manage=flow._is_hr(user))


@router.patch("/material-tasks/{task_id}/draft", summary="材料草稿")
def material_draft(
    task_id: int,
    payload: MaterialDraftIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_materials as mat_svc

    return mat_svc.save_draft(db, task_id, user, payload.content)


@router.post("/material-tasks/{task_id}/return", summary="退回单条材料")
def material_return(
    task_id: int,
    payload: MaterialReturnIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_materials as mat_svc

    return mat_svc.return_task(db, task_id, user, payload.reason)


@router.post("/material-tasks/{task_id}/verify", summary="核实单条材料")
def material_verify(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_materials as mat_svc

    return mat_svc.verify_task(db, task_id, user)


@router.post("/assessments/{assessment_id}/employee-submit", summary="员工提交考核材料")
def employee_submit(
    assessment_id: int,
    payload: EmployeeSubmitIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_assessment_flow as flow

    return flow.employee_submit(
        db,
        assessment_id,
        user,
        revision=payload.revision,
        actuals=[row.model_dump() for row in payload.actuals] if payload.actuals is not None else None,
        self_comment=payload.self_comment,
        draft=payload.draft,
    )


@router.post("/assessments/{assessment_id}/manager-submit", summary="主管提交评分")
def manager_submit(
    assessment_id: int,
    payload: ManagerSubmitIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_assessment_flow as flow

    return flow.manager_submit(
        db,
        assessment_id,
        user,
        revision=payload.revision,
        scores=payload.scores,
        comment=payload.comment,
        actuals=[row.model_dump() for row in payload.actuals] if payload.actuals is not None else None,
    )


@router.post("/assessments/{assessment_id}/training-submit", summary="培训部提交评分（入职考核）")
def training_submit(
    assessment_id: int,
    payload: ManagerSubmitIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_assessment_flow as flow

    return flow.training_submit(
        db,
        assessment_id,
        user,
        revision=payload.revision,
        scores=payload.scores,
        comment=payload.comment,
    )


@router.post("/assessments/{assessment_id}/hr-review", summary="HR复核")
def hr_review(
    assessment_id: int,
    payload: HrReviewIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_assessment_flow as flow

    return flow.hr_review(
        db, assessment_id, user, revision=payload.revision, approve=payload.approve, note=payload.note
    )


@router.post("/assessments/{assessment_id}/result-confirm", summary="员工确认结果")
def result_confirm(
    assessment_id: int,
    payload: RevisionIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_assessment_flow as flow

    return flow.result_confirm(db, assessment_id, user, revision=payload.revision)


class PartyConfirmIn(BaseModel):
    revision: int
    party: str  # manager | training | hr


@router.post("/assessments/{assessment_id}/party-confirm", summary="入职考核三方确认（主管/培训部/HR）")
def party_confirm(
    assessment_id: int,
    payload: PartyConfirmIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_assessment_flow as flow

    return flow.party_confirm(
        db, assessment_id, user, revision=payload.revision, party=payload.party
    )


@router.post("/assessments/{assessment_id}/runtime-appeals", summary="发起申诉")
def create_runtime_appeal(
    assessment_id: int,
    payload: AppealIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_assessment_flow as flow

    return flow.create_appeal(
        db,
        assessment_id,
        user,
        revision=payload.revision,
        reason=payload.reason,
        request_score=payload.request_score,
    )


@router.post("/assessments/{assessment_id}/runtime-appeals/resolve", summary="处理申诉")
def resolve_runtime_appeal(
    assessment_id: int,
    payload: ResolveAppealIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_assessment_flow as flow

    return flow.resolve_appeal(
        db,
        assessment_id,
        user,
        revision=payload.revision,
        approve=payload.approve,
        resolution=payload.resolution,
        final_score=payload.final_score,
        scores=payload.scores,
        return_to_manager=payload.return_to_manager,
    )


@router.get("/assessments/{assessment_id}/actions", summary="当前允许动作")
def assessment_actions(
    assessment_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_assessment_flow as flow

    return flow.get_actions(db, assessment_id, user)


@router.get("/assessments/{assessment_id}/runtime-detail", summary="运行期考核详情")
def assessment_runtime_detail(
    assessment_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.services import performance_assessment_flow as flow

    row = flow._assessment(db, assessment_id)
    return flow.detail_payload(db, row, user)
