"""ticket assignee candidates for multi-select

Revision ID: n2d3e4f5a6b7
Revises: m1c2d3e4f5a6
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n2d3e4f5a6b7"
down_revision: Union[str, None] = "m1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_assignee_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", "user_id", name="uq_ticket_assignee_candidate"),
    )
    op.create_index(
        "ix_ticket_assignee_candidates_ticket_id",
        "ticket_assignee_candidates",
        ["ticket_id"],
    )
    op.create_index(
        "ix_ticket_assignee_candidates_user_id",
        "ticket_assignee_candidates",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_assignee_candidates_user_id", table_name="ticket_assignee_candidates")
    op.drop_index("ix_ticket_assignee_candidates_ticket_id", table_name="ticket_assignee_candidates")
    op.drop_table("ticket_assignee_candidates")
