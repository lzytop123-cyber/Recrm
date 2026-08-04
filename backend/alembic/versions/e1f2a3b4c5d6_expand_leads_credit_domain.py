"""expand leads credit_code and company_domain

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("credit_code", sa.String(length=50), nullable=True))
    op.add_column("leads", sa.Column("company_domain", sa.String(length=100), nullable=True))
    op.create_index("ix_leads_credit_code", "leads", ["credit_code"])
    op.create_index("ix_leads_company_domain", "leads", ["company_domain"])


def downgrade() -> None:
    op.drop_index("ix_leads_company_domain", table_name="leads")
    op.drop_index("ix_leads_credit_code", table_name="leads")
    op.drop_column("leads", "company_domain")
    op.drop_column("leads", "credit_code")
