"""project finance check approval fields

Revision ID: j8e9f0a1b2c3
Revises: i7d8e9f0a1b2
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j8e9f0a1b2c3"
down_revision: Union[str, None] = "i7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "finance_check_status",
            sa.String(length=20),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column("projects", sa.Column("finance_check_submitted_by", sa.Integer(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("finance_check_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("projects", sa.Column("finance_check_approved_by", sa.Integer(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("finance_check_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("finance_check_reject_reason", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_projects_finance_check_status",
        "projects",
        ["finance_check_status"],
    )
    op.create_foreign_key(
        "fk_projects_finance_check_submitted_by",
        "projects",
        "users",
        ["finance_check_submitted_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_projects_finance_check_approved_by",
        "projects",
        "users",
        ["finance_check_approved_by"],
        ["id"],
    )
    # 已通过财务核对的历史数据同步为 approved
    op.execute(
        "UPDATE projects SET finance_check_status = 'approved' "
        "WHERE finance_check_passed IS TRUE"
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_finance_check_approved_by", "projects", type_="foreignkey")
    op.drop_constraint("fk_projects_finance_check_submitted_by", "projects", type_="foreignkey")
    op.drop_index("ix_projects_finance_check_status", table_name="projects")
    op.drop_column("projects", "finance_check_reject_reason")
    op.drop_column("projects", "finance_check_approved_at")
    op.drop_column("projects", "finance_check_approved_by")
    op.drop_column("projects", "finance_check_submitted_at")
    op.drop_column("projects", "finance_check_submitted_by")
    op.drop_column("projects", "finance_check_status")
