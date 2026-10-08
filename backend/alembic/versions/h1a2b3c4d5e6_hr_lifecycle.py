"""hr lifecycle tables: contracts, transfers, resignations, leave, payslips

Revision ID: h1a2b3c4d5e6
Revises: g2a3b4c5d6e7
Create Date: 2026-09-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h1a2b3c4d5e6"
down_revision: Union[str, None] = "g2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hr_labor_contracts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("contract_type", sa.String(length=30), nullable=False),
        sa.Column("signed_on", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("trial_start", sa.Date(), nullable=True),
        sa.Column("trial_end", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_sign"),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("remark", sa.String(length=300), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["hr_labor_contracts.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_labor_contracts_employee_id", "hr_labor_contracts", ["employee_id"])
    op.create_index("ix_hr_labor_contracts_status", "hr_labor_contracts", ["status"])

    op.create_table(
        "hr_transfers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("from_department_id", sa.Integer(), nullable=True),
        sa.Column("to_department_id", sa.Integer(), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("job_title", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("approval_instance_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["from_department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["to_department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["approval_instance_id"], ["approval_instances.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_transfers_employee_id", "hr_transfers", ["employee_id"])

    op.create_table(
        "hr_resignations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("last_working_day", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_approval"),
        sa.Column("approval_instance_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approval_instance_id"], ["approval_instances.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_resignations_employee_id", "hr_resignations", ["employee_id"])

    op.create_table(
        "hr_handovers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("resignation_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("signed_by", sa.Integer(), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["resignation_id"], ["hr_resignations.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["signed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resignation_id"),
    )

    op.create_table(
        "hr_handover_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("handover_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["handover_id"], ["hr_handovers.id"]),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_handover_items_handover_id", "hr_handover_items", ["handover_id"])

    op.create_table(
        "hr_leave_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("leave_type", sa.String(length=30), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Numeric(6, 1), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("approval_instance_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approval_instance_id"], ["approval_instances.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_leave_requests_employee_id", "hr_leave_requests", ["employee_id"])

    op.create_table(
        "hr_leave_balances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("leave_type", sa.String(length=30), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("quota", sa.Numeric(6, 1), nullable=False, server_default="0"),
        sa.Column("used", sa.Numeric(6, 1), nullable=False, server_default="0"),
        sa.Column("remaining", sa.Numeric(6, 1), nullable=False, server_default="0"),
        sa.Column("remark", sa.String(length=300), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "leave_type", "year", name="uq_hr_leave_balance"),
    )

    op.create_table(
        "hr_payslips",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=True),
        sa.Column("period_label", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="published"),
        sa.Column("base_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("performance_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("adjustment_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("items_json", sa.Text(), nullable=True),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["performance_cycles.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["hr_payslips.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_payslips_employee_id", "hr_payslips", ["employee_id"])
    op.create_index("ix_hr_payslips_period_label", "hr_payslips", ["period_label"])


def downgrade() -> None:
    op.drop_table("hr_payslips")
    op.drop_table("hr_leave_balances")
    op.drop_table("hr_leave_requests")
    op.drop_table("hr_handover_items")
    op.drop_table("hr_handovers")
    op.drop_table("hr_resignations")
    op.drop_table("hr_transfers")
    op.drop_table("hr_labor_contracts")
