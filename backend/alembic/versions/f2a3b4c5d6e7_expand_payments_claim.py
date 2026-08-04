"""expand payments for claim flow

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("payment_no", sa.String(length=50), nullable=True))
    op.add_column(
        "payments",
        sa.Column("record_type", sa.String(length=20), nullable=False, server_default="plan"),
    )
    op.add_column("payments", sa.Column("payer_name", sa.String(length=200), nullable=True))
    op.add_column("payments", sa.Column("account_tail", sa.String(length=10), nullable=True))
    op.add_column("payments", sa.Column("proof_filename", sa.String(length=255), nullable=True))
    op.create_index("ix_payments_payment_no", "payments", ["payment_no"], unique=False)
    op.create_index("ix_payments_record_type", "payments", ["record_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payments_record_type", table_name="payments")
    op.drop_index("ix_payments_payment_no", table_name="payments")
    op.drop_column("payments", "proof_filename")
    op.drop_column("payments", "account_tail")
    op.drop_column("payments", "payer_name")
    op.drop_column("payments", "record_type")
    op.drop_column("payments", "payment_no")
