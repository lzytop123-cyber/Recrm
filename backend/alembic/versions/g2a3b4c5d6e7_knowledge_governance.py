"""knowledge governance tables (versions, jobs, asks, feedback, gaps)

Revision ID: g2a3b4c5d6e7
Revises: f1b2c3d4e5f6
Create Date: 2026-09-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g2a3b4c5d6e7"
down_revision: Union[str, None] = "f1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_article_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("change_reason", sa.String(length=300), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["knowledge_articles.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_article_versions_article_id", "knowledge_article_versions", ["article_id"])

    op.create_table(
        "knowledge_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("job_type", sa.String(length=30), nullable=False, server_default="sync"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("error", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_jobs_source_id", "knowledge_jobs", ["source_id"])
    op.create_index("ix_knowledge_jobs_status", "knowledge_jobs", ["status"])

    op.create_table(
        "knowledge_asks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.String(length=500), nullable=False),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_asks_user_id", "knowledge_asks", ["user_id"])

    op.create_table(
        "knowledge_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ask_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("resolution", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ask_id"], ["knowledge_asks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_feedback_ask_id", "knowledge_feedback", ["ask_id"])
    op.create_index("ix_knowledge_feedback_status", "knowledge_feedback", ["status"])

    op.create_table(
        "knowledge_gaps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("keyword", sa.String(length=200), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_asked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keyword"),
    )
    op.create_index("ix_knowledge_gaps_keyword", "knowledge_gaps", ["keyword"], unique=True)


def downgrade() -> None:
    op.drop_table("knowledge_gaps")
    op.drop_table("knowledge_feedback")
    op.drop_table("knowledge_asks")
    op.drop_table("knowledge_jobs")
    op.drop_table("knowledge_article_versions")
