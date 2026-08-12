"""roles.module_scopes per-module data scope

Revision ID: u9v0w1x2y3z4
Revises: t8u9v0w1x2y3
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u9v0w1x2y3z4"
down_revision: Union[str, None] = "t8u9v0w1x2y3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("module_scopes", sa.JSON(), nullable=True, comment="模块数据范围覆盖"),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("UPDATE roles SET module_scopes = '{}'::json WHERE module_scopes IS NULL"))
    else:
        op.execute(sa.text("UPDATE roles SET module_scopes = '{}' WHERE module_scopes IS NULL"))
    op.alter_column("roles", "module_scopes", nullable=False)


def downgrade() -> None:
    op.drop_column("roles", "module_scopes")