"""add assignee_id to approval_tasks (指定人节点)

Revision ID: x2y3z4a5b6c7
Revises: w1x2y3z4a5b6
Create Date: 2026-08-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x2y3z4a5b6c7"
down_revision: Union[str, None] = "w1x2y3z4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("approval_tasks", sa.Column("assignee_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("approval_tasks", "assignee_id")
