"""knowledge editor: visibility/expires/source_note/reject_reason

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
Create Date: 2026-09-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "s1t2u3v4w5x6"
down_revision: Union[str, None] = "r0s1t2u3v4w5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = (
    ("source_note", sa.Column("source_note", sa.String(length=300), nullable=True)),
    ("visibility", sa.Column("visibility", sa.String(length=20), nullable=False, server_default="inherit")),
    ("visibility_department", sa.Column("visibility_department", sa.String(length=80), nullable=True)),
    ("expires_at", sa.Column("expires_at", sa.Date(), nullable=True)),
    ("reject_reason", sa.Column("reject_reason", sa.String(length=500), nullable=True)),
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in inspect(bind).get_columns("knowledge_articles")}
    with op.batch_alter_table("knowledge_articles") as batch:
        for name, col in _COLS:
            if name not in existing:
                batch.add_column(col)


def downgrade() -> None:
    with op.batch_alter_table("knowledge_articles") as batch:
        for name, _ in reversed(_COLS):
            batch.drop_column(name)
