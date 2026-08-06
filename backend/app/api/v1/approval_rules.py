"""审批规则 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.approval_rule import (
    ApprovalRuleCreate,
    ApprovalRuleListOut,
    ApprovalRuleOut,
    ApprovalRuleUpdate,
)
from app.services import approval_rule as rule_service

router = APIRouter(prefix="/approval-rules", tags=["审批规则"])


@router.get("", response_model=ApprovalRuleListOut, summary="审批规则列表（已发布规则会写入审批单 meta）")
def list_rules(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
    biz_type: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApprovalRuleListOut:
    _ = current_user
    return rule_service.list_rules(
        db, biz_type=biz_type, status=status, page=page, page_size=page_size
    )


@router.post("", response_model=ApprovalRuleOut, summary="创建审批规则")
def create_rule(
    payload: ApprovalRuleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> ApprovalRuleOut:
    return ApprovalRuleOut.model_validate(rule_service.create_rule(db, current_user, payload))


@router.get("/{rule_id}", response_model=ApprovalRuleOut, summary="审批规则详情")
def get_rule(
    rule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> ApprovalRuleOut:
    _ = current_user
    return ApprovalRuleOut.model_validate(rule_service.get_rule(db, rule_id))


@router.patch("/{rule_id}", response_model=ApprovalRuleOut, summary="更新审批规则")
def update_rule(
    rule_id: int,
    payload: ApprovalRuleUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> ApprovalRuleOut:
    _ = current_user
    return ApprovalRuleOut.model_validate(rule_service.update_rule(db, rule_id, payload))


@router.delete("/{rule_id}", summary="删除审批规则")
def delete_rule(
    rule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> dict:
    _ = current_user
    rule_service.delete_rule(db, rule_id)
    return {"ok": True, "message": "已删除"}


@router.post("/{rule_id}/publish", response_model=ApprovalRuleOut, summary="发布审批规则")
def publish_rule(
    rule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> ApprovalRuleOut:
    _ = current_user
    return ApprovalRuleOut.model_validate(rule_service.publish_rule(db, rule_id))


@router.post("/{rule_id}/disable", response_model=ApprovalRuleOut, summary="停用审批规则")
def disable_rule(
    rule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["approval:center"]))],
) -> ApprovalRuleOut:
    _ = current_user
    return ApprovalRuleOut.model_validate(rule_service.disable_rule(db, rule_id))
