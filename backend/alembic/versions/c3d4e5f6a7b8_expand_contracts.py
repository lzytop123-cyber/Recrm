"""expand contracts fields

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("contracts") as batch:
        batch.add_column(sa.Column("contract_type", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("currency", sa.String(length=10), nullable=True))
        batch.add_column(sa.Column("payment_method", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("effective_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("expire_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("creator_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("approved_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("terminate_reason", sa.String(length=500), nullable=True))
        batch.create_foreign_key("fk_contracts_creator_id", "users", ["creator_id"], ["id"])
        batch.create_foreign_key("fk_contracts_approved_by", "users", ["approved_by"], ["id"])
        batch.create_index("ix_contracts_contract_no", ["contract_no"])
        batch.create_index("ix_contracts_customer_id", ["customer_id"])
        batch.create_index("ix_contracts_status", ["status"])
        batch.create_index("ix_contracts_owner_id", ["owner_id"])

    op.execute("UPDATE contracts SET contract_type='other' WHERE contract_type IS NULL")
    op.execute("UPDATE contracts SET currency='CNY' WHERE currency IS NULL OR currency=''")
    # 旧 active 保留为执行中；无变更


def downgrade() -> None:
    with op.batch_alter_table("contracts") as batch:
        batch.drop_index("ix_contracts_owner_id")
        batch.drop_index("ix_contracts_status")
        batch.drop_index("ix_contracts_customer_id")
        batch.drop_index("ix_contracts_contract_no")
        batch.drop_constraint("fk_contracts_approved_by", type_="foreignkey")
        batch.drop_constraint("fk_contracts_creator_id", type_="foreignkey")
        for col in [
            "terminate_reason",
            "approved_at",
            "approved_by",
            "creator_id",
            "expire_date",
            "effective_date",
            "payment_method",
            "currency",
            "contract_type",
        ]:
            batch.drop_column(col)
