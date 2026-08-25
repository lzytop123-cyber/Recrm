"""contract revision and modification snapshot

Revision ID: y3z4a5b6c7d8
Revises: x2y3z4a5b6c7
Create Date: 2026-08-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y3z4a5b6c7d8"
down_revision: Union[str, None] = "x2y3z4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1", comment="内容版本号"),
    )
    op.add_column(
        "contracts",
        sa.Column(
            "modification_snapshot_json",
            sa.Text(),
            nullable=True,
            comment="待审批的合同修改快照 JSON",
        ),
    )


def downgrade() -> None:
    op.drop_column("contracts", "modification_snapshot_json")
    op.drop_column("contracts", "revision")
