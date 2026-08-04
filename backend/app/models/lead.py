"""
线索池：线索主表。
状态与字段对齐《子系统设计-线索池》。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# 线索状态（文档 2.2）
LEAD_STATUS_PENDING = "pending_assign"  # 待分配 / 公海
LEAD_STATUS_ASSIGNED = "assigned"  # 已分配，等待首次跟进
LEAD_STATUS_FOLLOWING = "following"  # 跟进中
LEAD_STATUS_CONVERTED = "converted"  # 已转化
LEAD_STATUS_RETURNED = "returned"  # 已退回公海
LEAD_STATUS_LOST = "lost"  # 已流失

LEAD_STATUSES = {
    LEAD_STATUS_PENDING,
    LEAD_STATUS_ASSIGNED,
    LEAD_STATUS_FOLLOWING,
    LEAD_STATUS_CONVERTED,
    LEAD_STATUS_RETURNED,
    LEAD_STATUS_LOST,
}

# 来源类型（文档 2.1，骨架期用枚举值）
LEAD_SOURCES = {
    "manual": "手动录入",
    "import": "批量导入",
    "api": "API接入",
    "im": "飞书/企微导入",
    "external": "外部线索筛选",
    "website": "官网",
    "ad": "广告投放",
    "event": "展会/活动",
    "referral": "转介绍",
    "other": "其他",
}


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # —— 联系人 / 公司 ——
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="联系人姓名")
    company_name: Mapped[Optional[str]] = mapped_column(String(200), index=True, comment="公司名称")
    credit_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True, comment="统一社会信用代码"
    )
    company_domain: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True, comment="企业域名"
    )
    phone: Mapped[Optional[str]] = mapped_column(String(30), index=True, comment="联系电话")
    email: Mapped[Optional[str]] = mapped_column(String(100), comment="邮箱")
    region: Mapped[Optional[str]] = mapped_column(String(100), comment="地区")

    # —— 需求信息（完整录入） ——
    source: Mapped[str] = mapped_column(String(50), default="manual", comment="来源类型编码")
    source_detail: Mapped[Optional[str]] = mapped_column(String(200), comment="来源明细")
    need_desc: Mapped[Optional[str]] = mapped_column(Text, comment="需求描述")
    budget: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), comment="预算")
    expected_deal_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="预计成交时间")
    business_type: Mapped[Optional[str]] = mapped_column(
        String(50), comment="业务类型：ai_product / ai_custom / media_ops"
    )

    # —— 状态与归属 ——
    status: Mapped[str] = mapped_column(
        String(30), default=LEAD_STATUS_PENDING, index=True, comment="线索状态"
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True, comment="当前跟进人"
    )
    creator_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="录入人"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, comment="所属部门"
    )

    # —— 保护期 ——
    protect_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="保护期截止时间"
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近一次分配时间"
    )
    last_followed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近跟进时间"
    )

    # —— 转化 / 流失 ——
    converted_customer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("customers.id"), nullable=True, comment="转化后的客户"
    )
    converted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="转化时间")
    lost_reason: Mapped[Optional[str]] = mapped_column(String(500), comment="流失原因")
    lost_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="流失时间")

    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    follow_ups: Mapped[list["LeadFollowUp"]] = relationship(
        "LeadFollowUp",
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    logs: Mapped[list["LeadLog"]] = relationship(
        "LeadLog",
        back_populates="lead",
        cascade="all, delete-orphan",
    )


class LeadFollowUp(Base):
    """跟进记录（文档 3.3）。"""

    __tablename__ = "lead_follow_ups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    follow_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="跟进时间")
    method: Mapped[str] = mapped_column(String(30), default="phone", comment="电话/微信/邮件/面谈/会议")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="沟通内容")
    customer_feedback: Mapped[Optional[str]] = mapped_column(Text, comment="客户反馈")
    result: Mapped[str] = mapped_column(
        String(30), default="keep", comment="推进 advance / 保持 keep / 退回 return / 流失 lost"
    )
    next_follow_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), comment="下次跟进时间"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped["Lead"] = relationship("Lead", back_populates="follow_ups")


class LeadLog(Base):
    """线索操作日志（文档 3.6，不可篡改追加写）。"""

    __tablename__ = "lead_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(50), comment="操作人用户名快照")
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="create/assign/claim/follow/transfer/return/recycle/convert/lost/edit"
    )
    detail: Mapped[Optional[str]] = mapped_column(Text, comment="变更说明/JSON 摘要")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped["Lead"] = relationship("Lead", back_populates="logs")
