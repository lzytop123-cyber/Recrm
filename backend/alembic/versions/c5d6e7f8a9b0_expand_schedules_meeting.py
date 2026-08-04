"""expand schedules for meeting workbench

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "schedules",
        sa.Column("schedule_type", sa.String(length=30), server_default="other", nullable=False),
    )
    op.add_column("schedules", sa.Column("project_task_id", sa.Integer(), nullable=True))
    op.add_column("schedules", sa.Column("ticket_id", sa.Integer(), nullable=True))
    op.add_column("schedules", sa.Column("coordination_note", sa.Text(), nullable=True))
    op.add_column("schedules", sa.Column("result", sa.Text(), nullable=True))
    op.add_column("schedules", sa.Column("actual_hours", sa.Numeric(5, 2), nullable=True))
    op.add_column("schedules", sa.Column("timesheet_id", sa.Integer(), nullable=True))
    op.add_column(
        "schedules",
        sa.Column("feishu_sync_status", sa.String(length=20), server_default="none", nullable=False),
    )
    op.create_index("ix_schedules_schedule_type", "schedules", ["schedule_type"])
    op.create_index("ix_schedules_project_task_id", "schedules", ["project_task_id"])
    op.create_index("ix_schedules_ticket_id", "schedules", ["ticket_id"])
    op.create_foreign_key(
        "fk_schedules_project_task_id",
        "schedules",
        "project_tasks",
        ["project_task_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_schedules_ticket_id",
        "schedules",
        "tickets",
        ["ticket_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_schedules_timesheet_id",
        "schedules",
        "timesheets",
        ["timesheet_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_schedules_timesheet_id", "schedules", type_="foreignkey")
    op.drop_constraint("fk_schedules_ticket_id", "schedules", type_="foreignkey")
    op.drop_constraint("fk_schedules_project_task_id", "schedules", type_="foreignkey")
    op.drop_index("ix_schedules_ticket_id", table_name="schedules")
    op.drop_index("ix_schedules_project_task_id", table_name="schedules")
    op.drop_index("ix_schedules_schedule_type", table_name="schedules")
    op.drop_column("schedules", "feishu_sync_status")
    op.drop_column("schedules", "timesheet_id")
    op.drop_column("schedules", "actual_hours")
    op.drop_column("schedules", "result")
    op.drop_column("schedules", "coordination_note")
    op.drop_column("schedules", "ticket_id")
    op.drop_column("schedules", "project_task_id")
    op.drop_column("schedules", "schedule_type")
