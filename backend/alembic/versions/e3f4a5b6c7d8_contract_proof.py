"""add contract proof attachment fields

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("proof_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("proof_path", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contracts", "proof_path")
    op.drop_column("contracts", "proof_filename")
