"""项目管理 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.project import (
    DepartmentMonitorOut,
    MilestoneCreate,
    MilestoneEvidenceReview,
    MilestoneOut,
    MilestoneUpdate,
    ProjectAcceptRequest,
    ProjectAcceptanceReviewRequest,
    ProjectCreate,
    ProjectDetailOut,
    ProjectFinanceCheckRequest,
    ProjectFinanceCheckReviewRequest,
    ProjectLeftoverCloseRequest,
    ProjectPaymentDeferReviewRequest,
    ProjectListOut,
    ProjectOut,
    ProjectStatsOut,
    ProjectTaskCreate,
    ProjectTaskListOut,
    ProjectTaskOut,
    ProjectTaskStatsOut,
    ProjectTaskUpdate,
    ProjectTerminateRequest,
    ProjectUpdate,
)
from app.schemas.project_resource import (
    ProjectHoursBudgetOut,
    ProjectResourceNeedListOut,
    ProjectResourceNeedOut,
    ResourceConfirmRequest,
    ResourceRoleOptionsOut,
)
from app.schemas.lead import SalesJourneyOut
from app.services import project as project_service
from app.services import project_resource as resource_service
from app.services import sales_journey as sales_journey_service

router = APIRouter(prefix="/projects", tags=["项目管理"])


@router.get("/stats", response_model=ProjectStatsOut, summary="项目统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectStatsOut:
    return ProjectStatsOut(**project_service.project_stats(db, current_user))


@router.get("/department-monitor", response_model=DepartmentMonitorOut, summary="部门执行监控")
def department_monitor(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> DepartmentMonitorOut:
    return DepartmentMonitorOut(**project_service.department_monitor(db, current_user))


@router.get("/tasks/stats", response_model=ProjectTaskStatsOut, summary="任务统计")
def tasks_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectTaskStatsOut:
    return ProjectTaskStatsOut(**project_service.task_stats(db, current_user))


@router.get("/tasks", response_model=ProjectTaskListOut, summary="项目任务列表")
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    scope: Optional[str] = Query(None, description="mine/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ProjectTaskListOut:
    total, items = project_service.list_tasks(
        db,
        current_user,
        project_id=project_id,
        status=status,
        keyword=keyword,
        scope_filter=scope,
        page=page,
        page_size=page_size,
    )
    return ProjectTaskListOut(total=total, items=[ProjectTaskOut.model_validate(x) for x in items])


@router.post("/tasks", response_model=ProjectTaskOut, summary="新建项目任务")
def create_task(
    payload: ProjectTaskCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectTaskOut:
    task = project_service.create_task(db, current_user, payload)
    return ProjectTaskOut.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=ProjectTaskOut, summary="更新项目任务")
def update_task(
    task_id: int,
    payload: ProjectTaskUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectTaskOut:
    task = project_service.update_task(db, current_user, task_id, payload)
    return ProjectTaskOut.model_validate(task)


@router.get("", response_model=ProjectListOut, summary="项目列表")
def list_projects(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    contract_id: Optional[int] = None,
    scope: Optional[str] = Query(None, description="mine/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ProjectListOut:
    total, items = project_service.list_projects(
        db,
        current_user,
        status=status,
        keyword=keyword,
        contract_id=contract_id,
        scope_filter=scope,
        page=page,
        page_size=page_size,
    )
    return ProjectListOut(total=total, items=[ProjectOut.model_validate(x) for x in items])


@router.get("/resource-role-options", response_model=ResourceRoleOptionsOut, summary="立项所需角色选项（飞书部门）")
def list_resource_role_options(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ResourceRoleOptionsOut:
    _ = current_user
    return resource_service.list_resource_role_options(db)


@router.get("/resource-needs", response_model=ProjectResourceNeedListOut, summary="待确认资源列表")
def list_resource_needs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
    only_pending: bool = Query(True, description="仅待确认"),
) -> ProjectResourceNeedListOut:
    items = resource_service.list_pending_resources(db, current_user, only_pending=only_pending)
    pending = sum(1 for x in items if x.status == "pending")
    return ProjectResourceNeedListOut(
        items=[ProjectResourceNeedOut.model_validate(x) for x in items],
        total=len(items),
        pending_count=pending,
    )


@router.post(
    "/resource-needs/{need_id}/confirm",
    response_model=ProjectResourceNeedOut,
    summary="确认/调整/拒绝资源投入",
)
def confirm_resource_need(
    need_id: int,
    payload: ResourceConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectResourceNeedOut:
    item = resource_service.confirm_resource(db, current_user, need_id, payload)
    return ProjectResourceNeedOut.model_validate(item)


@router.post("", response_model=ProjectOut, summary="项目立项")
def create_project(
    payload: ProjectCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    project = project_service.create_project(db, current_user, payload)
    return ProjectOut.model_validate(project)


@router.get("/{project_id}", response_model=ProjectDetailOut, summary="项目详情")
def get_project(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectDetailOut:
    project = project_service.get_project_detail(db, current_user, project_id)
    return ProjectDetailOut.model_validate(project)


@router.get("/{project_id}/journey", response_model=SalesJourneyOut, summary="业务旅程")
def get_project_journey(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> SalesJourneyOut:
    project = project_service.get_project_detail(db, current_user, project_id)
    return SalesJourneyOut(**sales_journey_service.build_sales_journey(db, project=project))


@router.get(
    "/{project_id}/hours-budget",
    response_model=ProjectHoursBudgetOut,
    summary="资源承诺 vs 任务工时",
)
def get_project_hours_budget(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectHoursBudgetOut:
    project = project_service.get_project_detail(db, current_user, project_id)
    return ProjectHoursBudgetOut(**resource_service.get_hours_budget(db, project.id))


@router.patch("/{project_id}", response_model=ProjectOut, summary="编辑项目")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    project = project_service.update_project(db, current_user, project_id, payload)
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/plan", response_model=ProjectOut, summary="进入计划中")
def start_planning(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(project_service.start_planning(db, current_user, project_id))


@router.post("/{project_id}/execute", response_model=ProjectOut, summary="进入执行中")
def start_executing(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(project_service.start_executing(db, current_user, project_id))


@router.post("/{project_id}/accepting", response_model=ProjectOut, summary="进入验收中")
def start_acceptance(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(project_service.start_acceptance(db, current_user, project_id))


@router.post("/{project_id}/accept", response_model=ProjectOut, summary="提交内部验收（待审批）")
def accept_project(
    project_id: int,
    payload: ProjectAcceptRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(
        project_service.accept_project(db, current_user, project_id, payload)
    )


@router.post(
    "/{project_id}/acceptance/confirm",
    response_model=ProjectOut,
    summary="通过验收审批",
)
def confirm_acceptance(
    project_id: int,
    payload: ProjectAcceptanceReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(
        project_service.review_acceptance(
            db, current_user, project_id, payload, approve=True
        )
    )


@router.post(
    "/{project_id}/acceptance/reject",
    response_model=ProjectOut,
    summary="驳回验收审批",
)
def reject_acceptance(
    project_id: int,
    payload: ProjectAcceptanceReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(
        project_service.review_acceptance(
            db, current_user, project_id, payload, approve=False
        )
    )


@router.post(
    "/{project_id}/finance-check",
    response_model=ProjectOut,
    summary="提交财务核对（待审批）",
)
def finance_check(
    project_id: int,
    payload: ProjectFinanceCheckRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(
        project_service.submit_finance_check(db, current_user, project_id, payload)
    )


@router.post(
    "/{project_id}/finance-check/confirm",
    response_model=ProjectOut,
    summary="通过财务核对审批",
)
def confirm_finance_check(
    project_id: int,
    payload: ProjectFinanceCheckReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(
        project_service.review_finance_check(
            db, current_user, project_id, payload, approve=True
        )
    )


@router.post(
    "/{project_id}/finance-check/reject",
    response_model=ProjectOut,
    summary="驳回财务核对审批",
)
def reject_finance_check(
    project_id: int,
    payload: ProjectFinanceCheckReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(
        project_service.review_finance_check(
            db, current_user, project_id, payload, approve=False
        )
    )


@router.post(
    "/{project_id}/payment-defer/confirm",
    response_model=ProjectOut,
    summary="通过无到款立项审批",
)
def confirm_payment_defer(
    project_id: int,
    payload: ProjectPaymentDeferReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(
        project_service.review_payment_defer(
            db, current_user, project_id, payload, approve=True
        )
    )


@router.post(
    "/{project_id}/payment-defer/reject",
    response_model=ProjectOut,
    summary="驳回无到款立项审批",
)
def reject_payment_defer(
    project_id: int,
    payload: ProjectPaymentDeferReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(
        project_service.review_payment_defer(
            db, current_user, project_id, payload, approve=False
        )
    )


@router.post(
    "/{project_id}/leftover-close",
    response_model=ProjectOut,
    summary="关闭遗留问题",
)
def leftover_close(
    project_id: int,
    payload: ProjectLeftoverCloseRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(
        project_service.set_leftover_closed(db, current_user, project_id, payload)
    )


@router.post("/{project_id}/complete", response_model=ProjectOut, summary="完成项目")
def complete_project(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(project_service.complete_project(db, current_user, project_id))


@router.post("/{project_id}/terminate", response_model=ProjectOut, summary="终止项目")
def terminate_project(
    project_id: int,
    payload: ProjectTerminateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> ProjectOut:
    return ProjectOut.model_validate(
        project_service.terminate_project(db, current_user, project_id, payload)
    )


@router.post("/{project_id}/milestones", response_model=MilestoneOut, summary="添加里程碑")
def add_milestone(
    project_id: int,
    payload: MilestoneCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> MilestoneOut:
    ms = project_service.add_milestone(db, current_user, project_id, payload)
    return MilestoneOut.model_validate(ms)


@router.patch(
    "/{project_id}/milestones/{milestone_id}",
    response_model=MilestoneOut,
    summary="更新里程碑",
)
def update_milestone(
    project_id: int,
    milestone_id: int,
    payload: MilestoneUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> MilestoneOut:
    ms = project_service.update_milestone(db, current_user, project_id, milestone_id, payload)
    return MilestoneOut.model_validate(ms)


@router.delete(
    "/{project_id}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除计划节点",
)
def delete_milestone(
    project_id: int,
    milestone_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> None:
    project_service.delete_milestone(db, current_user, project_id, milestone_id)


@router.post(
    "/{project_id}/milestones/{milestone_id}/evidence-review",
    response_model=MilestoneOut,
    summary="确认/驳回完成证据",
)
def review_milestone_evidence(
    project_id: int,
    milestone_id: int,
    payload: MilestoneEvidenceReview,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["project:view"]))],
) -> MilestoneOut:
    ms = project_service.review_milestone_evidence(
        db,
        current_user,
        project_id,
        milestone_id,
        payload.action,
        payload.reason,
    )
    return MilestoneOut.model_validate(ms)
