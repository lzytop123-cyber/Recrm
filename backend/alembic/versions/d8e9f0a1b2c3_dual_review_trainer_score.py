"""入职考核全表双评：指标项增加培训部分列

主管与培训部对每条指标各打一次分，各自算总分判通过（都通过=通过；
一方通过=待总经理裁决）。新增 trainer_score / trainer_comment。

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-10-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "performance_assessment_items",
        sa.Column("trainer_score", sa.Numeric(6, 2), nullable=True),
    )
    op.add_column(
        "performance_assessment_items",
        sa.Column("trainer_comment", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("performance_assessment_items", "trainer_comment")
    op.drop_column("performance_assessment_items", "trainer_score")
