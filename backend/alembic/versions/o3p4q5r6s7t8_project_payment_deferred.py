"""project payment deferred initiation exception

Revision ID: o3p4q5r6s7t8
Revises: n2d3e4f5a6b7
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o3p4q5r6s7t8"
down_revision: Union[str, None] = "n2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "payment_deferred",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="无到款立项（先干活后付款）",
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "payment_deferred_reason",
            sa.String(length=500),
            nullable=True,
            comment="无到款立项原因",
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "payment_deferred_reason")
    op.drop_column("projects", "payment_deferred")
