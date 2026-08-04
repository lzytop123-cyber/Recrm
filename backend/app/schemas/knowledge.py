"""AI 知识库 schemas。"""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeSpaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    icon: str
    description: Optional[str] = None
    sort_order: int = 0
    article_count: int = 0


class KnowledgeSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    source_type: str = Field(..., description="feishu_chat / feishu_doc / manual")
    space_id: Optional[int] = None
    external_ref: Optional[str] = None
    remark: Optional[str] = None


class KnowledgeSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str
    space_id: Optional[int] = None
    space_name: Optional[str] = None
    external_ref: Optional[str] = None
    status: str
    authorized: bool
    last_sync_at: Optional[datetime] = None
    sync_error: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    space_id: int
    space_name: Optional[str] = None
    source_id: Optional[int] = None
    content: str
    summary: Optional[str] = None
    keywords: Optional[str] = None
    version: str
    status: str
    source_label: Optional[str] = None
    published_at: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeAskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    space_id: Optional[int] = None


class KnowledgeCitation(BaseModel):
    article_id: int
    title: str
    source_label: str
    version: str
    updated_at: Optional[str] = None
    snippet: Optional[str] = None


class KnowledgeAskOut(BaseModel):
    question: str
    answer_html: str
    citations: List[KnowledgeCitation]
    retrieved_at: str
    matched_count: int
    answer_mode: str = Field(
        default="retrieve",
        description="llm=DeepSeek 生成；retrieve=检索拼接或未命中",
    )


class KnowledgeSyncStats(BaseModel):
    authorized_chats: int = 0
    doc_dirs: int = 0
    pending_review: int = 0
    sync_failed: int = 0
    status: str = "正常"


class KnowledgeWorkbenchOut(BaseModel):
    spaces: List[KnowledgeSpaceOut]
    sources: List[KnowledgeSourceOut]
    articles: List[KnowledgeArticleOut]
    sync_stats: KnowledgeSyncStats
    total_published: int
    can_manage: bool
