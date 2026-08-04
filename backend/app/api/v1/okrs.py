"""OKR API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.okr import (
    KeyResultCreate,
    KeyResultOut,
    KeyResultUpdate,
    OkrCreate,
    OkrDetailOut,
    OkrListOut,
    OkrOut,
    OkrStatsOut,
    OkrUpdate,
)
from app.services import okr as okr_service

router = APIRouter(prefix="/okrs", tags=["OKR"])


@router.get("/stats", response_model=OkrStatsOut, summary="OKR 统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    period_label: Optional[str] = None,
) -> OkrStatsOut:
    return OkrStatsOut(**okr_service.okr_stats(db, current_user, period_label=period_label))


@router.get("", response_model=OkrListOut, summary="OKR 列表")
def list_okrs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    status: Optional[str] = None,
    level: Optional[str] = None,
    period_label: Optional[str] = None,
    keyword: Optional[str] = None,
    scope: Optional[str] = Query(None, description="mine/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> OkrListOut:
    total, items = okr_service.list_okrs(
        db,
        current_user,
        status=status,
        level=level,
        period_label=period_label,
        keyword=keyword,
        scope_filter=scope,
        page=page,
        page_size=page_size,
    )
    return OkrListOut(total=total, items=[OkrOut.model_validate(x) for x in items])


@router.post("", response_model=OkrOut, summary="创建 OKR")
def create_okr(
    payload: OkrCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> OkrOut:
    return OkrOut.model_validate(okr_service.create_okr(db, current_user, payload))


@router.get("/{okr_id}", response_model=OkrDetailOut, summary="OKR 详情")
def get_okr(
    okr_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> OkrDetailOut:
    return OkrDetailOut.model_validate(okr_service.get_okr_detail(db, current_user, okr_id))


@router.patch("/{okr_id}", response_model=OkrOut, summary="编辑 OKR")
def update_okr(
    okr_id: int,
    payload: OkrUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> OkrOut:
    return OkrOut.model_validate(okr_service.update_okr(db, current_user, okr_id, payload))


@router.post("/{okr_id}/confirm", response_model=OkrOut, summary="确认目标")
def confirm_okr(
    okr_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> OkrOut:
    return OkrOut.model_validate(okr_service.confirm_okr(db, current_user, okr_id))


@router.post("/{okr_id}/complete", response_model=OkrOut, summary="完成目标")
def complete_okr(
    okr_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> OkrOut:
    return OkrOut.model_validate(okr_service.complete_okr(db, current_user, okr_id))


@router.post("/{okr_id}/terminate", response_model=OkrOut, summary="终止目标")
def terminate_okr(
    okr_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
    reason: Optional[str] = None,
) -> OkrOut:
    return OkrOut.model_validate(okr_service.terminate_okr(db, current_user, okr_id, reason))


@router.post("/{okr_id}/key-results", response_model=KeyResultOut, summary="添加关键结果")
def add_key_result(
    okr_id: int,
    payload: KeyResultCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> KeyResultOut:
    return KeyResultOut.model_validate(okr_service.add_key_result(db, current_user, okr_id, payload))


@router.patch(
    "/{okr_id}/key-results/{kr_id}",
    response_model=KeyResultOut,
    summary="更新关键结果/进度",
)
def update_key_result(
    okr_id: int,
    kr_id: int,
    payload: KeyResultUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["okr:view"]))],
) -> KeyResultOut:
    return KeyResultOut.model_validate(
        okr_service.update_key_result(db, current_user, okr_id, kr_id, payload)
    )
