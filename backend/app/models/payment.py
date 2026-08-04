"""
售前：收款/回款表。
对应合同的应收计划与收款记录（PRD 3.4 精简版）。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 收款记录状态
PAYMENT_STATUS_PENDING = "pending"  # 待收款 / 未确认
PAYMENT_STATUS_PENDING_REVIEW = "pending_review"  # 到款认领待财务复核
PAYMENT_STATUS_CONFIRMED = "confirmed"  # 已确认到账 / 已核销
PAYMENT_STATUS_REFUNDED = "refunded"  # 已退款

PAYMENT_STATUSES = {
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_PENDING_REVIEW,
    PAYMENT_STATUS_CONFIRMED,
    PAYMENT_STATUS_REFUNDED,
}

PAYMENT_STATUS_LABEL = {
    PAYMENT_STATUS_PENDING: "待收款",
    PAYMENT_STATUS_PENDING_REVIEW: "待复核",
    PAYMENT_STATUS_CONFIRMED: "已确认",
    PAYMENT_STATUS_REFUNDED: "已退款",
}

PAYMENT_RECORD_PLAN = "plan"
PAYMENT_RECORD_CLAIM = "claim"

PAYMENT_METHODS = {
    "bank": "银行转账",
    "alipay": "支付宝",
    "wechat": "微信",
    "cash": "现金",
    "other": "其他",
}


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_no: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True, comment="应收/认领单号"
    )
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contracts.id"), nullable=False, index=True, comment="所属合同"
    )
    record_type: Mapped[str] = mapped_column(
        String(20), default=PAYMENT_RECORD_PLAN, index=True, comment="plan应收/claim认领"
    )
    title: Mapped[Optional[str]] = mapped_column(String(100), comment="期次/款项名称")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, comment="应收/收款金额")
    due_date: Mapped[Optional[date]] = mapped_column(Date, index=True, comment="应收日期")
    paid_date: Mapped[Optional[date]] = mapped_column(Date, comment="实际收款日期")
    status: Mapped[str] = mapped_column(
        String(30), default=PAYMENT_STATUS_PENDING, index=True, comment="收款状态"
    )
    method: Mapped[Optional[str]] = mapped_column(String(50), comment="收款方式")
    payer_name: Mapped[Optional[str]] = mapped_column(String(200), comment="付款方")
    account_tail: Mapped[Optional[str]] = mapped_column(String(10), comment="收款账户末四位")
    proof_filename: Mapped[Optional[str]] = mapped_column(String(255), comment="到账证明文件名")
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True, comment="登记人/负责人"
    )
    creator_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="创建人"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, comment="所属部门"
    )
    confirmed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="确认人"
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
