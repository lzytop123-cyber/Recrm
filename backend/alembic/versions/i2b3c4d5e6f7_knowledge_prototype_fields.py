"""knowledge prototype: draft/origin/doc_type/source_url, longer source refs

Revision ID: i2b3c4d5e6f7
Revises: h1a2b3c4d5e6
Create Date: 2026-09-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i2b3c4d5e6f7"
down_revision: Union[str, None] = "h1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_articles") as batch:
        batch.add_column(sa.Column("doc_type", sa.String(length=20), nullable=False, server_default="qa"))
        batch.add_column(sa.Column("origin", sa.String(length=30), nullable=False, server_default="manual"))
        batch.add_column(sa.Column("source_url", sa.String(length=300), nullable=True))
        batch.create_index("ix_knowledge_articles_origin", ["origin"])
    with op.batch_alter_table("knowledge_sources") as batch:
        batch.alter_column(
            "external_ref",
            existing_type=sa.String(length=120),
            type_=sa.String(length=300),
            existing_nullable=True,
        )
    op.execute(
        sa.text(
            "UPDATE knowledge_articles SET origin = 'feishu_doc' "
            "WHERE source_id IS NOT NULL AND COALESCE(source_label, '') LIKE '%飞书%'"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("knowledge_articles") as batch:
        batch.drop_index("ix_knowledge_articles_origin")
        batch.drop_column("source_url")
        batch.drop_column("origin")
        batch.drop_column("doc_type")
    with op.batch_alter_table("knowledge_sources") as batch:
        batch.alter_column(
            "external_ref",
            existing_type=sa.String(length=300),
            type_=sa.String(length=120),
            existing_nullable=True,
        )
