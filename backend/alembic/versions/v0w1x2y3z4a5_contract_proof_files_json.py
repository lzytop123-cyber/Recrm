"""contract proof multi-file json

Revision ID: v0w1x2y3z4a5
Revises: u9v0w1x2y3z4
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v0w1x2y3z4a5"
down_revision: Union[str, None] = "u9v0w1x2y3z4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("proof_files_json", sa.Text(), nullable=True, comment="合同证明多文件JSON"),
    )
    # 回填历史单文件到 JSON 数组
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, proof_filename, proof_path FROM contracts "
            "WHERE proof_path IS NOT NULL AND proof_path != ''"
        )
    ).fetchall()
    for row in rows:
        cid, filename, path = row[0], row[1] or "", row[2]
        payload = sa.text(
            "UPDATE contracts SET proof_files_json = :js WHERE id = :id"
        )
        import json

        conn.execute(
            payload,
            {
                "id": cid,
                "js": json.dumps(
                    [{"filename": filename or path.split("/")[-1], "path": path}],
                    ensure_ascii=False,
                ),
            },
        )


def downgrade() -> None:
    op.drop_column("contracts", "proof_files_json")
