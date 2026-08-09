"""milestone evidence link and attachment

Revision ID: q5r6s7t8u9v0
Revises: p4q5r6s7t8u9
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q5r6s7t8u9v0"
down_revision: Union[str, None] = "p4q5r6s7t8u9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "project_milestones",
        "evidence",
        existing_type=sa.String(length=200),
        type_=sa.Text(),
        existing_nullable=True,
        comment="完成证据说明",
    )
    op.add_column(
        "project_milestones",
        sa.Column("evidence_link", sa.String(length=500), nullable=True, comment="完成证据链接"),
    )
    op.add_column(
        "project_milestones",
        sa.Column(
            "evidence_attachment",
            sa.String(length=255),
            nullable=True,
            comment="完成证据附件文件名",
        ),
    )
    op.add_column(
        "project_milestones",
        sa.Column(
            "evidence_attachment_path",
            sa.String(length=500),
            nullable=True,
            comment="完成证据附件存储路径",
        ),
    )


def downgrade() -> None:
    op.drop_column("project_milestones", "evidence_attachment_path")
    op.drop_column("project_milestones", "evidence_attachment")
    op.drop_column("project_milestones", "evidence_link")
    op.alter_column(
        "project_milestones",
        "evidence",
        existing_type=sa.Text(),
        type_=sa.String(length=200),
        existing_nullable=True,
        comment="完成证据",
    )
