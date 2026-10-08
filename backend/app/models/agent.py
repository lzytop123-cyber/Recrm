"""智能体会话与消息。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 对外会话 ID（UUID 字符串），与 LangGraph thread 对齐
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[List["AgentMessage"]] = relationship(
        "AgentMessage", back_populates="conversation", cascade="all, delete-orphan"
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agent_conversations.id"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant / tool
    content: Mapped[Optional[str]] = mapped_column(Text)
    tool_calls: Mapped[Optional[Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["AgentConversation"] = relationship(
        "AgentConversation", back_populates="messages"
    )


class AiSceneRun(Base):
    """S2–S5 场景调用留痕。日报草稿在此确认提交，不另开表。"""

    __tablename__ = "ai_scene_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scene: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="done")
    target_id: Mapped[Optional[str]] = mapped_column(String(64))
    result: Mapped[Optional[Any]] = mapped_column(JSON)
    body: Mapped[Optional[str]] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="facts-v1")
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AiPrompt(Base):
    """场景 Prompt。同一 code 多行即版本，同时只有一条 published。"""

    __tablename__ = "ai_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentMemory(Base):
    """跨会话的用户事实。一人一行。"""

    __tablename__ = "agent_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
