"""create schedules

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("resource_type", sa.String(length=30), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schedules_resource_type", "schedules", ["resource_type"])
    op.create_index("ix_schedules_employee_id", "schedules", ["employee_id"])
    op.create_index("ix_schedules_project_id", "schedules", ["project_id"])
    op.create_index("ix_schedules_start_time", "schedules", ["start_time"])
    op.create_index("ix_schedules_end_time", "schedules", ["end_time"])
    op.create_index("ix_schedules_status", "schedules", ["status"])
    op.create_index("ix_schedules_creator_id", "schedules", ["creator_id"])


def downgrade() -> None:
    op.drop_index("ix_schedules_creator_id", table_name="schedules")
    op.drop_index("ix_schedules_status", table_name="schedules")
    op.drop_index("ix_schedules_end_time", table_name="schedules")
    op.drop_index("ix_schedules_start_time", table_name="schedules")
    op.drop_index("ix_schedules_project_id", table_name="schedules")
    op.drop_index("ix_schedules_employee_id", table_name="schedules")
    op.drop_index("ix_schedules_resource_type", table_name="schedules")
    op.drop_table("schedules")
