"""create approval_rules

Revision ID: k9a0b1c2d3e4
Revises: j8e9f0a1b2c3
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k9a0b1c2d3e4"
down_revision: Union[str, None] = "j8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "approval_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("biz_type", sa.String(length=50), nullable=False),
        sa.Column("nodes_json", sa.Text(), nullable=False),
        sa.Column("conditions_json", sa.Text(), nullable=True),
        sa.Column("timeout_hours", sa.Integer(), nullable=False, server_default="72"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
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
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_approval_rules_code", "approval_rules", ["code"])
    op.create_index("ix_approval_rules_biz_type", "approval_rules", ["biz_type"])
    op.create_index("ix_approval_rules_status", "approval_rules", ["status"])


def downgrade() -> None:
    op.drop_index("ix_approval_rules_status", table_name="approval_rules")
    op.drop_index("ix_approval_rules_biz_type", table_name="approval_rules")
    op.drop_index("ix_approval_rules_code", table_name="approval_rules")
    op.drop_table("approval_rules")
