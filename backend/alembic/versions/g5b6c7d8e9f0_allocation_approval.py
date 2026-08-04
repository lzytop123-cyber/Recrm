"""receipt allocation pending approval fields

Revision ID: g5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g5b6c7d8e9f0"
down_revision: Union[str, None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "receipt_allocations",
        sa.Column("approved_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "receipt_allocations",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "receipt_allocations",
        sa.Column("review_remark", sa.String(length=500), nullable=True),
    )
    op.create_foreign_key(
        "fk_receipt_allocations_approved_by_users",
        "receipt_allocations",
        "users",
        ["approved_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_receipt_allocations_approved_by_users",
        "receipt_allocations",
        type_="foreignkey",
    )
    op.drop_column("receipt_allocations", "review_remark")
    op.drop_column("receipt_allocations", "approved_at")
    op.drop_column("receipt_allocations", "approved_by")
