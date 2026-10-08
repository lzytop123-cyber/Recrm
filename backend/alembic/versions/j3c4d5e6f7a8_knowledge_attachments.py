"""knowledge article attachments json

Revision ID: j3c4d5e6f7a8
Revises: i2b3c4d5e6f7
Create Date: 2026-09-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j3c4d5e6f7a8"
down_revision: Union[str, None] = "i2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_articles") as batch:
        batch.add_column(sa.Column("attachments_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("knowledge_articles") as batch:
        batch.drop_column("attachments_json")
