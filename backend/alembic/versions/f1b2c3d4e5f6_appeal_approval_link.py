"""link performance appeals to approval instances

Revision ID: f1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1b2c3d4e5f6"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("performance_appeals") as batch:
        batch.add_column(sa.Column("approval_instance_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_performance_appeals_approval_instance_id",
            "approval_instances",
            ["approval_instance_id"],
            ["id"],
        )
        batch.create_index("ix_performance_appeals_approval_instance_id", ["approval_instance_id"])


def downgrade() -> None:
    with op.batch_alter_table("performance_appeals") as batch:
        batch.drop_index("ix_performance_appeals_approval_instance_id")
        batch.drop_constraint("fk_performance_appeals_approval_instance_id", type_="foreignkey")
        batch.drop_column("approval_instance_id")
