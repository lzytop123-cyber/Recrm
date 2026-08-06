"""审批规则服务。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.approval_rule import (
    RULE_STATUS_DISABLED,
    RULE_STATUS_DRAFT,
    RULE_STATUS_PUBLISHED,
    ApprovalRule,
)
from app.models.user import User
from app.schemas.approval_rule import (
    ApprovalRuleCreate,
    ApprovalRuleListOut,
    ApprovalRuleOut,
    ApprovalRuleUpdate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_rules(
    db: Session,
    *,
    biz_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> ApprovalRuleListOut:
    q = db.query(ApprovalRule)
    if biz_type:
        q = q.filter(ApprovalRule.biz_type == biz_type)
    if status:
        q = q.filter(ApprovalRule.status == status)
    total = q.count()
    rows = (
        q.order_by(ApprovalRule.id.desc())
        .offset(max(0, (page - 1) * page_size))
        .limit(page_size)
        .all()
    )
    return ApprovalRuleListOut(
        total=total,
        items=[ApprovalRuleOut.model_validate(r) for r in rows],
    )


def create_rule(db: Session, user: User, payload: ApprovalRuleCreate) -> ApprovalRule:
    exists = db.query(ApprovalRule).filter(ApprovalRule.code == payload.code).first()
    if exists:
        raise HTTPException(status_code=400, detail="规则编码已存在")
    row = ApprovalRule(
        code=payload.code.strip(),
        name=payload.name.strip(),
        biz_type=payload.biz_type.strip(),
        nodes_json=payload.nodes_json,
        conditions_json=payload.conditions_json,
        timeout_hours=payload.timeout_hours,
        version=1,
        status=RULE_STATUS_DRAFT,
        remark=payload.remark,
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_rule(db: Session, rule_id: int) -> ApprovalRule:
    row = db.query(ApprovalRule).filter(ApprovalRule.id == rule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="审批规则不存在")
    return row


def update_rule(db: Session, rule_id: int, payload: ApprovalRuleUpdate) -> ApprovalRule:
    row = get_rule(db, rule_id)
    if row.status == RULE_STATUS_PUBLISHED:
        raise HTTPException(status_code=400, detail="已发布规则请先停用再编辑，或新建版本")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_rule(db: Session, rule_id: int) -> None:
    row = get_rule(db, rule_id)
    if row.status == RULE_STATUS_PUBLISHED:
        raise HTTPException(status_code=400, detail="已发布规则不可删除，请先停用")
    db.delete(row)
    db.commit()


def publish_rule(db: Session, rule_id: int) -> ApprovalRule:
    row = get_rule(db, rule_id)
    if row.status == RULE_STATUS_PUBLISHED:
        return row
    if row.status == RULE_STATUS_DISABLED:
        row.version = (row.version or 1) + 1
    row.status = RULE_STATUS_PUBLISHED
    row.published_at = _now()
    db.commit()
    db.refresh(row)
    return row


def disable_rule(db: Session, rule_id: int) -> ApprovalRule:
    row = get_rule(db, rule_id)
    row.status = RULE_STATUS_DISABLED
    db.commit()
    db.refresh(row)
    return row


def get_published_rule(db: Session, biz_type: str) -> Optional[ApprovalRule]:
    """按业务类型取最新已发布规则；审批中心用于展示节点时限/版本。"""
    code = (biz_type or "").strip()
    if not code:
        return None
    return (
        db.query(ApprovalRule)
        .filter(
            ApprovalRule.biz_type == code,
            ApprovalRule.status == RULE_STATUS_PUBLISHED,
        )
        .order_by(ApprovalRule.published_at.desc(), ApprovalRule.id.desc())
        .first()
    )
