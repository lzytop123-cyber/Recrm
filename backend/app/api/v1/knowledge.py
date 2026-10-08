"""AI 知识库 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.knowledge import SOURCE_TYPE_FEISHU_CHAT, SOURCE_TYPE_FEISHU_DOC
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeApproveIn,
    KnowledgeArticleCreate,
    KnowledgeArticleOut,
    KnowledgeArticlePatch,
    KnowledgeAskOut,
    KnowledgeAskRequest,
    KnowledgeCorrectionIn,
    KnowledgeEntryListOut,
    KnowledgeEntryOut,
    KnowledgeFeedbackIn,
    KnowledgeFeedbackOut,
    KnowledgeFeedbackPatch,
    KnowledgeGapOut,
    KnowledgeJobListOut,
    KnowledgeJobOut,
    KnowledgeRejectIn,
    KnowledgeSourceCreate,
    KnowledgeSourceListOut,
    KnowledgeSourceOut,
    KnowledgeSourceSyncStatusOut,
    KnowledgeSpaceCreate,
    KnowledgeSpaceOut,
    KnowledgeStatsOut,
    KnowledgeSyncConfigOut,
    KnowledgeSyncConfigPatch,
    KnowledgeSyncStats,
    KnowledgeVersionOut,
    KnowledgeWhitelistCreate,
    KnowledgeWorkbenchOut,
)
from app.services import knowledge as knowledge_service

router = APIRouter(prefix="/knowledge", tags=["AI知识库"])

_view = PermissionChecker(["knowledge:view"])
_manage = PermissionChecker(["knowledge:manage"])


@router.get("/workbench", response_model=KnowledgeWorkbenchOut, summary="知识库工作台")
def workbench(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_view)],
) -> KnowledgeWorkbenchOut:
    data = knowledge_service.get_workbench(db, current_user)
    return KnowledgeWorkbenchOut(
        spaces=[KnowledgeSpaceOut.model_validate(x) for x in data["spaces"]],
        sources=[KnowledgeSourceOut.model_validate(x) for x in data["sources"]],
        articles=[KnowledgeArticleOut.model_validate(x) for x in data["articles"]],
        sync_stats=KnowledgeSyncStats.model_validate(data["sync_stats"]),
        total_published=data["total_published"],
        can_manage=data["can_manage"],
    )


@router.post("/spaces", response_model=KnowledgeSpaceOut, summary="新增知识库目录")
def create_space(
    payload: KnowledgeSpaceCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeSpaceOut:
    return KnowledgeSpaceOut.model_validate(
        knowledge_service.create_space(db, current_user, payload)
    )


@router.post("/ask", response_model=KnowledgeAskOut, summary="向知识库提问")
def ask(
    payload: KnowledgeAskRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_view)],
) -> KnowledgeAskOut:
    return KnowledgeAskOut.model_validate(knowledge_service.ask(db, current_user, payload))


@router.post("/ask/{ask_id}/feedback", response_model=KnowledgeFeedbackOut, summary="问答反馈")
def ask_feedback(
    ask_id: int,
    payload: KnowledgeFeedbackIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_view)],
) -> KnowledgeFeedbackOut:
    return KnowledgeFeedbackOut.model_validate(
        knowledge_service.create_feedback(db, current_user, ask_id, payload)
    )


@router.post("/articles", response_model=KnowledgeArticleOut, summary="手工录入知识条目")
def create_article(
    payload: KnowledgeArticleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeArticleOut:
    return KnowledgeArticleOut.model_validate(
        knowledge_service.create_article(db, current_user, payload)
    )


@router.get("/sources", response_model=KnowledgeSourceListOut, summary="来源列表")
def list_sources(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_view)],
    status: Annotated[Optional[str], Query()] = None,
    source_type: Annotated[Optional[str], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> KnowledgeSourceListOut:
    _ = current_user
    data = knowledge_service.list_sources(
        db, status=status, source_type=source_type, page=page, page_size=page_size
    )
    return KnowledgeSourceListOut(
        total=data["total"],
        items=[KnowledgeSourceOut.model_validate(x) for x in data["items"]],
    )


@router.post("/sources", response_model=KnowledgeSourceOut, summary="添加知识源")
async def create_source(
    payload: KnowledgeSourceCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeSourceOut:
    return KnowledgeSourceOut.model_validate(
        await knowledge_service.create_source(db, current_user, payload)
    )


@router.get(
    "/sources/{source_id}/sync-status",
    response_model=KnowledgeSourceSyncStatusOut,
    summary="来源同步状态",
)
def source_sync_status(
    source_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_view)],
) -> KnowledgeSourceSyncStatusOut:
    _ = current_user
    return KnowledgeSourceSyncStatusOut.model_validate(
        knowledge_service.source_sync_status(db, source_id)
    )


@router.post("/sources/{source_id}/resync", response_model=KnowledgeSourceOut, summary="重新同步")
async def resync_source(
    source_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeSourceOut:
    return KnowledgeSourceOut.model_validate(
        await knowledge_service.resync_source(db, current_user, source_id)
    )


@router.post("/sources/{source_id}/revoke", response_model=KnowledgeSourceOut, summary="来源失效")
def revoke_source(
    source_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeSourceOut:
    return KnowledgeSourceOut.model_validate(
        knowledge_service.revoke_source(db, current_user, source_id)
    )


@router.post("/sources/{source_id}/authorize", response_model=KnowledgeSourceOut, summary="同步飞书文档")
async def authorize_source(
    source_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeSourceOut:
    return KnowledgeSourceOut.model_validate(
        await knowledge_service.sync_feishu_source(db, current_user, source_id)
    )


@router.get("/sources/{source_id}", response_model=KnowledgeSourceOut, summary="来源详情")
def get_source(
    source_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_view)],
) -> KnowledgeSourceOut:
    _ = current_user
    return KnowledgeSourceOut.model_validate(knowledge_service.get_source(db, source_id))


@router.get("/entries", response_model=KnowledgeEntryListOut, summary="知识条目列表")
def list_entries(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_view)],
    source_id: Annotated[Optional[int], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    space_id: Annotated[Optional[int], Query()] = None,
    keyword: Annotated[Optional[str], Query()] = None,
    origin: Annotated[Optional[str], Query()] = None,
    sort: Annotated[Optional[str], Query(description="recent / title")] = "recent",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> KnowledgeEntryListOut:
    data = knowledge_service.list_entries(
        db,
        current_user,
        source_id=source_id,
        status=status,
        space_id=space_id,
        keyword=keyword,
        origin=origin,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return KnowledgeEntryListOut(
        total=data["total"],
        items=[KnowledgeArticleOut.model_validate(x) for x in data["items"]],
    )


@router.get(
    "/entries/{entry_id}/versions",
    response_model=list[KnowledgeVersionOut],
    summary="条目版本",
)
def list_versions(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_view)],
) -> list[KnowledgeVersionOut]:
    _ = current_user
    return [KnowledgeVersionOut.model_validate(x) for x in knowledge_service.list_versions(db, entry_id)]


@router.post("/entries/{entry_id}/review", response_model=KnowledgeArticleOut, summary="审核条目")
def review_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeArticleOut:
    return KnowledgeArticleOut.model_validate(
        knowledge_service.review_entry(db, current_user, entry_id)
    )


@router.post("/entries/{entry_id}/publish", response_model=KnowledgeArticleOut, summary="发布条目")
def publish_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeArticleOut:
    return KnowledgeArticleOut.model_validate(
        knowledge_service.publish_entry(db, current_user, entry_id)
    )


@router.post("/entries/{entry_id}/disable", response_model=KnowledgeArticleOut, summary="停用条目")
def disable_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeArticleOut:
    return KnowledgeArticleOut.model_validate(
        knowledge_service.disable_entry(db, current_user, entry_id)
    )


@router.post("/entries/{entry_id}/archive", response_model=KnowledgeArticleOut, summary="归档条目")
def archive_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeArticleOut:
    return KnowledgeArticleOut.model_validate(
        knowledge_service.archive_entry(db, current_user, entry_id)
    )


@router.post("/entries/{entry_id}/submit", response_model=KnowledgeArticleOut, summary="提交审核")
def submit_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeArticleOut:
    return KnowledgeArticleOut.model_validate(
        knowledge_service.submit_entry(db, current_user, entry_id)
    )


@router.post("/entries/{entry_id}/approve", response_model=KnowledgeArticleOut, summary="审核通过并发布")
def approve_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
    payload: Annotated[KnowledgeApproveIn, Body()] = KnowledgeApproveIn(),
) -> KnowledgeArticleOut:
    return KnowledgeArticleOut.model_validate(
        knowledge_service.approve_entry(db, current_user, entry_id, payload)
    )


@router.post("/entries/{entry_id}/reject", response_model=KnowledgeArticleOut, summary="退回修改")
def reject_entry(
    entry_id: int,
    payload: KnowledgeRejectIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeArticleOut:
    return KnowledgeArticleOut.model_validate(
        knowledge_service.reject_entry(db, current_user, entry_id, payload.reason)
    )


@router.patch("/entries/{entry_id}", response_model=KnowledgeArticleOut, summary="保存草稿")
def patch_entry(
    entry_id: int,
    payload: KnowledgeArticlePatch,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeArticleOut:
    return KnowledgeArticleOut.model_validate(
        knowledge_service.patch_entry(db, current_user, entry_id, payload)
    )


@router.post("/entries/{entry_id}/corrections", response_model=KnowledgeArticleOut, summary="纠错出新版本")
def correct_entry(
    entry_id: int,
    payload: KnowledgeCorrectionIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeArticleOut:
    return KnowledgeArticleOut.model_validate(
        knowledge_service.correct_entry(db, current_user, entry_id, payload)
    )


@router.get("/entries/{entry_id}", response_model=KnowledgeEntryOut, summary="条目详情")
def get_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_view)],
) -> KnowledgeEntryOut:
    _ = current_user
    return KnowledgeEntryOut.model_validate(knowledge_service.get_entry(db, entry_id, current_user))


@router.get(
    "/entries/{entry_id}/attachments/{index}/download",
    summary="下载附件",
)
def download_attachment(
    entry_id: int,
    index: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_view)],
) -> FileResponse:
    path, filename = knowledge_service.download_attachment(db, current_user, entry_id, index)
    return FileResponse(path, filename=filename)


@router.delete("/entries/{entry_id}", summary="删除条目")
def delete_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> dict:
    knowledge_service.delete_entry(db, current_user, entry_id)
    return {"ok": True, "message": "已删除"}


@router.get("/jobs", response_model=KnowledgeJobListOut, summary="采集任务列表")
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> KnowledgeJobListOut:
    _ = current_user
    data = knowledge_service.list_jobs(db, page=page, page_size=page_size)
    return KnowledgeJobListOut(
        total=data["total"],
        items=[KnowledgeJobOut.model_validate(x) for x in data["items"]],
    )


@router.post("/jobs/{job_id}/retry", response_model=KnowledgeJobOut, summary="重试采集任务")
async def retry_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeJobOut:
    return KnowledgeJobOut.model_validate(await knowledge_service.retry_job(db, current_user, job_id))


@router.get("/feedback", response_model=list[KnowledgeFeedbackOut], summary="反馈队列")
def list_feedback(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
    status: Annotated[Optional[str], Query()] = None,
) -> list[KnowledgeFeedbackOut]:
    _ = current_user
    return [KnowledgeFeedbackOut.model_validate(x) for x in knowledge_service.list_feedback(db, status=status)]


@router.patch("/feedback/{feedback_id}", response_model=KnowledgeFeedbackOut, summary="处理反馈")
def patch_feedback(
    feedback_id: int,
    payload: KnowledgeFeedbackPatch,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeFeedbackOut:
    return KnowledgeFeedbackOut.model_validate(
        knowledge_service.patch_feedback(db, current_user, feedback_id, payload)
    )


@router.get("/gaps", response_model=list[KnowledgeGapOut], summary="知识缺失清单")
def list_gaps(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> list[KnowledgeGapOut]:
    _ = current_user
    return [KnowledgeGapOut.model_validate(x) for x in knowledge_service.list_gaps(db)]


@router.get("/stats", response_model=KnowledgeStatsOut, summary="知识运营统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeStatsOut:
    _ = current_user
    return KnowledgeStatsOut.model_validate(knowledge_service.knowledge_stats(db))


@router.get("/sync-config", response_model=KnowledgeSyncConfigOut, summary="飞书同步配置")
def get_sync_config(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeSyncConfigOut:
    data = knowledge_service.get_sync_config(db, current_user)
    return KnowledgeSyncConfigOut(
        crawl_enabled=data["crawl_enabled"],
        chats=[KnowledgeSourceOut.model_validate(x) for x in data["chats"]],
        folders=[KnowledgeSourceOut.model_validate(x) for x in data["folders"]],
    )


@router.patch("/sync-config", response_model=KnowledgeSyncConfigOut, summary="更新抓取总开关")
def patch_sync_config(
    payload: KnowledgeSyncConfigPatch,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeSyncConfigOut:
    data = knowledge_service.patch_sync_config(db, current_user, payload.crawl_enabled)
    return KnowledgeSyncConfigOut(
        crawl_enabled=data["crawl_enabled"],
        chats=[KnowledgeSourceOut.model_validate(x) for x in data["chats"]],
        folders=[KnowledgeSourceOut.model_validate(x) for x in data["folders"]],
    )


@router.post("/sync-config/chats", response_model=KnowledgeSourceOut, summary="添加飞书群白名单")
async def add_chat_whitelist(
    payload: KnowledgeWhitelistCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeSourceOut:
    return KnowledgeSourceOut.model_validate(
        await knowledge_service.add_whitelist(db, current_user, SOURCE_TYPE_FEISHU_CHAT, payload)
    )


@router.post("/sync-config/folders", response_model=KnowledgeSourceOut, summary="添加文档文件夹白名单")
async def add_folder_whitelist(
    payload: KnowledgeWhitelistCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeSourceOut:
    return KnowledgeSourceOut.model_validate(
        await knowledge_service.add_whitelist(db, current_user, SOURCE_TYPE_FEISHU_DOC, payload)
    )


@router.delete("/sync-config/{source_id}", response_model=KnowledgeSourceOut, summary="移除白名单")
def remove_whitelist(
    source_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_manage)],
) -> KnowledgeSourceOut:
    return KnowledgeSourceOut.model_validate(
        knowledge_service.revoke_source(db, current_user, source_id)
    )
