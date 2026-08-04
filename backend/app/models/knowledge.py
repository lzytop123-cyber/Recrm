"""
AI 知识库：空间、知识源、知识条目。
对齐高保真原型 pageKnowledge（飞书源授权 + 可追溯问答）。
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

SOURCE_TYPE_FEISHU_CHAT = "feishu_chat"
SOURCE_TYPE_FEISHU_DOC = "feishu_doc"
SOURCE_TYPE_MANUAL = "manual"

SOURCE_TYPES = {SOURCE_TYPE_FEISHU_CHAT, SOURCE_TYPE_FEISHU_DOC, SOURCE_TYPE_MANUAL}

SOURCE_STATUS_ACTIVE = "active"
SOURCE_STATUS_SYNCING = "syncing"
SOURCE_STATUS_FAILED = "failed"
SOURCE_STATUS_PENDING = "pending"

ARTICLE_STATUS_DRAFT = "draft"
ARTICLE_STATUS_PENDING_REVIEW = "pending_review"
ARTICLE_STATUS_PUBLISHED = "published"
ARTICLE_STATUS_ARCHIVED = "archived"


class KnowledgeSpace(Base):
    __tablename__ = "knowledge_spaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    icon: Mapped[str] = mapped_column(String(8), default="知")
    description: Mapped[Optional[str]] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    space_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("knowledge_spaces.id"), index=True)
    external_ref: Mapped[Optional[str]] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default=SOURCE_STATUS_PENDING, index=True)
    authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sync_error: Mapped[Optional[str]] = mapped_column(String(300))
    creator_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_spaces.id"), nullable=False, index=True)
    source_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("knowledge_sources.id"), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String(500))
    keywords: Mapped[Optional[str]] = mapped_column(String(300), comment="逗号分隔关键词，用于检索")
    version: Mapped[str] = mapped_column(String(20), default="V1.0")
    status: Mapped[str] = mapped_column(String(30), default=ARTICLE_STATUS_PUBLISHED, index=True)
    source_label: Mapped[Optional[str]] = mapped_column(String(80), comment="展示用来源类型文案")
    published_at: Mapped[Optional[date]] = mapped_column(Date)
    creator_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
