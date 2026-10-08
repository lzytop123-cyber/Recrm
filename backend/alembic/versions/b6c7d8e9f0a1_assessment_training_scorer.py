"""KPI 双评分：记录培训部评分人（用于禁止自审）

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "performance_assessments",
        sa.Column("training_scorer_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("performance_assessments", "training_scorer_id")
