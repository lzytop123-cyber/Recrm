"""create fixed assets borrow inventory tables

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fixed_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asset_no", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("serial_no", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("holder_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("original_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("next_maintenance", sa.Date(), nullable=True),
        sa.Column("qr_code", sa.String(length=40), nullable=False),
        sa.Column("current_use", sa.String(length=200), nullable=True),
        sa.Column("schedule_ref", sa.String(length=40), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["holder_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_no"),
        sa.UniqueConstraint("qr_code"),
    )
    op.create_index("ix_fixed_assets_asset_no", "fixed_assets", ["asset_no"])
    op.create_index("ix_fixed_assets_category", "fixed_assets", ["category"])
    op.create_index("ix_fixed_assets_status", "fixed_assets", ["status"])

    op.create_table(
        "asset_borrow_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_no", sa.String(length=40), nullable=False),
        sa.Column("purpose", sa.String(length=200), nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schedule_ref", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["applicant_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_no"),
    )
    op.create_index("ix_asset_borrow_requests_request_no", "asset_borrow_requests", ["request_no"])
    op.create_index("ix_asset_borrow_requests_applicant_id", "asset_borrow_requests", ["applicant_id"])
    op.create_index("ix_asset_borrow_requests_status", "asset_borrow_requests", ["status"])

    op.create_table(
        "asset_borrow_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["asset_borrow_requests.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["fixed_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_borrow_items_request_id", "asset_borrow_items", ["request_id"])
    op.create_index("ix_asset_borrow_items_asset_id", "asset_borrow_items", ["asset_id"])

    op.create_table(
        "asset_inventory_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("period_label", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("scanned_count", sa.Integer(), nullable=False),
        sa.Column("matched_count", sa.Integer(), nullable=False),
        sa.Column("anomaly_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_label"),
    )


def downgrade() -> None:
    op.drop_table("asset_inventory_sessions")
    op.drop_table("asset_borrow_items")
    op.drop_table("asset_borrow_requests")
    op.drop_table("fixed_assets")
