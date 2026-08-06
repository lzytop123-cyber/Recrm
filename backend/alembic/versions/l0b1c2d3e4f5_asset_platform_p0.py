"""asset platform p0 tables

Revision ID: l0b1c2d3e4f5
Revises: j8e9f0a1b2c3
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l0b1c2d3e4f5"
down_revision: Union[str, None] = "j8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_inventory_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("qr_code", sa.String(length=40), nullable=True),
        sa.Column("result", sa.String(length=30), nullable=False),
        sa.Column("scanned_by", sa.Integer(), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["asset_inventory_sessions.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["fixed_assets.id"]),
        sa.ForeignKeyConstraint(["scanned_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_inventory_lines_session_id", "asset_inventory_lines", ["session_id"])
    op.create_index("ix_asset_inventory_lines_asset_id", "asset_inventory_lines", ["asset_id"])

    op.create_table(
        "asset_maintenances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["fixed_assets.id"]),
        sa.ForeignKeyConstraint(["applicant_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_maintenances_asset_id", "asset_maintenances", ["asset_id"])
    op.create_index("ix_asset_maintenances_status", "asset_maintenances", ["status"])

    op.create_table(
        "asset_depreciation_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("residual_rate", sa.Numeric(8, 4), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_depreciation_rules_status", "asset_depreciation_rules", ["status"])

    op.create_table(
        "asset_depreciation_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("period_label", sa.String(length=7), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("original_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("monthly_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("accumulated", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["fixed_assets.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["asset_depreciation_rules.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_label", "asset_id", name="uq_depr_snapshot_period_asset"),
    )
    op.create_index(
        "ix_asset_depreciation_snapshots_period_label",
        "asset_depreciation_snapshots",
        ["period_label"],
    )
    op.create_index(
        "ix_asset_depreciation_snapshots_asset_id",
        "asset_depreciation_snapshots",
        ["asset_id"],
    )

    op.create_table(
        "asset_disposals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("disposed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["fixed_assets.id"]),
        sa.ForeignKeyConstraint(["applicant_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_disposals_asset_id", "asset_disposals", ["asset_id"])
    op.create_index("ix_asset_disposals_status", "asset_disposals", ["status"])

    op.create_table(
        "shooting_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("shoot_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shooting_schedules_shoot_date", "shooting_schedules", ["shoot_date"])
    op.create_index("ix_shooting_schedules_owner_id", "shooting_schedules", ["owner_id"])
    op.create_index("ix_shooting_schedules_status", "shooting_schedules", ["status"])

    op.create_table(
        "shooting_schedule_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["schedule_id"], ["shooting_schedules.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["fixed_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_shooting_schedule_assets_schedule_id",
        "shooting_schedule_assets",
        ["schedule_id"],
    )
    op.create_index(
        "ix_shooting_schedule_assets_asset_id",
        "shooting_schedule_assets",
        ["asset_id"],
    )

    op.create_table(
        "shooting_schedule_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["schedule_id"], ["shooting_schedules.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_shooting_schedule_members_schedule_id",
        "shooting_schedule_members",
        ["schedule_id"],
    )
    op.create_index(
        "ix_shooting_schedule_members_user_id",
        "shooting_schedule_members",
        ["user_id"],
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=300), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    op.create_table(
        "system_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_system_configs_key", "system_configs", ["key"])

    op.create_table(
        "system_dictionaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("items_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_system_dictionaries_code", "system_dictionaries", ["code"])

    op.create_table(
        "delegations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("granter_id", sa.Integer(), nullable=False),
        sa.Column("grantee_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["granter_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["grantee_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delegations_granter_id", "delegations", ["granter_id"])
    op.create_index("ix_delegations_grantee_id", "delegations", ["grantee_id"])
    op.create_index("ix_delegations_status", "delegations", ["status"])

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_jobs_type", "export_jobs", ["type"])
    op.create_index("ix_export_jobs_status", "export_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("export_jobs")
    op.drop_table("delegations")
    op.drop_table("system_dictionaries")
    op.drop_table("system_configs")
    op.drop_table("notifications")
    op.drop_table("shooting_schedule_members")
    op.drop_table("shooting_schedule_assets")
    op.drop_table("shooting_schedules")
    op.drop_table("asset_disposals")
    op.drop_table("asset_depreciation_snapshots")
    op.drop_table("asset_depreciation_rules")
    op.drop_table("asset_maintenances")
    op.drop_table("asset_inventory_lines")
