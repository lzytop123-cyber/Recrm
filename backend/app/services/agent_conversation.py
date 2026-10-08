"""智能体会话持久化。"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.agent import AgentConversation, AgentMessage


def get_or_create(
    db: Session, user_id: int, public_id: str, *, title: Optional[str] = None
) -> AgentConversation:
    conv = (
        db.query(AgentConversation)
        .filter(AgentConversation.public_id == public_id, AgentConversation.user_id == user_id)
        .first()
    )
    if conv:
        return conv
    conv = AgentConversation(
        public_id=public_id,
        user_id=user_id,
        title=(title or "新对话")[:200],
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def append_message(
    db: Session,
    conversation: AgentConversation,
    *,
    role: str,
    content: str,
    tool_calls: Any = None,
) -> AgentMessage:
    msg = AgentMessage(
        conversation_id=conversation.id,
        role=role,
        content=content,
        tool_calls=tool_calls,
    )
    db.add(msg)
    if role == "user" and (not conversation.title or conversation.title == "新对话"):
        conversation.title = (content or "新对话").strip()[:40] or "新对话"
    db.commit()
    db.refresh(msg)
    return msg


def list_by_user(db: Session, user_id: int, *, limit: int = 30) -> list[AgentConversation]:
    return (
        db.query(AgentConversation)
        .filter(AgentConversation.user_id == user_id)
        .order_by(AgentConversation.updated_at.desc())
        .limit(limit)
        .all()
    )


def get_messages(db: Session, user_id: int, public_id: str) -> list[AgentMessage]:
    conv = (
        db.query(AgentConversation)
        .filter(AgentConversation.public_id == public_id, AgentConversation.user_id == user_id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return (
        db.query(AgentMessage)
        .filter(AgentMessage.conversation_id == conv.id)
        .order_by(AgentMessage.id.asc())
        .all()
    )
