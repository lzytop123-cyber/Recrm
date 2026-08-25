"""
售前：合同表。
状态与字段对齐 PRD 3.3（简化审批链路；起草需上传合同证明）。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 合同状态（PRD 流转精简版）
CONTRACT_STATUS_DRAFT = "draft"
CONTRACT_STATUS_PENDING_APPROVAL = "pending_approval"
CONTRACT_STATUS_APPROVED = "approved"
CONTRACT_STATUS_SIGNED = "signed"
CONTRACT_STATUS_ACTIVE = "active"  # 执行中
CONTRACT_STATUS_COMPLETED = "completed"
CONTRACT_STATUS_TERMINATED = "terminated"

CONTRACT_STATUSES = {
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_PENDING_APPROVAL,
    CONTRACT_STATUS_APPROVED,
    CONTRACT_STATUS_SIGNED,
    CONTRACT_STATUS_ACTIVE,
    CONTRACT_STATUS_COMPLETED,
    CONTRACT_STATUS_TERMINATED,
}

CONTRACT_STATUS_LABEL = {
    CONTRACT_STATUS_DRAFT: "草稿",
    CONTRACT_STATUS_PENDING_APPROVAL: "待审批",
    CONTRACT_STATUS_APPROVED: "已审批",
    CONTRACT_STATUS_SIGNED: "已签署",
    CONTRACT_STATUS_ACTIVE: "执行中",
    CONTRACT_STATUS_COMPLETED: "已完成",
    CONTRACT_STATUS_TERMINATED: "已终止",
}

# 合同类型（三类业务）
CONTRACT_TYPES = {
    "ai_product": "AI产品销售",
    "ai_custom": "AI定制开发",
    "media_ops": "自媒体代运营",
    "other": "其他",
}


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, comment="合同编号"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="合同名称")
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id"), nullable=False, index=True, comment="客户"
    )
    opportunity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("opportunities.id"), nullable=True, index=True, comment="来源商机"
    )
    contract_type: Mapped[str] = mapped_column(
        String(30), default="other", comment="ai_product/ai_custom/media_ops/other"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0, comment="合同金额"
    )
    currency: Mapped[str] = mapped_column(String(10), default="CNY", comment="币种")
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(30), comment="一次性/分期/按里程碑"
    )
    status: Mapped[str] = mapped_column(
        String(30), default=CONTRACT_STATUS_DRAFT, index=True, comment="合同状态"
    )
    signed_date: Mapped[Optional[date]] = mapped_column(Date, comment="签署日期")
    effective_date: Mapped[Optional[date]] = mapped_column(Date, comment="生效日期")
    expire_date: Mapped[Optional[date]] = mapped_column(Date, comment="到期日期")
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True, comment="负责人"
    )
    creator_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="创建人"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, comment="所属部门"
    )
    approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="审批人"
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    terminate_reason: Mapped[Optional[str]] = mapped_column(String(500), comment="终止原因")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="内容版本号")
    modification_snapshot_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="待审批的合同修改快照 JSON"
    )
    proof_filename: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="合同证明原文件名（首张，兼容旧字段）"
    )
    proof_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="合同证明相对路径（首张，兼容旧字段）"
    )
    proof_files_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment='合同证明多文件 JSON [{"filename","path"}]'
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
