"""审批规则：定义业务类型节点与超时策略。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

RULE_STATUS_DRAFT = "draft"
RULE_STATUS_PUBLISHED = "published"
RULE_STATUS_DISABLED = "disabled"

RULE_STATUSES = {
    RULE_STATUS_DRAFT,
    RULE_STATUS_PUBLISHED,
    RULE_STATUS_DISABLED,
}


class ApprovalRule(Base):
    __tablename__ = "approval_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="业务类型")
    nodes_json: Mapped[str] = mapped_column(Text, nullable=False, comment="审批节点 JSON")
    conditions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="条件 JSON")
    timeout_hours: Mapped[int] = mapped_column(Integer, default=72, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=RULE_STATUS_DRAFT, nullable=False, index=True
    )
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
