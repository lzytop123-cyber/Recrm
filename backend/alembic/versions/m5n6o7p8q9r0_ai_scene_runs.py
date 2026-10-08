"""S2-S5 scene runs (daily report draft, follow-up, ticket, precheck)

Revision ID: m5n6o7p8q9r0
Revises: k4d5e6f7a8b9
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m5n6o7p8q9r0"
down_revision: Union[str, None] = "k4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_scene_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scene", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_scene_runs_user_id", "ai_scene_runs", ["user_id"])
    op.create_index("ix_ai_scene_runs_scene", "ai_scene_runs", ["scene"])


def downgrade() -> None:
    op.drop_index("ix_ai_scene_runs_scene", table_name="ai_scene_runs")
    op.drop_index("ix_ai_scene_runs_user_id", table_name="ai_scene_runs")
    op.drop_table("ai_scene_runs")
