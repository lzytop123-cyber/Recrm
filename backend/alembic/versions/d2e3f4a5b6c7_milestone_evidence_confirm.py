"""milestone evidence confirm fields

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_milestones",
        sa.Column("evidence_status", sa.String(length=30), server_default="none", nullable=False),
    )
    op.add_column(
        "project_milestones",
        sa.Column("evidence_confirmed_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "project_milestones",
        sa.Column("evidence_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project_milestones",
        sa.Column("evidence_reject_reason", sa.String(length=200), nullable=True),
    )
    op.create_foreign_key(
        "fk_project_milestones_evidence_confirmed_by",
        "project_milestones",
        "users",
        ["evidence_confirmed_by"],
        ["id"],
    )
    # 已有证据文本的视为待确认，便于存量数据走确认闭环
    op.execute(
        "UPDATE project_milestones SET evidence_status = 'pending' "
        "WHERE evidence IS NOT NULL AND TRIM(evidence) <> '' AND evidence_status = 'none'"
    )


def downgrade() -> None:
    op.drop_constraint("fk_project_milestones_evidence_confirmed_by", "project_milestones", type_="foreignkey")
    op.drop_column("project_milestones", "evidence_reject_reason")
    op.drop_column("project_milestones", "evidence_confirmed_at")
    op.drop_column("project_milestones", "evidence_confirmed_by")
    op.drop_column("project_milestones", "evidence_status")
