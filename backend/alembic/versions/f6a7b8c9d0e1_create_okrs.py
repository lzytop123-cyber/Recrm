"""create okrs and key_results

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "okrs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("period_label", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["okrs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_okrs_level", "okrs", ["level"])
    op.create_index("ix_okrs_period_label", "okrs", ["period_label"])
    op.create_index("ix_okrs_status", "okrs", ["status"])
    op.create_index("ix_okrs_owner_id", "okrs", ["owner_id"])
    op.create_index("ix_okrs_department_id", "okrs", ["department_id"])

    op.create_table(
        "key_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("okr_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("target_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("current_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["okr_id"], ["okrs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_key_results_okr_id", "key_results", ["okr_id"])


def downgrade() -> None:
    op.drop_index("ix_key_results_okr_id", table_name="key_results")
    op.drop_table("key_results")
    op.drop_index("ix_okrs_department_id", table_name="okrs")
    op.drop_index("ix_okrs_owner_id", table_name="okrs")
    op.drop_index("ix_okrs_status", table_name="okrs")
    op.drop_index("ix_okrs_period_label", table_name="okrs")
    op.drop_index("ix_okrs_level", table_name="okrs")
    op.drop_table("okrs")
