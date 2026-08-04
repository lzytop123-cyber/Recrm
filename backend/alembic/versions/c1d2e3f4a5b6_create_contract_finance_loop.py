"""create contract receivable receipt allocation refund loop

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-07-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "receivable_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="CNY"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="unpaid"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_id", "sequence_no", name="uq_receivable_contract_sequence"),
    )
    op.create_index("ix_receivable_plans_contract_id", "receivable_plans", ["contract_id"])
    op.create_index("ix_receivable_plans_due_date", "receivable_plans", ["due_date"])
    op.create_index("ix_receivable_plans_status", "receivable_plans", ["status"])

    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_no", sa.String(length=50), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("paid_date", sa.Date(), nullable=False),
        sa.Column("payer_name", sa.String(length=200), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("bank_reference", sa.String(length=100), nullable=True),
        sa.Column("proof_filename", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_review"),
        sa.Column("submitted_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_receipts_receipt_no", "receipts", ["receipt_no"], unique=True)
    op.create_index("ix_receipts_contract_id", "receipts", ["contract_id"])
    op.create_index("ix_receipts_paid_date", "receipts", ["paid_date"])
    op.create_index("ix_receipts_status", "receipts", ["status"])
    op.create_index("ix_receipts_idempotency_key", "receipts", ["idempotency_key"], unique=True)

    op.create_table(
        "receipt_allocations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_id", sa.Integer(), nullable=False),
        sa.Column("receivable_plan_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("allocated_by", sa.Integer(), nullable=True),
        sa.Column("allocated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reversed_by", sa.Integer(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reverse_reason", sa.String(length=500), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.id"]),
        sa.ForeignKeyConstraint(["receivable_plan_id"], ["receivable_plans.id"]),
        sa.ForeignKeyConstraint(["allocated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reversed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "receipt_id", "idempotency_key",
            name="uq_allocation_business_key",
        ),
    )
    op.create_index("ix_receipt_allocations_receipt_id", "receipt_allocations", ["receipt_id"])
    op.create_index(
        "ix_receipt_allocations_receivable_plan_id",
        "receipt_allocations",
        ["receivable_plan_id"],
    )
    op.create_index("ix_receipt_allocations_status", "receipt_allocations", ["status"])
    op.create_index(
        "ix_receipt_allocations_idempotency_key",
        "receipt_allocations",
        ["idempotency_key"],
    )

    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("refund_no", sa.String(length=50), nullable=False),
        sa.Column("receipt_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("review_remark", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refunds_refund_no", "refunds", ["refund_no"], unique=True)
    op.create_index("ix_refunds_receipt_id", "refunds", ["receipt_id"])
    op.create_index("ix_refunds_status", "refunds", ["status"])
    op.create_index("ix_refunds_idempotency_key", "refunds", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_refunds_idempotency_key", table_name="refunds")
    op.drop_index("ix_refunds_status", table_name="refunds")
    op.drop_index("ix_refunds_receipt_id", table_name="refunds")
    op.drop_index("ix_refunds_refund_no", table_name="refunds")
    op.drop_table("refunds")
    op.drop_index("ix_receipt_allocations_idempotency_key", table_name="receipt_allocations")
    op.drop_index("ix_receipt_allocations_status", table_name="receipt_allocations")
    op.drop_index("ix_receipt_allocations_receivable_plan_id", table_name="receipt_allocations")
    op.drop_index("ix_receipt_allocations_receipt_id", table_name="receipt_allocations")
    op.drop_table("receipt_allocations")
    op.drop_index("ix_receipts_idempotency_key", table_name="receipts")
    op.drop_index("ix_receipts_status", table_name="receipts")
    op.drop_index("ix_receipts_paid_date", table_name="receipts")
    op.drop_index("ix_receipts_contract_id", table_name="receipts")
    op.drop_index("ix_receipts_receipt_no", table_name="receipts")
    op.drop_table("receipts")
    op.drop_index("ix_receivable_plans_status", table_name="receivable_plans")
    op.drop_index("ix_receivable_plans_due_date", table_name="receivable_plans")
    op.drop_index("ix_receivable_plans_contract_id", table_name="receivable_plans")
    op.drop_table("receivable_plans")
