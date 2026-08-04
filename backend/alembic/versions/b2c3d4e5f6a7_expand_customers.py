"""expand customers and follow-ups

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("customers") as batch:
        batch.add_column(sa.Column("short_name", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("company_size", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("address", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("source", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("creator_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("source_lead_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("last_followed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_customers_creator_id", "users", ["creator_id"], ["id"])
        batch.create_foreign_key("fk_customers_source_lead_id", "leads", ["source_lead_id"], ["id"])
        batch.create_index("ix_customers_name", ["name"])
        batch.create_index("ix_customers_phone", ["phone"])
        batch.create_index("ix_customers_status", ["status"])
        batch.create_index("ix_customers_owner_id", ["owner_id"])

    op.create_table(
        "customer_follow_ups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("follow_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("next_follow_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_follow_ups_customer_id", "customer_follow_ups", ["customer_id"])

    # 旧状态 inactive -> paused
    op.execute("UPDATE customers SET status='paused' WHERE status='inactive'")


def downgrade() -> None:
    op.drop_index("ix_customer_follow_ups_customer_id", table_name="customer_follow_ups")
    op.drop_table("customer_follow_ups")
    with op.batch_alter_table("customers") as batch:
        batch.drop_index("ix_customers_owner_id")
        batch.drop_index("ix_customers_status")
        batch.drop_index("ix_customers_phone")
        batch.drop_index("ix_customers_name")
        batch.drop_constraint("fk_customers_source_lead_id", type_="foreignkey")
        batch.drop_constraint("fk_customers_creator_id", type_="foreignkey")
        for col in [
            "last_followed_at",
            "source_lead_id",
            "creator_id",
            "source",
            "address",
            "company_size",
            "short_name",
        ]:
            batch.drop_column(col)
