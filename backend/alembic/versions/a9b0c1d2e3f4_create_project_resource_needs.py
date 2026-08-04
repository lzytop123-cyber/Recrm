"""create project resource needs

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-07-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_resource_needs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("role_name", sa.String(length=80), nullable=False),
        sa.Column("department_name", sa.String(length=80), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("suggested_user_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_user_id", sa.Integer(), nullable=True),
        sa.Column("planned_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("schedule_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["suggested_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_resource_needs_project_id", "project_resource_needs", ["project_id"])
    op.create_index("ix_project_resource_needs_suggested_user_id", "project_resource_needs", ["suggested_user_id"])
    op.create_index("ix_project_resource_needs_status", "project_resource_needs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_project_resource_needs_status", table_name="project_resource_needs")
    op.drop_index("ix_project_resource_needs_suggested_user_id", table_name="project_resource_needs")
    op.drop_index("ix_project_resource_needs_project_id", table_name="project_resource_needs")
    op.drop_table("project_resource_needs")
