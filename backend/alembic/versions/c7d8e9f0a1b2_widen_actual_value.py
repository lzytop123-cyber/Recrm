"""放宽指标「实际完成 / 目标」列长度（60 → 1000 / 500 字）

实际完成原为 varchar(60)，代码上限放宽到 500 字后写入报
StringDataRightTruncation（接口 500）。此处同步放宽数据库列。

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-10-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "b6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "performance_assessment_items",
        "actual_value",
        existing_type=sa.String(60),
        type_=sa.String(1000),
        existing_nullable=True,
    )
    # 目标值虽然是模板派生，但制度类文字（如区间、口径说明）也可能较长，一并放宽
    op.alter_column(
        "performance_assessment_items",
        "target_value",
        existing_type=sa.String(60),
        type_=sa.String(500),
        existing_nullable=True,
    )
    op.alter_column(
        "performance_template_items",
        "target_value",
        existing_type=sa.String(60),
        type_=sa.String(500),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "performance_template_items",
        "target_value",
        existing_type=sa.String(500),
        type_=sa.String(60),
        existing_nullable=True,
    )
    op.alter_column(
        "performance_assessment_items",
        "target_value",
        existing_type=sa.String(500),
        type_=sa.String(60),
        existing_nullable=True,
    )
    op.alter_column(
        "performance_assessment_items",
        "actual_value",
        existing_type=sa.String(1000),
        type_=sa.String(60),
        existing_nullable=True,
    )
