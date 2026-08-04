"""
用户表。
账号密码登录 + 飞书 OAuth（feishu_open_id 绑定）。
"""
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import user_roles

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.employee_hr import EmployeeHistoryEvent, FeishuAttendanceDaily
    from app.models.role import Role


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, comment="登录用户名"
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="bcrypt 哈希")
    real_name: Mapped[Optional[str]] = mapped_column(String(50), comment="真实姓名")
    email: Mapped[Optional[str]] = mapped_column(String(100), comment="邮箱")
    phone: Mapped[Optional[str]] = mapped_column(String(30), comment="手机号")
    job_title: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="飞书通讯录职位/职务"
    )
    employee_no: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True, comment="工号（飞书 employee_no）"
    )
    feishu_open_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, comment="飞书 open_id"
    )
    feishu_user_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, comment="飞书 user_id（考勤 employee_id）"
    )
    hire_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="入职日期")
    employment_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="正式/试用/待入职/离职"
    )
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="直属负责人"
    )
    contract_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="合同类型")
    contract_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_status: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="生效中/已到期/未签署"
    )
    archive_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="完整/待补"
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, comment="所属部门"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="users")
    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=user_roles, back_populates="users"
    )
    manager: Mapped[Optional["User"]] = relationship(
        "User", remote_side="User.id", foreign_keys=[manager_id]
    )
    history_events: Mapped[List["EmployeeHistoryEvent"]] = relationship(
        "EmployeeHistoryEvent", back_populates="user", cascade="all, delete-orphan"
    )
    attendance_days: Mapped[List["FeishuAttendanceDaily"]] = relationship(
        "FeishuAttendanceDaily", back_populates="user", cascade="all, delete-orphan"
    )
