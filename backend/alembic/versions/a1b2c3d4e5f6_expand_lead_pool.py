"""expand lead pool tables

Revision ID: a1b2c3d4e5f6
Revises: 395d4a1d713a
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "395d4a1d713a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 跟进记录表
    op.create_table(
        "lead_follow_ups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("follow_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("customer_feedback", sa.Text(), nullable=True),
        sa.Column("result", sa.String(length=30), nullable=False),
        sa.Column("next_follow_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_follow_ups_lead_id", "lead_follow_ups", ["lead_id"])

    # 线索日志表
    op.create_table(
        "lead_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_logs_lead_id", "lead_logs", ["lead_id"])

    # 扩展 leads 字段（SQLite batch）
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("email", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("region", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("source_detail", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("need_desc", sa.Text(), nullable=True))
        batch.add_column(sa.Column("budget", sa.Numeric(12, 2), nullable=True))
        batch.add_column(sa.Column("expected_deal_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("business_type", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("creator_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("protect_until", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_followed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("lost_reason", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("lost_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_leads_creator_id", "users", ["creator_id"], ["id"])
        batch.create_index("ix_leads_company_name", ["company_name"])
        batch.create_index("ix_leads_phone", ["phone"])
        batch.create_index("ix_leads_status", ["status"])
        batch.create_index("ix_leads_owner_id", ["owner_id"])

    # 旧状态值迁移：new -> pending_assign
    op.execute("UPDATE leads SET status='pending_assign' WHERE status='new'")
    op.execute("UPDATE leads SET status='following' WHERE status='following'")
    op.execute("UPDATE leads SET source='manual' WHERE source IS NULL OR source=''")


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.drop_index("ix_leads_owner_id")
        batch.drop_index("ix_leads_status")
        batch.drop_index("ix_leads_phone")
        batch.drop_index("ix_leads_company_name")
        batch.drop_constraint("fk_leads_creator_id", type_="foreignkey")
        for col in [
            "lost_at",
            "lost_reason",
            "converted_at",
            "last_followed_at",
            "assigned_at",
            "protect_until",
            "creator_id",
            "business_type",
            "expected_deal_at",
            "budget",
            "need_desc",
            "source_detail",
            "region",
            "email",
        ]:
            batch.drop_column(col)
    op.drop_index("ix_lead_logs_lead_id", table_name="lead_logs")
    op.drop_table("lead_logs")
    op.drop_index("ix_lead_follow_ups_lead_id", table_name="lead_follow_ups")
    op.drop_table("lead_follow_ups")
