"""extend performance with templates and assessment items

Revision ID: f0a1b2c3d4e5
Revises: z4a5b6c7d8e9
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "z4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "performance_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("base_template_id", sa.Integer(), nullable=True, comment="null=HR 基础模板；非 null=部门 fork 自哪份基础模板"),
        sa.Column("owner_type", sa.String(length=20), nullable=False, server_default=sa.text("'hr'")),
        sa.Column("owner_dept_id", sa.Integer(), nullable=True),
        sa.Column("cycle_type", sa.String(length=20), nullable=False, server_default=sa.text("'monthly'")),
        sa.Column("rules_json", sa.Text(), nullable=True, comment="HR 基础模板：权重上下限 / 数据源白名单 / 评分规则"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("approval_instance_id", sa.Integer(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["base_template_id"], ["performance_templates.id"]),
        sa.ForeignKeyConstraint(["owner_dept_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["approval_instance_id"], ["approval_instances.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_performance_templates_code", "performance_templates", ["code"], unique=True)
    op.create_index("ix_performance_templates_owner_type", "performance_templates", ["owner_type"])
    op.create_index("ix_performance_templates_status", "performance_templates", ["status"])

    op.create_table(
        "performance_template_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("order_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False),
        sa.Column("data_source", sa.String(length=20), nullable=False),
        sa.Column("source_ref", sa.String(length=120), nullable=True),
        sa.Column("target_value", sa.String(length=60), nullable=True),
        sa.Column("score_rule", sa.String(length=200), nullable=True),
        sa.Column("hint", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["performance_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_performance_template_items_template_id", "performance_template_items", ["template_id"])
    op.create_index("ix_performance_template_items_data_source", "performance_template_items", ["data_source"])

    op.create_table(
        "performance_assessment_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("template_item_id", sa.Integer(), nullable=True, comment="追溯来源，只读"),
        sa.Column("order_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False),
        sa.Column("data_source", sa.String(length=20), nullable=False),
        sa.Column("source_ref", sa.String(length=120), nullable=True),
        sa.Column("target_value", sa.String(length=60), nullable=True),
        sa.Column("score_rule", sa.String(length=200), nullable=True),
        sa.Column("actual_value", sa.String(length=60), nullable=True),
        sa.Column("system_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("self_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("self_comment", sa.Text(), nullable=True),
        sa.Column("leader_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("leader_comment", sa.Text(), nullable=True),
        sa.Column("final_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["performance_assessments.id"]),
        sa.ForeignKeyConstraint(["template_item_id"], ["performance_template_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_performance_assessment_items_assessment_id",
        "performance_assessment_items",
        ["assessment_id"],
    )

    with op.batch_alter_table("performance_cycles") as batch:
        batch.add_column(
            sa.Column("cycle_type", sa.String(length=20), nullable=False, server_default=sa.text("'monthly'"))
        )
        batch.add_column(sa.Column("default_template_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_performance_cycles_default_template_id",
            "performance_templates",
            ["default_template_id"],
            ["id"],
        )
        batch.create_index("ix_performance_cycles_cycle_type", ["cycle_type"])

    with op.batch_alter_table("performance_assessments") as batch:
        batch.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("approval_instance_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_performance_assessments_template_id",
            "performance_templates",
            ["template_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_performance_assessments_approval_instance_id",
            "approval_instances",
            ["approval_instance_id"],
            ["id"],
        )
        batch.create_index("ix_performance_assessments_template_id", ["template_id"])
        batch.create_index("ix_performance_assessments_approval_instance_id", ["approval_instance_id"])


def downgrade() -> None:
    with op.batch_alter_table("performance_assessments") as batch:
        batch.drop_index("ix_performance_assessments_approval_instance_id")
        batch.drop_index("ix_performance_assessments_template_id")
        batch.drop_constraint("fk_performance_assessments_approval_instance_id", type_="foreignkey")
        batch.drop_constraint("fk_performance_assessments_template_id", type_="foreignkey")
        batch.drop_column("approval_instance_id")
        batch.drop_column("template_id")

    with op.batch_alter_table("performance_cycles") as batch:
        batch.drop_index("ix_performance_cycles_cycle_type")
        batch.drop_constraint("fk_performance_cycles_default_template_id", type_="foreignkey")
        batch.drop_column("default_template_id")
        batch.drop_column("cycle_type")

    op.drop_table("performance_assessment_items")
    op.drop_table("performance_template_items")
    op.drop_table("performance_templates")
