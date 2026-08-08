"""payment defer initiation approval fields

Revision ID: p4q5r6s7t8u9
Revises: o3p4q5r6s7t8
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p4q5r6s7t8u9"
down_revision: Union[str, None] = "o3p4q5r6s7t8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "payment_defer_status",
            sa.String(length=20),
            nullable=False,
            server_default="none",
            comment="none/pending/approved/rejected",
        ),
    )
    op.add_column(
        "projects", sa.Column("payment_defer_submitted_by", sa.Integer(), nullable=True)
    )
    op.add_column(
        "projects",
        sa.Column("payment_defer_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "projects", sa.Column("payment_defer_approved_by", sa.Integer(), nullable=True)
    )
    op.add_column(
        "projects",
        sa.Column("payment_defer_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("payment_defer_reject_reason", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_projects_payment_defer_status",
        "projects",
        ["payment_defer_status"],
    )
    op.create_foreign_key(
        "fk_projects_payment_defer_submitted_by",
        "projects",
        "users",
        ["payment_defer_submitted_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_projects_payment_defer_approved_by",
        "projects",
        "users",
        ["payment_defer_approved_by"],
        ["id"],
    )
    # 已存在的无到款立项视为历史已通过，避免卡住进行中的项目
    op.execute(
        "UPDATE projects SET payment_defer_status = 'approved' "
        "WHERE payment_deferred IS TRUE"
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_payment_defer_approved_by", "projects", type_="foreignkey")
    op.drop_constraint("fk_projects_payment_defer_submitted_by", "projects", type_="foreignkey")
    op.drop_index("ix_projects_payment_defer_status", table_name="projects")
    op.drop_column("projects", "payment_defer_reject_reason")
    op.drop_column("projects", "payment_defer_approved_at")
    op.drop_column("projects", "payment_defer_approved_by")
    op.drop_column("projects", "payment_defer_submitted_at")
    op.drop_column("projects", "payment_defer_submitted_by")
    op.drop_column("projects", "payment_defer_status")
