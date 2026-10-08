"""S2–S5 一键场景。聊天仍走 /agent/chat。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_current_user
from app.database import get_db
from app.models.user import User
from app.services import ai_admin
from app.services import ai_scene as scene_service

router = APIRouter(tags=["AI场景"])


class DailyReportIn(BaseModel):
    date: Optional[str] = None
    week: Optional[str] = None


class DailyReportSubmitIn(BaseModel):
    body: str = Field(min_length=1)


class FollowupSummaryIn(BaseModel):
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    opportunity_id: Optional[int] = None


class PromptIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1)


class ScenePatch(BaseModel):
    enabled: bool


class BudgetItem(BaseModel):
    scope: str
    scope_id: int
    monthly_tokens: int = Field(ge=0)


class BudgetPut(BaseModel):
    items: list[BudgetItem]
    auto_pass_max_amount: Optional[str] = None


class SpotReviewIn(BaseModel):
    conclusion: str
    comment: str = ""


@router.post("/agent/scenes/daily-report", summary="生成日报/周报草稿")
def create_daily_report(
    payload: DailyReportIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return scene_service.create_daily_report(db, user, work_date=payload.date, week=payload.week)


@router.post("/agent/scenes/daily-report/{run_id}/submit", summary="确认提交日报草稿")
def submit_daily_report(
    run_id: int,
    payload: DailyReportSubmitIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return scene_service.submit_daily_report(db, user, run_id, payload.body)


@router.post("/agent/scenes/followup-summary", summary="跟进摘要（只提示）")
def followup_summary(
    payload: FollowupSummaryIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return scene_service.followup_summary(
        db,
        user,
        lead_id=payload.lead_id,
        customer_id=payload.customer_id,
        opportunity_id=payload.opportunity_id,
    )


@router.get("/tickets/{ticket_id}/recommendations", summary="工单方案推荐")
def ticket_recommendations(
    ticket_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(PermissionChecker(["ticket:view"]))],
) -> dict:
    return scene_service.ticket_recommendations(db, user, ticket_id)


@router.get("/approvals/{approval_id}/precheck", summary="审批预审")
def approval_precheck(
    approval_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> dict:
    return scene_service.approval_precheck(db, user, approval_id)


@router.get("/ai/calls", summary="场景调用审计")
def list_calls(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    total, items = scene_service.list_calls(db, user, page=page, page_size=page_size)
    return {"total": total, "items": [ai_admin.call_view(row) for row in items]}


@router.get("/ai/calls/{call_id}", summary="单次调用详情")
def get_call(
    call_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return ai_admin.call_view(scene_service.get_call(db, user, call_id), detail=True)


@router.get("/ai/prompts", summary="Prompt 模板列表")
def list_prompts(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> dict:
    rows = ai_admin.list_prompts(db)
    return {"items": [ai_admin.prompt_out(row) for row in rows]}


@router.post("/ai/prompts", summary="新建 Prompt 版本")
def create_prompt(
    payload: PromptIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(PermissionChecker(["system:manage"]))],
) -> dict:
    return ai_admin.prompt_out(ai_admin.create_prompt(db, user, code=payload.code, name=payload.name, content=payload.content))


@router.get("/ai/prompts/{prompt_id}", summary="模板详情与版本")
def get_prompt(
    prompt_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> dict:
    row, versions = ai_admin.get_prompt(db, prompt_id)
    return ai_admin.prompt_out(row, versions)


@router.post("/ai/prompts/{prompt_id}/publish", summary="发布 Prompt 版本")
def publish_prompt(
    prompt_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(PermissionChecker(["system:manage"]))],
) -> dict:
    return ai_admin.prompt_out(ai_admin.publish_prompt(db, user, prompt_id))


@router.get("/ai/scenes", summary="场景清单与开关")
def list_scenes(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> dict:
    return {"items": ai_admin.list_scenes(db)}


@router.patch("/ai/scenes/{code}", summary="启用或停用场景")
def set_scene(
    code: str,
    payload: ScenePatch,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(PermissionChecker(["system:manage"]))],
) -> dict:
    return ai_admin.set_scene(db, user, code, payload.enabled)


@router.get("/ai/budgets", summary="token 限额与自动通过上限")
def get_budgets(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(PermissionChecker(["system:view"]))],
) -> dict:
    return ai_admin.list_budgets(db)


@router.put("/ai/budgets", summary="保存 token 限额")
def put_budgets(
    payload: BudgetPut,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(PermissionChecker(["system:manage"]))],
) -> dict:
    return ai_admin.save_budgets(
        db,
        user,
        [item.model_dump() for item in payload.items],
        payload.auto_pass_max_amount,
    )


@router.post("/approvals/{approval_id}/auto-pass", summary="L1 低风险自动通过")
def auto_pass(
    approval_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> dict:
    return scene_service.auto_pass(db, user, approval_id)


@router.get("/approvals/spot-checks", summary="L1 事后抽查队列")
def list_spot_checks(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(PermissionChecker(["system:view"]))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    total, items = ai_admin.list_spot_checks(db, page=page, page_size=page_size)
    return {"total": total, "items": [ai_admin.call_view(row, detail=True) for row in items]}


@router.post("/approvals/spot-checks/{check_id}/review", summary="抽查结论")
def review_spot_check(
    check_id: int,
    payload: SpotReviewIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(PermissionChecker(["system:manage"]))],
) -> dict:
    return ai_admin.review_spot_check(
        db, user, check_id, conclusion=payload.conclusion, comment=payload.comment
    )
