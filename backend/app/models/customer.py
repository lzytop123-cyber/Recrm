"""
售前：客户表。
可由线索转化而来；字段对齐 PRD 3.1。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 客户状态（PRD：潜在 / 合作中 / 暂停 / 终止）
CUSTOMER_STATUS_POTENTIAL = "potential"
CUSTOMER_STATUS_ACTIVE = "active"
CUSTOMER_STATUS_PAUSED = "paused"
CUSTOMER_STATUS_TERMINATED = "terminated"

CUSTOMER_STATUSES = {
    CUSTOMER_STATUS_POTENTIAL,
    CUSTOMER_STATUS_ACTIVE,
    CUSTOMER_STATUS_PAUSED,
    CUSTOMER_STATUS_TERMINATED,
}

CUSTOMER_STATUS_LABEL = {
    CUSTOMER_STATUS_POTENTIAL: "潜在",
    CUSTOMER_STATUS_ACTIVE: "合作中",
    CUSTOMER_STATUS_PAUSED: "暂停",
    CUSTOMER_STATUS_TERMINATED: "终止",
}


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True, comment="客户名称")
    short_name: Mapped[Optional[str]] = mapped_column(String(100), comment="客户简称")
    contact_name: Mapped[Optional[str]] = mapped_column(String(50), comment="主要联系人")
    phone: Mapped[Optional[str]] = mapped_column(String(30), index=True, comment="电话")
    email: Mapped[Optional[str]] = mapped_column(String(100), comment="邮箱")
    industry: Mapped[Optional[str]] = mapped_column(String(50), comment="行业")
    company_size: Mapped[Optional[str]] = mapped_column(
        String(30), comment="公司规模：startup/sme/large/group"
    )
    address: Mapped[Optional[str]] = mapped_column(String(300), comment="客户地址")
    source: Mapped[Optional[str]] = mapped_column(String(50), comment="客户来源")
    status: Mapped[str] = mapped_column(
        String(30), default=CUSTOMER_STATUS_POTENTIAL, index=True, comment="客户状态"
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True, comment="负责销售"
    )
    creator_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="创建人"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, comment="所属部门"
    )
    source_lead_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("leads.id"), nullable=True, comment="来源线索"
    )
    last_followed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近跟进时间"
    )
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    follow_ups: Mapped[list["CustomerFollowUp"]] = relationship(
        "CustomerFollowUp",
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class CustomerFollowUp(Base):
    """客户跟进记录（PRD 3.1）。"""

    __tablename__ = "customer_follow_ups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    follow_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    method: Mapped[str] = mapped_column(String(30), default="phone", comment="电话/微信/邮件/面谈")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    next_follow_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship("Customer", back_populates="follow_ups")
