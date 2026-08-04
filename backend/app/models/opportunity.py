"""售前：商机表。对齐 PRD 商机阶段与原型「客户与商机」。"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

OPP_STAGE_CONTACT = "contact"
OPP_STAGE_NEED = "need_confirm"
OPP_STAGE_PROPOSAL = "proposal"
OPP_STAGE_NEGOTIATION = "negotiation"
OPP_STAGE_WON = "won"
OPP_STAGE_LOST = "lost"
OPP_STAGE_PAUSED = "paused"

OPP_STAGES = {
    OPP_STAGE_CONTACT,
    OPP_STAGE_NEED,
    OPP_STAGE_PROPOSAL,
    OPP_STAGE_NEGOTIATION,
    OPP_STAGE_WON,
    OPP_STAGE_LOST,
    OPP_STAGE_PAUSED,
}

OPP_STAGE_LABEL = {
    OPP_STAGE_CONTACT: "初步接触",
    OPP_STAGE_NEED: "需求确认",
    OPP_STAGE_PROPOSAL: "方案报价",
    OPP_STAGE_NEGOTIATION: "商务谈判",
    OPP_STAGE_WON: "赢单",
    OPP_STAGE_LOST: "输单",
    OPP_STAGE_PAUSED: "暂停",
}

# 开放阶段 → 下一阶段候选（赢/输/暂停始终可选，除已关闭）
OPP_OPEN_STAGES = {
    OPP_STAGE_CONTACT,
    OPP_STAGE_NEED,
    OPP_STAGE_PROPOSAL,
    OPP_STAGE_NEGOTIATION,
    OPP_STAGE_PAUSED,
}


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, comment="商机编号"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="商机名称")
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id"), nullable=False, index=True, comment="客户"
    )
    source_lead_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("leads.id"), nullable=True, comment="来源线索"
    )
    business_type: Mapped[str] = mapped_column(
        String(30), default="other", comment="ai_product/ai_custom/media_ops/other"
    )
    stage: Mapped[str] = mapped_column(
        String(30), default=OPP_STAGE_NEED, index=True, comment="商机阶段"
    )
    expected_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0, comment="预计金额"
    )
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    creator_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True
    )
    requirement_summary: Mapped[Optional[str]] = mapped_column(Text, comment="需求摘要")
    next_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_action_note: Mapped[Optional[str]] = mapped_column(String(500))
    lost_reason: Mapped[Optional[str]] = mapped_column(String(500))
    won_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    lost_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    activities: Mapped[list["OpportunityActivity"]] = relationship(
        "OpportunityActivity",
        back_populates="opportunity",
        cascade="all, delete-orphan",
    )


class OpportunityActivity(Base):
    __tablename__ = "opportunity_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("opportunities.id"), nullable=False, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    activity_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="follow/stage_change/create"
    )
    content: Mapped[Optional[str]] = mapped_column(Text)
    evidence: Mapped[Optional[str]] = mapped_column(Text, comment="依据/证据说明")
    from_stage: Mapped[Optional[str]] = mapped_column(String(30))
    to_stage: Mapped[Optional[str]] = mapped_column(String(30))
    next_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    opportunity: Mapped["Opportunity"] = relationship("Opportunity", back_populates="activities")
