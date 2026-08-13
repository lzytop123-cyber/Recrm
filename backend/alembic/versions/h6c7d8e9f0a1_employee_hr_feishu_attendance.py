"""employee hr fields + history + feishu attendance + sync state

Revision ID: h6c7d8e9f0a1
Revises: g5b6c7d8e9f0
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h6c7d8e9f0a1"
down_revision: Union[str, None] = "g5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("employee_no", sa.String(length=50), nullable=True, comment="工号（飞书 employee_no）"))
    op.add_column("users", sa.Column("feishu_user_id", sa.String(length=100), nullable=True, comment="飞书 user_id（考勤 employee_id）"))
    op.add_column("users", sa.Column("hire_date", sa.Date(), nullable=True, comment="入职日期"))
    op.add_column("users", sa.Column("employment_status", sa.String(length=20), nullable=True, comment="正式/试用/待入职/离职"))
    op.add_column("users", sa.Column("manager_id", sa.Integer(), nullable=True, comment="直属负责人"))
    op.add_column("users", sa.Column("contract_type", sa.String(length=50), nullable=True, comment="合同类型"))
    op.add_column("users", sa.Column("contract_start", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("contract_end", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("contract_status", sa.String(length=30), nullable=True, comment="生效中/已到期/未签署"))
    op.add_column("users", sa.Column("archive_status", sa.String(length=20), nullable=True, comment="完整/待补"))
    op.create_index("ix_users_employee_no", "users", ["employee_no"])
    # SQLite 不支持 ALTER TABLE ADD CONSTRAINT，需 batch 模式重建表
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("uq_users_feishu_user_id", ["feishu_user_id"])
        batch_op.create_foreign_key("fk_users_manager_id_users", "users", ["manager_id"], ["id"])

    op.create_table(
        "employee_history_events",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False, comment="hire/transfer/resign/regularize/other"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_employee_history_events_user_id", "employee_history_events", ["user_id"])

    op.create_table(
        "feishu_attendance_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, comment="正常/迟到/早退/缺卡/请假/外出/休息日/异常"),
        sa.Column("first_punch", sa.Time(), nullable=True),
        sa.Column("last_punch", sa.Time(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="飞书同步", comment="飞书同步/日历规则"),
        sa.Column("raw_result", sa.String(length=100), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "work_date", name="uq_feishu_attendance_user_date"),
    )
    op.create_index("ix_feishu_attendance_daily_user_id", "feishu_attendance_daily", ["user_id"])
    op.create_index("ix_feishu_attendance_daily_work_date", "feishu_attendance_daily", ["work_date"])

    op.create_table(
        "system_sync_states",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unknown", comment="ok/error/pending/unknown"),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_system_sync_states_key", "system_sync_states", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_system_sync_states_key", table_name="system_sync_states")
    op.drop_table("system_sync_states")
    op.drop_index("ix_feishu_attendance_daily_work_date", table_name="feishu_attendance_daily")
    op.drop_index("ix_feishu_attendance_daily_user_id", table_name="feishu_attendance_daily")
    op.drop_table("feishu_attendance_daily")
    op.drop_index("ix_employee_history_events_user_id", table_name="employee_history_events")
    op.drop_table("employee_history_events")
    op.drop_constraint("fk_users_manager_id_users", "users", type_="foreignkey")
    op.drop_constraint("uq_users_feishu_user_id", "users", type_="unique")
    op.drop_index("ix_users_employee_no", table_name="users")
    op.drop_column("users", "archive_status")
    op.drop_column("users", "contract_status")
    op.drop_column("users", "contract_end")
    op.drop_column("users", "contract_start")
    op.drop_column("users", "contract_type")
    op.drop_column("users", "manager_id")
    op.drop_column("users", "employment_status")
    op.drop_column("users", "hire_date")
    op.drop_column("users", "feishu_user_id")
    op.drop_column("users", "employee_no")
