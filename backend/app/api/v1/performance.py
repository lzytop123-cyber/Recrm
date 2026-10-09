"""绩效 API。"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.performance import PerformanceCycle
from app.models.user import User
from app.schemas.performance import (
    AppealCreate,
    AppealOut,
    AppealResolveRequest,
    AssessmentDetailOut,
    AssessmentOut,
    CycleCreateRequest,
    CycleDetailOut,
    CycleGenerateRequest,
    ManagerRateRequest,
    MineAssessmentsOut,
    PerformanceCycleOut,
    PerformanceWorkbenchOut,
    SelfRateRequest,
    TemplateApproveRequest,
    TemplateCreateRequest,
    TemplateForkRequest,
    TemplateOut,
    TemplateUpdateRequest,
)
from app.services import performance as perf_service
from app.services import performance_template as tpl_service

router = APIRouter(prefix="/performance", tags=["目标绩效"])


def _tpl_out(row) -> TemplateOut:
    if not hasattr(row, "scopes"):
        row.scopes = []
    return TemplateOut.model_validate(row)


# —— 模板 ——
@router.get("/templates", response_model=List[TemplateOut], summary="绩效模板列表")
def list_templates(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["kpi:template:manage", "kpi:template:write", "kpi:view", "okr:view"], any_of=True))
    ],
    owner_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    owner_dept_id: Optional[int] = Query(None),
    cycle_id: Optional[int] = Query(None, description="传入后按周期生效期过滤，并计算该周期下模板人员是否全部阻断"),
) -> List[TemplateOut]:
    _ = current_user
    rows = tpl_service.list_templates(
        db, owner_type=owner_type, status=status, owner_dept_id=owner_dept_id
    )
    if cycle_id is not None:
        cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
        if cycle is None:
            raise HTTPException(status_code=404, detail="考核周期不存在")
        from app.services.performance_data_source import cycle_window
        from app.services.performance_personnel_matcher import template_all_blocked

        start, end = cycle_window(cycle)
        rows = [
            row
            for row in rows
            if tpl_service.is_template_effective_for_period(row, start, end)
        ]
        for row in rows:
            row.all_blocked = template_all_blocked(db, cycle_id=cycle_id, template_id=row.id)  # type: ignore[attr-defined]
    return [_tpl_out(x) for x in rows]


@router.get("/templates/{template_id}", response_model=TemplateOut, summary="模板详情")
def get_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["kpi:template:manage", "kpi:template:write", "kpi:view", "okr:view"], any_of=True))
    ],
) -> TemplateOut:
    _ = current_user
    return _tpl_out(tpl_service.get_template(db, template_id))


@router.post("/templates", response_model=TemplateOut, summary="新建 HR 基础模板")
def create_template(
    payload: TemplateCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["kpi:template:manage"]))],
) -> TemplateOut:
    row = tpl_service.create_template(
        db,
        name=payload.name,
        code=payload.code,
        items=[i.model_dump() for i in payload.items],
        owner_type="hr",
        cycle_type=payload.cycle_type,
        rules_json=payload.rules_json,
        created_by=current_user.id,
        remark=payload.remark,
        scopes=[s.model_dump() for s in payload.scopes] if payload.scopes is not None else None,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        eligibility_policy_json=payload.eligibility_policy_json,
        scoring_mode=payload.scoring_mode,
        engine_version=payload.engine_version,
        nominal_total=payload.nominal_total,
    )
    return _tpl_out(tpl_service.get_template(db, row.id))


@router.post("/templates/{template_id}/fork", response_model=TemplateOut, summary="部门派生模板")
def fork_template(
    template_id: int,
    payload: TemplateForkRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["kpi:template:write", "kpi:template:manage"], any_of=True))
    ],
) -> TemplateOut:
    row = tpl_service.fork_template(
        db,
        template_id,
        owner_dept_id=payload.owner_dept_id,
        created_by=current_user.id,
        name=payload.name,
        code=payload.code,
    )
    return _tpl_out(tpl_service.get_template(db, row.id))


@router.put("/templates/{template_id}", response_model=TemplateOut, summary="编辑模板")
def update_template(
    template_id: int,
    payload: TemplateUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["kpi:template:write", "kpi:template:manage"], any_of=True))
    ],
) -> TemplateOut:
    _ = current_user
    row = tpl_service.update_template(
        db,
        template_id,
        name=payload.name,
        remark=payload.remark,
        rules_json=payload.rules_json,
        items=[i.model_dump() for i in payload.items] if payload.items is not None else None,
        scopes=[s.model_dump() for s in payload.scopes] if payload.scopes is not None else None,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        eligibility_policy_json=payload.eligibility_policy_json,
    )
    return _tpl_out(row)


@router.post("/templates/{template_id}/submit", response_model=TemplateOut, summary="提交模板审批")
def submit_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["kpi:template:write", "kpi:template:manage"], any_of=True))
    ],
) -> TemplateOut:
    return _tpl_out(tpl_service.submit_for_review(db, template_id, current_user))


@router.post("/templates/{template_id}/approve", response_model=TemplateOut, summary="审批模板")
def approve_template(
    template_id: int,
    payload: TemplateApproveRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["kpi:template:manage"]))],
) -> TemplateOut:
    return _tpl_out(
        tpl_service.approve_template(
            db, template_id, current_user, approve=payload.approve, comment=payload.comment
        )
    )


@router.post("/templates/{template_id}/publish", response_model=TemplateOut, summary="发布模板")
def publish_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["kpi:template:manage"]))],
) -> TemplateOut:
    return _tpl_out(tpl_service.publish_template(db, template_id, current_user))


@router.post("/templates/{template_id}/disable", response_model=TemplateOut, summary="停用模板")
def disable_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["kpi:template:manage"]))],
) -> TemplateOut:
    return _tpl_out(tpl_service.disable_template(db, template_id, current_user))


@router.delete("/templates/{template_id}", status_code=204, summary="删除未使用的模板")
def delete_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["kpi:template:manage"]))],
) -> None:
    _ = current_user
    tpl_service.delete_template(db, template_id)


# —— 周期 ——
@router.get("/cycles", response_model=List[PerformanceCycleOut], summary="考核周期列表")
def list_cycles(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["kpi:cycle:manage", "kpi:template:manage", "kpi:view", "okr:view"], any_of=True))
    ],
    status: Optional[str] = Query(None),
) -> List[PerformanceCycleOut]:
    _ = current_user
    return [PerformanceCycleOut.model_validate(x) for x in perf_service.list_cycles(db, status=status)]


@router.post("/cycles", response_model=PerformanceCycleOut, summary="新建考核周期")
def create_cycle(
    payload: CycleCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["kpi:cycle:manage", "kpi:template:manage"], any_of=True))
    ],
) -> PerformanceCycleOut:
    _ = current_user
    return PerformanceCycleOut.model_validate(
        perf_service.create_cycle(
            db,
            payload.name,
            payload.template_id,
            cycle_type=payload.cycle_type,
            scope=payload.scope,
        )
    )


@router.post("/cycles/{cycle_id}/generate", response_model=List[AssessmentOut], summary="批量生成考核单")
def generate_assessments(
    cycle_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["kpi:cycle:manage", "kpi:template:manage"], any_of=True))
    ],
    payload: Optional[CycleGenerateRequest] = None,
) -> List[AssessmentOut]:
    _ = current_user
    scope = payload.scope if payload else None
    rows = perf_service.generate_assessments(db, cycle_id, scope=scope)
    return [AssessmentOut.model_validate(perf_service.enrich_assessment(db, r, with_items=True)) for r in rows]


@router.get("/cycles/{cycle_id}/detail", response_model=CycleDetailOut, summary="周期归档明细")
def cycle_detail(
    cycle_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["kpi:cycle:manage", "kpi:template:manage", "kpi:view", "okr:view"], any_of=True))
    ],
) -> CycleDetailOut:
    _ = current_user
    data = perf_service.get_cycle_detail(db, cycle_id)
    return CycleDetailOut(
        cycle=PerformanceCycleOut.model_validate(data["cycle"]),
        assessments=[AssessmentOut.model_validate(x) for x in data["assessments"]],
        grade_distribution=data["grade_distribution"],
    )


# —— 考核查询（静态路径放在动态路径前）——
@router.get("/assessments/mine", response_model=MineAssessmentsOut, summary="我的绩效历史")
def my_assessments(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> MineAssessmentsOut:
    data = perf_service.list_my_assessments(db, current_user)
    return MineAssessmentsOut(
        assessments=[AssessmentOut.model_validate(x) for x in data["assessments"]],
        trend=data["trend"],
    )


@router.get("/assessments/team", response_model=List[AssessmentOut], summary="团队绩效")
def team_assessments(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    scope: str = Query("direct", pattern="^(direct|dept)$"),
    period_label: Optional[str] = Query(None),
) -> List[AssessmentOut]:
    rows = perf_service.list_team_assessments(
        db, current_user, scope=scope, period_label=period_label
    )
    # 每行补「当前登录人能做什么」——前端只按 action_label 渲染按钮与统计
    from app.services import performance_assessment_flow as kpi_flow

    out: List[AssessmentOut] = []
    for row in rows:
        data = AssessmentOut.model_validate(row)
        actions = kpi_flow.allowed_actions(row, current_user)
        data.my_actions = actions
        data.action_label = kpi_flow.primary_action_label(actions)
        data.action_required = kpi_flow.action_required(actions)
        out.append(data)
    return out


@router.get("/assessments/{assessment_id}/detail", response_model=AssessmentDetailOut, summary="考核明细")
def assessment_detail(
    assessment_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> AssessmentDetailOut:
    row = perf_service.get_assessment_detail(db, current_user, assessment_id)
    return AssessmentDetailOut.model_validate(row)


# —— 原有工作台 / 评价 / 申诉 / 周期动作 ——
@router.get("/workbench", response_model=PerformanceWorkbenchOut, summary="绩效工作台数据")
def workbench(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: Optional[str] = Query(None),
) -> PerformanceWorkbenchOut:
    data = perf_service.get_workbench(db, current_user, period_label)
    return PerformanceWorkbenchOut(
        # 系统里还没有任何考核周期时 cycle 为 None（不自动创建）
        cycle=PerformanceCycleOut.model_validate(data["cycle"]) if data["cycle"] else None,
        assessments=[AssessmentOut.model_validate(x) for x in data["assessments"]],
        appeals=[AppealOut.model_validate(x) for x in data["appeals"]],
        grade_distribution=data["grade_distribution"],
    )


@router.post("/assessments/{assessment_id}/self-rate", response_model=AssessmentOut)
def self_rate(
    assessment_id: int,
    payload: SelfRateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> AssessmentOut:
    return AssessmentOut.model_validate(
        perf_service.rate_self(db, current_user, assessment_id, payload)
    )


@router.post("/assessments/{assessment_id}/manager-rate", response_model=AssessmentOut)
def manager_rate(
    assessment_id: int,
    payload: ManagerRateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> AssessmentOut:
    return AssessmentOut.model_validate(
        perf_service.rate_manager(db, current_user, assessment_id, payload)
    )


@router.post("/assessments/{assessment_id}/appeals", response_model=AppealOut)
def create_appeal(
    assessment_id: int,
    payload: AppealCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> AppealOut:
    return AppealOut.model_validate(
        perf_service.create_appeal(db, current_user, assessment_id, payload)
    )


@router.post("/appeals/{appeal_id}/resolve", response_model=AppealOut)
def resolve_appeal(
    appeal_id: int,
    payload: AppealResolveRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> AppealOut:
    return AppealOut.model_validate(
        perf_service.resolve_appeal(db, current_user, appeal_id, payload)
    )


@router.post("/cycles/reset", response_model=PerformanceCycleOut, summary="重置考核周期（可重新打分）")
def reset_cycle(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: Optional[str] = Query(None),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.reset_cycle(db, current_user, period_label)
    )


@router.post("/cycles/calibrate", response_model=PerformanceCycleOut)
def calibrate(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: Optional[str] = Query(None),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.start_calibration(db, current_user, period_label)
    )


@router.post("/cycles/lock", response_model=PerformanceCycleOut)
def lock_cycle(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: Optional[str] = Query(None),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.lock_cycle(db, current_user, period_label)
    )


@router.post("/cycles/payroll/generate", response_model=PerformanceCycleOut)
def generate_payroll(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: Optional[str] = Query(None),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.generate_payroll(db, current_user, period_label)
    )


@router.post("/cycles/payroll/review", response_model=PerformanceCycleOut)
def review_payroll(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: Optional[str] = Query(None),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.review_payroll(db, current_user, period_label)
    )


@router.post("/cycles/payroll/publish", response_model=PerformanceCycleOut)
def publish_payroll(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: Optional[str] = Query(None),
) -> PerformanceCycleOut:
    return PerformanceCycleOut.model_validate(
        perf_service.publish_payroll(db, current_user, period_label)
    )
