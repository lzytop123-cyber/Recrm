"""Agent API schemas。"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(
        default=None, description="会话 ID；不传则新建"
    )
    page_context: Optional[dict[str, Any]] = None


class ConfirmRequest(BaseModel):
    conversation_id: str
    confirmed: bool = True


class ConversationOut(BaseModel):
    id: str
    title: Optional[str] = None
    updated_at: Optional[str] = None


class HistoryMessageOut(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[Any] = None
    created_at: Optional[str] = None
