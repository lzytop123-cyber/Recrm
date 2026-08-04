"""project acceptance approval and closeout fields

Revision ID: i7d8e9f0a1b2
Revises: h6c7d8e9f0a1
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i7d8e9f0a1b2"
down_revision: Union[str, None] = "h6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "acceptance_approval_status",
            sa.String(length=20),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column("projects", sa.Column("acceptance_submitted_by", sa.Integer(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("acceptance_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("projects", sa.Column("acceptance_approved_by", sa.Integer(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("acceptance_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("acceptance_reject_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("acceptance_attachment", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("acceptance_attachment_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column(
            "finance_check_passed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "leftover_closed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_projects_acceptance_approval_status",
        "projects",
        ["acceptance_approval_status"],
    )
    op.create_foreign_key(
        "fk_projects_acceptance_submitted_by",
        "projects",
        "users",
        ["acceptance_submitted_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_projects_acceptance_approved_by",
        "projects",
        "users",
        ["acceptance_approved_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_acceptance_approved_by", "projects", type_="foreignkey")
    op.drop_constraint("fk_projects_acceptance_submitted_by", "projects", type_="foreignkey")
    op.drop_index("ix_projects_acceptance_approval_status", table_name="projects")
    op.drop_column("projects", "leftover_closed")
    op.drop_column("projects", "finance_check_passed")
    op.drop_column("projects", "acceptance_attachment_path")
    op.drop_column("projects", "acceptance_attachment")
    op.drop_column("projects", "acceptance_reject_reason")
    op.drop_column("projects", "acceptance_approved_at")
    op.drop_column("projects", "acceptance_approved_by")
    op.drop_column("projects", "acceptance_submitted_at")
    op.drop_column("projects", "acceptance_submitted_by")
    op.drop_column("projects", "acceptance_approval_status")
