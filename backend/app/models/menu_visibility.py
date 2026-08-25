"""
菜单可见性覆盖表：按角色对某个菜单强制可见/隐藏。
命中一条即覆盖默认 (角色白名单 / 销售隐藏工单) 逻辑。
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MenuVisibility(Base):
    __tablename__ = "menu_visibility"
    __table_args__ = (
        UniqueConstraint("role_code", "menu_path", name="uq_menu_visibility_role_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    menu_path: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
