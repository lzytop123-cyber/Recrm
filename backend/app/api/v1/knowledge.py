"""AI 知识库 API。"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeAskOut,
    KnowledgeAskRequest,
    KnowledgeArticleOut,
    KnowledgeSourceCreate,
    KnowledgeSourceOut,
    KnowledgeSpaceOut,
    KnowledgeSyncStats,
    KnowledgeWorkbenchOut,
)
from app.services import knowledge as knowledge_service

router = APIRouter(prefix="/knowledge", tags=["AI知识库"])


@router.get("/workbench", response_model=KnowledgeWorkbenchOut, summary="知识库工作台")
def workbench(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["knowledge:view"]))],
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


@router.post("/ask", response_model=KnowledgeAskOut, summary="向知识库提问")
def ask(
    payload: KnowledgeAskRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["knowledge:view"]))],
) -> KnowledgeAskOut:
    return KnowledgeAskOut.model_validate(knowledge_service.ask(db, current_user, payload))


@router.post("/sources", response_model=KnowledgeSourceOut, summary="添加知识源")
def create_source(
    payload: KnowledgeSourceCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["knowledge:manage"]))],
) -> KnowledgeSourceOut:
    return KnowledgeSourceOut.model_validate(
        knowledge_service.create_source(db, current_user, payload)
    )


@router.post("/sources/{source_id}/authorize", response_model=KnowledgeSourceOut, summary="授权知识源")
def authorize_source(
    source_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["knowledge:manage"]))],
) -> KnowledgeSourceOut:
    return KnowledgeSourceOut.model_validate(
        knowledge_service.authorize_source(db, current_user, source_id)
    )
