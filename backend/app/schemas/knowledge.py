"""AI 知识库 schemas。"""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class KnowledgeSpaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    code: Optional[str] = Field(None, min_length=1, max_length=40, description="唯一编码，不传则自动生成")
    icon: Optional[str] = Field(None, max_length=8)
    description: Optional[str] = Field(None, max_length=200)


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
    source_type: str = Field(..., description="feishu_doc / feishu_chat / manual")
    space_id: Optional[int] = None
    external_ref: Optional[str] = Field(None, max_length=300)
    remark: Optional[str] = None
    auto_sync: bool = True


class KnowledgeWhitelistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    external_ref: str = Field(..., min_length=1, max_length=300)
    space_id: Optional[int] = None


class KnowledgeAttachmentIn(BaseModel):
    filename: Optional[str] = Field(None, max_length=255)
    path: Optional[str] = Field(None, max_length=500)
    url: Optional[str] = Field(None, max_length=500)


class KnowledgeAttachmentOut(BaseModel):
    filename: str
    path: str
    url: str
    download_url: str = ""


def _coerce_attachment_list(value):
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return [{"path": value}]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [{"path": x} if isinstance(x, str) else x for x in value]
    return value


class KnowledgeArticleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    space_id: int
    keywords: Optional[str] = Field(None, max_length=300)
    summary: Optional[str] = Field(None, max_length=500)
    doc_type: str = Field(
        default="qa",
        description="qa / doc / note / guide / policy / case / faq",
    )
    source_url: Optional[str] = Field(None, max_length=300)
    source_note: Optional[str] = Field(None, max_length=300)
    visibility: str = Field(default="inherit", description="inherit / department / all")
    visibility_department: Optional[str] = Field(None, max_length=80)
    expires_at: Optional[date] = Field(None, description="有效期截止日，空=长期")
    action: str = Field(default="submit", description="draft / submit / publish")
    attachments: Optional[List[KnowledgeAttachmentIn]] = None
    attachment: Optional[str] = Field(
        None, max_length=500, description="单个附件路径，填 POST /uploads 返回的 path 或 url"
    )

    @field_validator("attachments", mode="before")
    @classmethod
    def coerce_attachments(cls, value):
        return _coerce_attachment_list(value)


class KnowledgeArticlePatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    keywords: Optional[str] = Field(None, max_length=300)
    summary: Optional[str] = Field(None, max_length=500)
    space_id: Optional[int] = None
    doc_type: Optional[str] = None
    source_url: Optional[str] = Field(None, max_length=300)
    source_note: Optional[str] = Field(None, max_length=300)
    visibility: Optional[str] = Field(None, description="inherit / department / all")
    visibility_department: Optional[str] = Field(None, max_length=80)
    expires_at: Optional[date] = None
    attachments: Optional[List[KnowledgeAttachmentIn]] = None
    attachment: Optional[str] = Field(
        None, max_length=500, description="单个附件路径，填 POST /uploads 返回的 path 或 url"
    )

    @field_validator("attachments", mode="before")
    @classmethod
    def coerce_attachments(cls, value):
        return _coerce_attachment_list(value)


class KnowledgeApproveIn(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    summary: Optional[str] = Field(None, max_length=500)


class KnowledgeRejectIn(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500, description="退回修改意见")


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
    article_count: int = 0
    creator_id: Optional[int] = None


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
    doc_type: str = "qa"
    origin: str = "manual"
    version: str
    status: str
    source_label: Optional[str] = None
    source_url: Optional[str] = None
    source_note: Optional[str] = None
    visibility: str = "inherit"
    visibility_department: Optional[str] = None
    expires_at: Optional[date] = None
    reject_reason: Optional[str] = None
    attachments: List[KnowledgeAttachmentOut] = Field(default_factory=list)
    published_at: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def source(self) -> str:
        """列表「来源」列：优先 source_label，否则按 origin 映射。"""
        if (self.source_label or "").strip():
            return self.source_label.strip()  # type: ignore[union-attr]
        return {
            "manual": "人工录入",
            "feishu_doc": "飞书文档同步",
            "feishu_chat": "飞书会话抓取",
            "ai": "AI 草稿",
        }.get(self.origin or "", self.origin or "—")

    @computed_field
    @property
    def attachment_name(self) -> Optional[str]:
        names = [a.filename for a in self.attachments if a.filename]
        return "、".join(names) or None

    @computed_field
    @property
    def images(self) -> List[str]:
        return [
            a.url
            for a in self.attachments
            if a.url
            and (a.filename or "").lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))
        ]


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
    source_url: Optional[str] = None


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
    ask_id: Optional[int] = None


class KnowledgeSourceListOut(BaseModel):
    total: int
    items: List[KnowledgeSourceOut]


class KnowledgeSourceSyncStatusOut(BaseModel):
    source_id: int
    status: str
    last_sync_at: Optional[datetime] = None
    article_count: int = 0
    sync_error: Optional[str] = None


class KnowledgeEntryOut(KnowledgeArticleOut):
    chunks: List[str] = []


class KnowledgeEntryListOut(BaseModel):
    total: int
    items: List[KnowledgeArticleOut]


class KnowledgeCorrectionIn(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    summary: Optional[str] = Field(None, max_length=500)
    reason: Optional[str] = Field(None, max_length=300)


class KnowledgeVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    article_id: int
    version: str
    title: str
    content: str
    summary: Optional[str] = None
    change_reason: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime


class KnowledgeJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: Optional[int] = None
    job_type: str
    status: str
    error: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None


class KnowledgeJobListOut(BaseModel):
    total: int
    items: List[KnowledgeJobOut]


class KnowledgeFeedbackIn(BaseModel):
    kind: str = Field(..., description="useful / useless / correction")
    content: Optional[str] = Field(None, max_length=1000)


class KnowledgeFeedbackPatch(BaseModel):
    status: str = Field(..., description="accepted / rejected")
    resolution: Optional[str] = Field(None, max_length=300)


class KnowledgeFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ask_id: int
    user_id: int
    kind: str
    content: Optional[str] = None
    status: str
    resolution: Optional[str] = None
    question: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeGapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keyword: str
    hit_count: int
    last_asked_at: datetime


class KnowledgeStatsOut(BaseModel):
    total_articles: int = 0
    published: int = 0
    pending_review: int = 0
    disabled: int = 0
    archived: int = 0
    sources_active: int = 0
    sources_failed: int = 0
    ask_count: int = 0
    ask_hit_rate: float = 0
    no_result_count: int = 0
    feedback_pending: int = 0


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


class KnowledgeSyncConfigPatch(BaseModel):
    crawl_enabled: bool


class KnowledgeSyncConfigOut(BaseModel):
    crawl_enabled: bool
    chats: List[KnowledgeSourceOut]
    folders: List[KnowledgeSourceOut]
