"""expand payments fields

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payments") as batch:
        batch.add_column(sa.Column("title", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("due_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("creator_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("confirmed_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_payments_creator_id", "users", ["creator_id"], ["id"])
        batch.create_foreign_key("fk_payments_department_id", "departments", ["department_id"], ["id"])
        batch.create_foreign_key("fk_payments_confirmed_by", "users", ["confirmed_by"], ["id"])
        batch.create_index("ix_payments_contract_id", ["contract_id"])
        batch.create_index("ix_payments_due_date", ["due_date"])
        batch.create_index("ix_payments_status", ["status"])
        batch.create_index("ix_payments_owner_id", ["owner_id"])


def downgrade() -> None:
    with op.batch_alter_table("payments") as batch:
        batch.drop_index("ix_payments_owner_id")
        batch.drop_index("ix_payments_status")
        batch.drop_index("ix_payments_due_date")
        batch.drop_index("ix_payments_contract_id")
        batch.drop_constraint("fk_payments_confirmed_by", type_="foreignkey")
        batch.drop_constraint("fk_payments_department_id", type_="foreignkey")
        batch.drop_constraint("fk_payments_creator_id", type_="foreignkey")
        for col in [
            "confirmed_at",
            "confirmed_by",
            "department_id",
            "creator_id",
            "due_date",
            "title",
        ]:
            batch.drop_column(col)
