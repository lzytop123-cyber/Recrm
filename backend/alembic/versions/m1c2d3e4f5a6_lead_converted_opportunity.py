"""add leads.converted_opportunity_id and merge heads

Revision ID: m1c2d3e4f5a6
Revises: k9a0b1c2d3e4, l0b1c2d3e4f5
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m1c2d3e4f5a6"
down_revision: Union[str, tuple[str, ...], None] = ("k9a0b1c2d3e4", "l0b1c2d3e4f5")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("converted_opportunity_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_leads_converted_opportunity_id",
        "leads",
        "opportunities",
        ["converted_opportunity_id"],
        ["id"],
    )
    op.create_index(
        "ix_leads_converted_opportunity_id",
        "leads",
        ["converted_opportunity_id"],
    )
    # 回填：已有转化线索按 opportunities.source_lead_id 对齐
    op.execute(
        """
        UPDATE leads
        SET converted_opportunity_id = (
            SELECT opportunities.id
            FROM opportunities
            WHERE opportunities.source_lead_id = leads.id
            ORDER BY opportunities.id
            LIMIT 1
        )
        WHERE converted_customer_id IS NOT NULL
          AND converted_opportunity_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_leads_converted_opportunity_id", table_name="leads")
    op.drop_constraint("fk_leads_converted_opportunity_id", "leads", type_="foreignkey")
    op.drop_column("leads", "converted_opportunity_id")
