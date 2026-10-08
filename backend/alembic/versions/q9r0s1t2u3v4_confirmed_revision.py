"""confirmed_revision on assessments

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q9r0s1t2u3v4"
down_revision: Union[str, None] = "p8q9r0s1t2u3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("performance_assessments") as batch:
        batch.add_column(sa.Column("confirmed_revision", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("performance_assessments") as batch:
        batch.drop_column("confirmed_revision")
