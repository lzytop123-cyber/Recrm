"""kpi v2 columns and fact tables

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p8q9r0s1t2u3"
down_revision: Union[str, None] = "o7p8q9r0s1t2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("performance_cycles") as batch:
        batch.add_column(sa.Column("scope_json", sa.Text(), nullable=True))
    with op.batch_alter_table("performance_templates") as batch:
        batch.add_column(sa.Column("family_code", sa.String(40), nullable=True))
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("supersedes_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("engine_version", sa.String(20), nullable=False, server_default="legacy"))
        batch.add_column(sa.Column("assessment_kind", sa.String(30), nullable=False, server_default="monthly"))
        batch.add_column(sa.Column("scoring_mode", sa.String(30), nullable=False, server_default="legacy_weighted"))
        batch.add_column(sa.Column("nominal_total", sa.Numeric(8, 2), nullable=True))
        batch.add_column(sa.Column("definition_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("blocking_issues_json", sa.Text(), nullable=True))
    with op.batch_alter_table("performance_template_items") as batch:
        batch.add_column(sa.Column("metric_key", sa.String(80), nullable=True))
        batch.add_column(sa.Column("max_points", sa.Numeric(8, 2), nullable=True))
        batch.add_column(sa.Column("rule_config_json", sa.Text(), nullable=True))
    with op.batch_alter_table("performance_assessments") as batch:
        batch.add_column(sa.Column("assessment_kind", sa.String(30), nullable=False, server_default="monthly"))
        batch.add_column(sa.Column("instance_key", sa.String(80), nullable=False, server_default="monthly_primary"))
        batch.add_column(sa.Column("engine_version", sa.String(20), nullable=False, server_default="legacy"))
        batch.add_column(sa.Column("base_points", sa.Numeric(8, 2), nullable=True))
        batch.add_column(sa.Column("adjustment_points", sa.Numeric(8, 2), nullable=True))
        batch.add_column(sa.Column("total_points", sa.Numeric(8, 2), nullable=True))
        batch.add_column(sa.Column("grade_label", sa.String(20), nullable=True))
        batch.add_column(sa.Column("performance_base_snapshot", sa.Numeric(12, 2), nullable=True))
        batch.add_column(sa.Column("payroll_eligible", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("template_snapshot_json", sa.Text(), nullable=True))
    with op.batch_alter_table("performance_assessment_items") as batch:
        batch.add_column(sa.Column("metric_key", sa.String(80), nullable=True))
        batch.add_column(sa.Column("max_points", sa.Numeric(8, 2), nullable=True))
        batch.add_column(sa.Column("awarded_points", sa.Numeric(8, 2), nullable=True))
        batch.add_column(sa.Column("data_state", sa.String(20), nullable=True))
        batch.add_column(sa.Column("calculation_trace_json", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_assessment_instance", "performance_assessments", ["cycle_id", "user_id", "instance_key"]
    )
    op.create_table(
        "performance_template_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("performance_templates.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("job_title", sa.String(80), nullable=True),
        sa.Column("assessment_kind", sa.String(30), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
    )
    op.create_table(
        "performance_metric_facts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("metric_key", sa.String(80), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("occurred_on", sa.String(20), nullable=True),
        sa.Column("value", sa.Numeric(14, 4), nullable=True),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("source_record_id", sa.String(80), nullable=False),
        sa.Column("project_ref", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint("metric_key", "owner_id", "source_record_id", name="uq_metric_fact_source"),
    )
    op.create_table(
        "performance_import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rows_json", sa.Text(), nullable=True),
        sa.Column("errors_json", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.create_table(
        "performance_stage_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("hire_event_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(10), nullable=False),
        sa.Column("role_kind", sa.String(20), nullable=False),
        sa.Column("due_at", sa.String(20), nullable=True),
        sa.Column("assessment_id", sa.Integer(), nullable=True),
    )
    op.create_table(
        "performance_observation_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("end_score", sa.Numeric(8, 2), nullable=True),
        sa.Column("retriggered", sa.Boolean(), nullable=False),
        sa.Column("hr_todo", sa.String(200), nullable=True),
    )
    op.create_table(
        "performance_feedback_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("form_type", sa.String(40), nullable=False),
        sa.Column("subject_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("anonymous", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("performance_feedback_records")
    op.drop_table("performance_observation_cases")
    op.drop_table("performance_stage_cases")
    op.drop_table("performance_import_batches")
    op.drop_table("performance_metric_facts")
    op.drop_table("performance_template_assignments")
    op.drop_constraint("uq_assessment_instance", "performance_assessments", type_="unique")
