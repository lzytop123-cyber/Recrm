"""kpi runtime: indicator library, scopes, batches, materials, action logs

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2026-09-22

可重复执行：半应用环境（表已存在但列未加）可安全 upgrade。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "r0s1t2u3v4w5"
down_revision: Union[str, None] = "q9r0s1t2u3v4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(name)


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _indexes(table: str) -> set[str]:
    bind = op.get_bind()
    return {ix["name"] for ix in inspect(bind).get_indexes(table) if ix.get("name")}


def _fks(table: str) -> set[str]:
    bind = op.get_bind()
    return {fk["name"] for fk in inspect(bind).get_foreign_keys(table) if fk.get("name")}


def upgrade() -> None:
    if not _has_table("performance_indicator_definitions"):
        op.create_table(
            "performance_indicator_definitions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("metric_key", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
            sa.Column("job_title", sa.String(length=80), nullable=True),
            sa.Column("scoring_type", sa.String(length=30), nullable=False),
            sa.Column("default_target", sa.String(length=80), nullable=True),
            sa.Column("unit", sa.String(length=30), nullable=False, server_default=""),
            sa.Column("data_source_code", sa.String(length=60), nullable=False),
            sa.Column("handling_mode", sa.String(length=30), nullable=False),
            sa.Column("rule_config_json", sa.Text(), nullable=True),
            sa.Column("evidence_policy_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("metric_key", name="uq_indicator_metric_key"),
        )
    if "ix_performance_indicator_definitions_metric_key" not in _indexes("performance_indicator_definitions"):
        op.create_index(
            "ix_performance_indicator_definitions_metric_key",
            "performance_indicator_definitions",
            ["metric_key"],
        )
    if "ix_performance_indicator_definitions_status" not in _indexes("performance_indicator_definitions"):
        op.create_index(
            "ix_performance_indicator_definitions_status",
            "performance_indicator_definitions",
            ["status"],
        )

    if not _has_table("performance_template_scopes"):
        op.create_table(
            "performance_template_scopes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("template_id", sa.Integer(), sa.ForeignKey("performance_templates.id"), nullable=False),
            sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
            sa.Column("job_title", sa.String(length=80), nullable=False),
            sa.UniqueConstraint("template_id", "department_id", "job_title", name="uq_template_scope"),
        )
    if "ix_performance_template_scopes_template_id" not in _indexes("performance_template_scopes"):
        op.create_index(
            "ix_performance_template_scopes_template_id",
            "performance_template_scopes",
            ["template_id"],
        )

    if not _has_table("performance_assessment_batches"):
        op.create_table(
            "performance_assessment_batches",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("performance_cycles.id"), nullable=False),
            sa.Column("template_id", sa.Integer(), sa.ForeignKey("performance_templates.id"), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="launched"),
            sa.Column("employee_due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("manager_due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("hr_review_due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("confirm_due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("hr_review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("idempotency_key", sa.String(length=80), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("idempotency_key", name="uq_assessment_batch_idempotency"),
        )
    for ix, cols, unique in (
        ("ix_performance_assessment_batches_cycle_id", ["cycle_id"], False),
        ("ix_performance_assessment_batches_template_id", ["template_id"], False),
        ("ix_performance_assessment_batches_status", ["status"], False),
        ("ix_performance_assessment_batches_idempotency_key", ["idempotency_key"], True),
    ):
        if ix not in _indexes("performance_assessment_batches"):
            op.create_index(ix, "performance_assessment_batches", cols, unique=unique)

    tcols = _columns("performance_templates")
    with op.batch_alter_table("performance_templates") as batch:
        if "effective_from" not in tcols:
            batch.add_column(sa.Column("effective_from", sa.Date(), nullable=True))
        if "effective_to" not in tcols:
            batch.add_column(sa.Column("effective_to", sa.Date(), nullable=True))
        if "published_at" not in tcols:
            batch.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        if "published_by" not in tcols:
            batch.add_column(sa.Column("published_by", sa.Integer(), nullable=True))
        if "eligibility_policy_json" not in tcols:
            batch.add_column(sa.Column("eligibility_policy_json", sa.Text(), nullable=True))
        if "fk_performance_templates_published_by" not in _fks("performance_templates") and (
            "published_by" not in tcols or "published_by" in tcols
        ):
            # FK may be missing even if column was added earlier without constraint
            pass
    if "published_by" in _columns("performance_templates") and (
        "fk_performance_templates_published_by" not in _fks("performance_templates")
    ):
        op.create_foreign_key(
            "fk_performance_templates_published_by",
            "performance_templates",
            "users",
            ["published_by"],
            ["id"],
        )

    icols = _columns("performance_template_items")
    with op.batch_alter_table("performance_template_items") as batch:
        if "indicator_definition_id" not in icols:
            batch.add_column(sa.Column("indicator_definition_id", sa.Integer(), nullable=True))
        if "scoring_type" not in icols:
            batch.add_column(sa.Column("scoring_type", sa.String(length=30), nullable=True))
        if "unit" not in icols:
            batch.add_column(sa.Column("unit", sa.String(length=30), nullable=True))
        if "handling_mode" not in icols:
            batch.add_column(sa.Column("handling_mode", sa.String(length=30), nullable=True))
        if "evidence_policy_json" not in icols:
            batch.add_column(sa.Column("evidence_policy_json", sa.Text(), nullable=True))
    if "indicator_definition_id" in _columns("performance_template_items"):
        if "fk_template_items_indicator_definition" not in _fks("performance_template_items"):
            op.create_foreign_key(
                "fk_template_items_indicator_definition",
                "performance_template_items",
                "performance_indicator_definitions",
                ["indicator_definition_id"],
                ["id"],
            )
        if "ix_template_items_indicator_definition_id" not in _indexes("performance_template_items"):
            op.create_index(
                "ix_template_items_indicator_definition_id",
                "performance_template_items",
                ["indicator_definition_id"],
            )

    acols = _columns("performance_assessments")
    with op.batch_alter_table("performance_assessments") as batch:
        if "batch_id" not in acols:
            batch.add_column(sa.Column("batch_id", sa.Integer(), nullable=True))
        if "manager_id" not in acols:
            batch.add_column(sa.Column("manager_id", sa.Integer(), nullable=True))
        if "current_handler_type" not in acols:
            batch.add_column(sa.Column("current_handler_type", sa.String(length=30), nullable=True))
        if "current_handler_id" not in acols:
            batch.add_column(sa.Column("current_handler_id", sa.Integer(), nullable=True))
        if "person_snapshot_json" not in acols:
            batch.add_column(sa.Column("person_snapshot_json", sa.Text(), nullable=True))
        if "workflow_config_json" not in acols:
            batch.add_column(sa.Column("workflow_config_json", sa.Text(), nullable=True))
        if "completed_at" not in acols:
            batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    acols = _columns("performance_assessments")
    afks = _fks("performance_assessments")
    aidx = _indexes("performance_assessments")
    if "batch_id" in acols and "fk_assessments_batch_id" not in afks:
        op.create_foreign_key(
            "fk_assessments_batch_id",
            "performance_assessments",
            "performance_assessment_batches",
            ["batch_id"],
            ["id"],
        )
    if "manager_id" in acols and "fk_assessments_manager_id" not in afks:
        op.create_foreign_key(
            "fk_assessments_manager_id",
            "performance_assessments",
            "users",
            ["manager_id"],
            ["id"],
        )
    if "current_handler_id" in acols and "fk_assessments_current_handler_id" not in afks:
        op.create_foreign_key(
            "fk_assessments_current_handler_id",
            "performance_assessments",
            "users",
            ["current_handler_id"],
            ["id"],
        )
    if "batch_id" in acols and "ix_performance_assessments_batch_id" not in aidx:
        op.create_index("ix_performance_assessments_batch_id", "performance_assessments", ["batch_id"])
    if "manager_id" in acols and "ix_performance_assessments_manager_id" not in aidx:
        op.create_index("ix_performance_assessments_manager_id", "performance_assessments", ["manager_id"])
    if "current_handler_id" in acols and "ix_performance_assessments_current_handler_id" not in aidx:
        op.create_index(
            "ix_performance_assessments_current_handler_id",
            "performance_assessments",
            ["current_handler_id"],
        )

    if not _has_table("performance_material_tasks"):
        op.create_table(
            "performance_material_tasks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("performance_assessments.id"), nullable=False),
            sa.Column(
                "assessment_item_id",
                sa.Integer(),
                sa.ForeignKey("performance_assessment_items.id"),
                nullable=False,
            ),
            sa.Column("source_record_type", sa.String(length=60), nullable=False),
            sa.Column("source_record_id", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("existing_data_json", sa.Text(), nullable=True),
            sa.Column("missing_fields_json", sa.Text(), nullable=True),
            sa.Column("requirement_text", sa.Text(), nullable=True),
            sa.Column("employee_content", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("return_reason", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
            sa.UniqueConstraint(
                "assessment_id",
                "assessment_item_id",
                "source_record_type",
                "source_record_id",
                name="uq_material_task_source",
            ),
        )
    for ix, cols in (
        ("ix_performance_material_tasks_assessment_id", ["assessment_id"]),
        ("ix_performance_material_tasks_assessment_item_id", ["assessment_item_id"]),
        ("ix_performance_material_tasks_status", ["status"]),
    ):
        if _has_table("performance_material_tasks") and ix not in _indexes("performance_material_tasks"):
            op.create_index(ix, "performance_material_tasks", cols)

    if not _has_table("performance_action_logs"):
        op.create_table(
            "performance_action_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("performance_assessments.id"), nullable=False),
            sa.Column("action", sa.String(length=60), nullable=False),
            sa.Column("from_status", sa.String(length=30), nullable=True),
            sa.Column("to_status", sa.String(length=30), nullable=True),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
    if _has_table("performance_action_logs") and (
        "ix_performance_action_logs_assessment_id" not in _indexes("performance_action_logs")
    ):
        op.create_index(
            "ix_performance_action_logs_assessment_id",
            "performance_action_logs",
            ["assessment_id"],
        )


def downgrade() -> None:
    if _has_table("performance_action_logs"):
        op.drop_table("performance_action_logs")
    if _has_table("performance_material_tasks"):
        op.drop_table("performance_material_tasks")
    if _has_table("performance_assessments"):
        acols = _columns("performance_assessments")
        afks = _fks("performance_assessments")
        aidx = _indexes("performance_assessments")
        with op.batch_alter_table("performance_assessments") as batch:
            if "fk_assessments_current_handler_id" in afks:
                batch.drop_constraint("fk_assessments_current_handler_id", type_="foreignkey")
            if "fk_assessments_manager_id" in afks:
                batch.drop_constraint("fk_assessments_manager_id", type_="foreignkey")
            if "fk_assessments_batch_id" in afks:
                batch.drop_constraint("fk_assessments_batch_id", type_="foreignkey")
            if "ix_performance_assessments_current_handler_id" in aidx:
                batch.drop_index("ix_performance_assessments_current_handler_id")
            if "ix_performance_assessments_manager_id" in aidx:
                batch.drop_index("ix_performance_assessments_manager_id")
            if "ix_performance_assessments_batch_id" in aidx:
                batch.drop_index("ix_performance_assessments_batch_id")
            for col in (
                "completed_at",
                "workflow_config_json",
                "person_snapshot_json",
                "current_handler_id",
                "current_handler_type",
                "manager_id",
                "batch_id",
            ):
                if col in acols:
                    batch.drop_column(col)
    if _has_table("performance_template_items"):
        icols = _columns("performance_template_items")
        ifks = _fks("performance_template_items")
        iidx = _indexes("performance_template_items")
        with op.batch_alter_table("performance_template_items") as batch:
            if "fk_template_items_indicator_definition" in ifks:
                batch.drop_constraint("fk_template_items_indicator_definition", type_="foreignkey")
            if "ix_template_items_indicator_definition_id" in iidx:
                batch.drop_index("ix_template_items_indicator_definition_id")
            for col in (
                "evidence_policy_json",
                "handling_mode",
                "unit",
                "scoring_type",
                "indicator_definition_id",
            ):
                if col in icols:
                    batch.drop_column(col)
    if _has_table("performance_templates"):
        tcols = _columns("performance_templates")
        tfks = _fks("performance_templates")
        with op.batch_alter_table("performance_templates") as batch:
            if "fk_performance_templates_published_by" in tfks:
                batch.drop_constraint("fk_performance_templates_published_by", type_="foreignkey")
            for col in (
                "eligibility_policy_json",
                "published_by",
                "published_at",
                "effective_to",
                "effective_from",
            ):
                if col in tcols:
                    batch.drop_column(col)
    if _has_table("performance_assessment_batches"):
        op.drop_table("performance_assessment_batches")
    if _has_table("performance_template_scopes"):
        op.drop_table("performance_template_scopes")
    if _has_table("performance_indicator_definitions"):
        op.drop_table("performance_indicator_definitions")
