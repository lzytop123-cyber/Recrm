"""AP-25 delegation biz_types (可代理的流程范围)

Revision ID: z4a5b6c7d8e9
Revises: y3z4a5b6c7d8
Create Date: 2026-08-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z4a5b6c7d8e9"
down_revision: Union[str, None] = "y3z4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("delegations", sa.Column("biz_types_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("delegations", "biz_types_json")
