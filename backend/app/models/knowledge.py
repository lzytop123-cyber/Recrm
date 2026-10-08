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
SOURCE_STATUS_REVOKED = "revoked"

ARTICLE_STATUS_DRAFT = "draft"
ARTICLE_STATUS_PENDING_REVIEW = "pending_review"
ARTICLE_STATUS_REVIEWED = "reviewed"
ARTICLE_STATUS_PUBLISHED = "published"
ARTICLE_STATUS_DISABLED = "disabled"
ARTICLE_STATUS_ARCHIVED = "archived"
ARTICLE_STATUS_REJECTED = "rejected"

ARTICLE_ORIGIN_MANUAL = "manual"
ARTICLE_ORIGIN_FEISHU_DOC = "feishu_doc"
ARTICLE_ORIGIN_FEISHU_CHAT = "feishu_chat"
ARTICLE_ORIGIN_AI = "ai"

DOC_TYPE_QA = "qa"
DOC_TYPE_DOC = "doc"
DOC_TYPE_NOTE = "note"
DOC_TYPE_GUIDE = "guide"
DOC_TYPE_POLICY = "policy"
DOC_TYPE_CASE = "case"
DOC_TYPE_FAQ = "faq"
DOC_TYPES = {
    DOC_TYPE_QA,
    DOC_TYPE_DOC,
    DOC_TYPE_NOTE,
    DOC_TYPE_GUIDE,
    DOC_TYPE_POLICY,
    DOC_TYPE_CASE,
    DOC_TYPE_FAQ,
}

VISIBILITY_INHERIT = "inherit"
VISIBILITY_DEPARTMENT = "department"
VISIBILITY_ALL = "all"
VISIBILITIES = {VISIBILITY_INHERIT, VISIBILITY_DEPARTMENT, VISIBILITY_ALL}

SORT_RECENT = "recent"
SORT_TITLE = "title"
ENTRY_SORTS = {SORT_RECENT, SORT_TITLE}

ARTICLE_ACTION_DRAFT = "draft"
ARTICLE_ACTION_SUBMIT = "submit"
ARTICLE_ACTION_PUBLISH = "publish"
ARTICLE_ACTIONS = {ARTICLE_ACTION_DRAFT, ARTICLE_ACTION_SUBMIT, ARTICLE_ACTION_PUBLISH}

CRAWL_CONFIG_KEY = "knowledge.feishu_crawl_enabled"

FEEDBACK_USEFUL = "useful"
FEEDBACK_USELESS = "useless"
FEEDBACK_CORRECTION = "correction"
FEEDBACK_PENDING = "pending"
FEEDBACK_ACCEPTED = "accepted"
FEEDBACK_REJECTED = "rejected"

JOB_STATUS_RUNNING = "running"
JOB_STATUS_DONE = "done"
JOB_STATUS_FAILED = "failed"


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
    external_ref: Mapped[Optional[str]] = mapped_column(String(300))
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
    keywords: Mapped[Optional[str]] = mapped_column(String(300), comment="逗号分隔关键词/标签")
    doc_type: Mapped[str] = mapped_column(String(20), default=DOC_TYPE_QA)
    origin: Mapped[str] = mapped_column(String(30), default=ARTICLE_ORIGIN_MANUAL, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(300))
    source_note: Mapped[Optional[str]] = mapped_column(String(300), comment="来源说明")
    visibility: Mapped[str] = mapped_column(String(20), default=VISIBILITY_INHERIT)
    visibility_department: Mapped[Optional[str]] = mapped_column(String(80), comment="可见部门名称")
    expires_at: Mapped[Optional[date]] = mapped_column(Date, comment="有效期截止日，空=长期")
    reject_reason: Mapped[Optional[str]] = mapped_column(String(500), comment="最近一次退回修改意见")
    attachments_json: Mapped[Optional[str]] = mapped_column(Text, comment="附件 JSON [{filename,path}]")
    attachment_text: Mapped[Optional[str]] = mapped_column(Text, comment="附件抽取文本，供检索/问答")
    version: Mapped[str] = mapped_column(String(20), default="V1.0")
    status: Mapped[str] = mapped_column(String(30), default=ARTICLE_STATUS_PUBLISHED, index=True)
    source_label: Mapped[Optional[str]] = mapped_column(String(80), comment="展示用来源类型文案")
    published_at: Mapped[Optional[date]] = mapped_column(Date)
    creator_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeArticleVersion(Base):
    __tablename__ = "knowledge_article_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_articles.id"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String(500))
    change_reason: Mapped[Optional[str]] = mapped_column(String(300))
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeJob(Base):
    __tablename__ = "knowledge_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("knowledge_sources.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False, default="sync")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=JOB_STATUS_RUNNING, index=True)
    error: Mapped[Optional[str]] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class KnowledgeAsk(Base):
    __tablename__ = "knowledge_asks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeFeedback(Base):
    __tablename__ = "knowledge_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ask_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_asks.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=FEEDBACK_PENDING, index=True)
    resolution: Mapped[Optional[str]] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=1)
    last_asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
