"""create approval flow engine (instances + tasks)

Revision ID: w1x2y3z4a5b6
Revises: v0w1x2y3z4a5
Create Date: 2026-08-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w1x2y3z4a5b6"
down_revision: Union[str, None] = "v0w1x2y3z4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "approval_instances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("rule_code", sa.String(length=64), nullable=True),
        sa.Column("biz_type", sa.String(length=50), nullable=False),
        sa.Column("biz_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="CNY"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("current_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("initiator_id", sa.Integer(), nullable=True),
        sa.Column("initiator_name", sa.String(length=50), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("cc_json", sa.Text(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("deep_link", sa.String(length=200), nullable=True),
        sa.Column("reject_reason", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["rule_id"], ["approval_rules.id"]),
        sa.ForeignKeyConstraint(["initiator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_approval_instances_code", "approval_instances", ["code"])
    op.create_index("ix_approval_instances_biz_type", "approval_instances", ["biz_type"])
    op.create_index("ix_approval_instances_biz_id", "approval_instances", ["biz_id"])
    op.create_index("ix_approval_instances_status", "approval_instances", ["status"])

    op.create_table(
        "approval_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("node_type", sa.String(length=20), nullable=False, server_default="approve"),
        sa.Column("group_label", sa.String(length=60), nullable=True),
        sa.Column("roles_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="waiting"),
        sa.Column("acted_by", sa.Integer(), nullable=True),
        sa.Column("acted_by_name", sa.String(length=50), nullable=True),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
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
        sa.ForeignKeyConstraint(["instance_id"], ["approval_instances.id"]),
        sa.ForeignKeyConstraint(["acted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_tasks_instance_id", "approval_tasks", ["instance_id"])
    op.create_index("ix_approval_tasks_seq", "approval_tasks", ["seq"])
    op.create_index("ix_approval_tasks_status", "approval_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_approval_tasks_status", table_name="approval_tasks")
    op.drop_index("ix_approval_tasks_seq", table_name="approval_tasks")
    op.drop_index("ix_approval_tasks_instance_id", table_name="approval_tasks")
    op.drop_table("approval_tasks")
    op.drop_index("ix_approval_instances_status", table_name="approval_instances")
    op.drop_index("ix_approval_instances_biz_id", table_name="approval_instances")
    op.drop_index("ix_approval_instances_biz_type", table_name="approval_instances")
    op.drop_index("ix_approval_instances_code", table_name="approval_instances")
    op.drop_table("approval_instances")
