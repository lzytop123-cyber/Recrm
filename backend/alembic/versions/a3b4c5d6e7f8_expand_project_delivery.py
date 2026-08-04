"""expand project delivery fields

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("payment_verified", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "projects",
        sa.Column("handoff_complete", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "projects",
        sa.Column("contact_confirmed", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("projects", sa.Column("business_owner_id", sa.Integer(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("baseline_version", sa.String(length=30), server_default="V1", nullable=True),
    )
    op.add_column("projects", sa.Column("acceptance_result", sa.String(length=20), nullable=True))
    op.add_column("projects", sa.Column("accepted_at", sa.Date(), nullable=True))
    op.add_column("projects", sa.Column("acceptance_method", sa.String(length=50), nullable=True))
    op.add_column("projects", sa.Column("acceptance_owner_id", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("acceptance_conclusion", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("leftover_summary", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_projects_business_owner_id", "projects", "users", ["business_owner_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_projects_acceptance_owner_id", "projects", "users", ["acceptance_owner_id"], ["id"]
    )

    op.add_column("project_milestones", sa.Column("actual_date", sa.Date(), nullable=True))
    op.add_column("project_milestones", sa.Column("role", sa.String(length=50), nullable=True))
    op.add_column(
        "project_milestones", sa.Column("deliverable", sa.String(length=200), nullable=True)
    )
    op.add_column("project_milestones", sa.Column("evidence", sa.String(length=200), nullable=True))

    op.create_table(
        "project_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_no", sa.String(length=50), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("milestone_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("criteria", sa.Text(), nullable=True),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("planned_hours", sa.Numeric(10, 2), nullable=True),
        sa.Column("actual_hours", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("ticket_id", sa.Integer(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["milestone_id"], ["project_milestones.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_tasks_task_no", "project_tasks", ["task_no"])
    op.create_index("ix_project_tasks_project_id", "project_tasks", ["project_id"])
    op.create_index("ix_project_tasks_assignee_id", "project_tasks", ["assignee_id"])
    op.create_index("ix_project_tasks_due_date", "project_tasks", ["due_date"])
    op.create_index("ix_project_tasks_status", "project_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_project_tasks_status", table_name="project_tasks")
    op.drop_index("ix_project_tasks_due_date", table_name="project_tasks")
    op.drop_index("ix_project_tasks_assignee_id", table_name="project_tasks")
    op.drop_index("ix_project_tasks_project_id", table_name="project_tasks")
    op.drop_index("ix_project_tasks_task_no", table_name="project_tasks")
    op.drop_table("project_tasks")

    op.drop_column("project_milestones", "evidence")
    op.drop_column("project_milestones", "deliverable")
    op.drop_column("project_milestones", "role")
    op.drop_column("project_milestones", "actual_date")

    op.drop_constraint("fk_projects_acceptance_owner_id", "projects", type_="foreignkey")
    op.drop_constraint("fk_projects_business_owner_id", "projects", type_="foreignkey")
    op.drop_column("projects", "leftover_summary")
    op.drop_column("projects", "acceptance_conclusion")
    op.drop_column("projects", "acceptance_owner_id")
    op.drop_column("projects", "acceptance_method")
    op.drop_column("projects", "accepted_at")
    op.drop_column("projects", "acceptance_result")
    op.drop_column("projects", "baseline_version")
    op.drop_column("projects", "business_owner_id")
    op.drop_column("projects", "contact_confirmed")
    op.drop_column("projects", "handoff_complete")
    op.drop_column("projects", "payment_verified")
