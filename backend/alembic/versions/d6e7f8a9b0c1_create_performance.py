"""create performance cycle assessment appeal tables

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "performance_cycles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("period_label", sa.String(length=30), nullable=False),
        sa.Column("rule_version", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("calibration_started", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("locked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payroll_batch_no", sa.String(length=50), nullable=True),
        sa.Column("payroll_created", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("payroll_reviewed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("payroll_published", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_label"),
    )
    op.create_index("ix_performance_cycles_period_label", "performance_cycles", ["period_label"])
    op.create_index("ix_performance_cycles_status", "performance_cycles", ["status"])

    op.create_table(
        "performance_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("self_score", sa.Integer(), nullable=True),
        sa.Column("manager_score", sa.Integer(), nullable=True),
        sa.Column("final_score", sa.Integer(), nullable=True),
        sa.Column("grade", sa.String(length=10), nullable=True),
        sa.Column("coefficient", sa.Numeric(4, 2), nullable=True),
        sa.Column("evidence_status", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("manager_comment", sa.Text(), nullable=True),
        sa.Column("bonus_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["performance_cycles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_performance_assessments_cycle_id", "performance_assessments", ["cycle_id"])
    op.create_index("ix_performance_assessments_user_id", "performance_assessments", ["user_id"])
    op.create_index("ix_performance_assessments_status", "performance_assessments", ["status"])

    op.create_table(
        "performance_appeals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_score", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["performance_assessments.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_performance_appeals_assessment_id", "performance_appeals", ["assessment_id"])
    op.create_index("ix_performance_appeals_status", "performance_appeals", ["status"])


def downgrade() -> None:
    op.drop_table("performance_appeals")
    op.drop_table("performance_assessments")
    op.drop_table("performance_cycles")
