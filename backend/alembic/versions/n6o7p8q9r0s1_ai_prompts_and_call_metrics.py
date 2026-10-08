"""ai prompts and call metrics

Revision ID: n6o7p8q9r0s1
Revises: m5n6o7p8q9r0
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n6o7p8q9r0s1"
down_revision: Union[str, None] = "m5n6o7p8q9r0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ai_scene_runs") as batch:
        batch.add_column(sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("elapsed_ms", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("cost", sa.Numeric(12, 6), nullable=False, server_default="0"))
    op.create_table(
        "ai_prompts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_prompts_code", "ai_prompts", ["code"])
    op.create_index("ix_ai_prompts_status", "ai_prompts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ai_prompts_status", table_name="ai_prompts")
    op.drop_index("ix_ai_prompts_code", table_name="ai_prompts")
    op.drop_table("ai_prompts")
    with op.batch_alter_table("ai_scene_runs") as batch:
        batch.drop_column("cost")
        batch.drop_column("elapsed_ms")
        batch.drop_column("tokens")
