"""
操作日志表：记录关键写操作，便于审计。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, comment="操作人 id")
    username: Mapped[Optional[str]] = mapped_column(String(50), comment="操作人用户名")
    action: Mapped[str] = mapped_column(String(50), nullable=False, comment="动作，如 login/create")
    module: Mapped[Optional[str]] = mapped_column(String(50), comment="模块")
    target_type: Mapped[Optional[str]] = mapped_column(String(50), comment="对象类型")
    target_id: Mapped[Optional[str]] = mapped_column(String(50), comment="对象 id")
    ip: Mapped[Optional[str]] = mapped_column(String(50), comment="客户端 IP")
    detail: Mapped[Optional[str]] = mapped_column(Text, comment="详情 JSON/文本")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
