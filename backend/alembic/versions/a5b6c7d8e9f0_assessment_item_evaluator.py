"""KPI 双评分：考核指标增加评分人标注（主管 / 培训部）

Revision ID: a5b6c7d8e9f0
Revises: s1t2u3v4w5x6
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, None] = "s1t2u3v4w5x6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 空值视为 'manager'（与历史行为一致：主管评分）
    op.add_column(
        "performance_template_items",
        sa.Column("evaluator", sa.String(length=20), nullable=True, comment="评分人：manager=直属主管 training=培训部"),
    )
    op.add_column(
        "performance_assessment_items",
        sa.Column("evaluator", sa.String(length=20), nullable=True, comment="评分人：manager=直属主管 training=培训部"),
    )


def downgrade() -> None:
    op.drop_column("performance_assessment_items", "evaluator")
    op.drop_column("performance_template_items", "evaluator")
