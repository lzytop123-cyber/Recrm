"""seed business_type system dictionary

Revision ID: r6s7t8u9v0w1
Revises: q5r6s7t8u9v0
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r6s7t8u9v0w1"
down_revision: Union[str, None] = "q5r6s7t8u9v0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ITEMS_JSON = (
    '[{"value":"ai_product","label":"AI产品销售","enabled":true,"sort":10},'
    '{"value":"ai_custom","label":"AI定制开发","enabled":true,"sort":20},'
    '{"value":"media_ops","label":"自媒体代运营","enabled":true,"sort":30},'
    '{"value":"other","label":"其他","enabled":true,"sort":90}]'
)


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT id FROM system_dictionaries WHERE code = :code"),
        {"code": "business_type"},
    ).fetchone()
    if exists:
        return
    conn.execute(
        sa.text(
            "INSERT INTO system_dictionaries (code, name, items_json) "
            "VALUES (:code, :name, :items_json)"
        ),
        {
            "code": "business_type",
            "name": "业务类型",
            "items_json": ITEMS_JSON,
        },
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_dictionaries WHERE code = 'business_type'")
