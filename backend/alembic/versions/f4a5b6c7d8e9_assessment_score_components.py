"""add okr/kpi/behavior score columns on assessments

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("performance_assessments", sa.Column("okr_score", sa.Integer(), nullable=True))
    op.add_column("performance_assessments", sa.Column("kpi_score", sa.Integer(), nullable=True))
    op.add_column("performance_assessments", sa.Column("behavior_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("performance_assessments", "behavior_score")
    op.drop_column("performance_assessments", "kpi_score")
    op.drop_column("performance_assessments", "okr_score")
