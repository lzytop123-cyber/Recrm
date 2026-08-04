"""expand tickets phase2: task link, satisfaction, sla escalate, reopen

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("task_id", sa.Integer(), nullable=True))
    op.add_column("tickets", sa.Column("satisfaction", sa.Integer(), nullable=True))
    op.add_column("tickets", sa.Column("satisfaction_comment", sa.Text(), nullable=True))
    op.add_column(
        "tickets",
        sa.Column("sla_remind_level", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "tickets",
        sa.Column("escalated_level", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "tickets",
        sa.Column("sla_paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tickets_task_id", "tickets", ["task_id"])
    op.create_foreign_key(
        "fk_tickets_task_id_project_tasks",
        "tickets",
        "project_tasks",
        ["task_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_tickets_task_id_project_tasks", "tickets", type_="foreignkey")
    op.drop_index("ix_tickets_task_id", table_name="tickets")
    op.drop_column("tickets", "sla_paused_at")
    op.drop_column("tickets", "escalated_level")
    op.drop_column("tickets", "sla_remind_level")
    op.drop_column("tickets", "satisfaction_comment")
    op.drop_column("tickets", "satisfaction")
    op.drop_column("tickets", "task_id")
