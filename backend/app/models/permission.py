"""
RBAC：权限表。
code 形如 module:action，例如 lead:view、contract:create。
"""
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import role_permissions

if TYPE_CHECKING:
    from app.models.role import Role


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="权限名称")
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="权限编码")
    module: Mapped[Optional[str]] = mapped_column(String(50), comment="所属模块")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="说明")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )
