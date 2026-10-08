"""knowledge article attachment_text

Revision ID: k4d5e6f7a8b9
Revises: j3c4d5e6f7a8
Create Date: 2026-09-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k4d5e6f7a8b9"
down_revision: Union[str, None] = "j3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_articles") as batch:
        batch.add_column(sa.Column("attachment_text", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("knowledge_articles") as batch:
        batch.drop_column("attachment_text")
