"""create opportunities + contracts.opportunity_id

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_no", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("source_lead_id", sa.Integer(), nullable=True),
        sa.Column("business_type", sa.String(length=30), nullable=False),
        sa.Column("stage", sa.String(length=30), nullable=False),
        sa.Column("expected_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("requirement_summary", sa.Text(), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_action_note", sa.String(length=500), nullable=True),
        sa.Column("lost_reason", sa.String(length=500), nullable=True),
        sa.Column("won_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["source_lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_opportunities_opportunity_no", "opportunities", ["opportunity_no"], unique=True)
    op.create_index("ix_opportunities_customer_id", "opportunities", ["customer_id"])
    op.create_index("ix_opportunities_stage", "opportunities", ["stage"])
    op.create_index("ix_opportunities_owner_id", "opportunities", ["owner_id"])

    op.create_table(
        "opportunity_activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("activity_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("from_stage", sa.String(length=30), nullable=True),
        sa.Column("to_stage", sa.String(length=30), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_opportunity_activities_opportunity_id",
        "opportunity_activities",
        ["opportunity_id"],
    )

    op.add_column(
        "contracts",
        sa.Column("opportunity_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_contracts_opportunity_id", "contracts", ["opportunity_id"])
    op.create_foreign_key(
        "fk_contracts_opportunity_id",
        "contracts",
        "opportunities",
        ["opportunity_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_contracts_opportunity_id", "contracts", type_="foreignkey")
    op.drop_index("ix_contracts_opportunity_id", table_name="contracts")
    op.drop_column("contracts", "opportunity_id")

    op.drop_index("ix_opportunity_activities_opportunity_id", table_name="opportunity_activities")
    op.drop_table("opportunity_activities")

    op.drop_index("ix_opportunities_owner_id", table_name="opportunities")
    op.drop_index("ix_opportunities_stage", table_name="opportunities")
    op.drop_index("ix_opportunities_customer_id", table_name="opportunities")
    op.drop_index("ix_opportunities_opportunity_no", table_name="opportunities")
    op.drop_table("opportunities")
