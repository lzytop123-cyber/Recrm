"""系统同步状态读写。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.employee_hr import SystemSyncState

SYNC_KEY_CONTACT = "feishu_contact"
SYNC_KEY_ATTENDANCE = "feishu_attendance"


def upsert_sync_state(
    db: Session,
    key: str,
    *,
    status: str,
    last_error: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
    success: bool = False,
) -> SystemSyncState:
    row = db.query(SystemSyncState).filter(SystemSyncState.key == key).first()
    if not row:
        row = SystemSyncState(key=key, status=status)
        db.add(row)
    row.status = status
    row.last_error = last_error
    if meta is not None:
        row.meta_json = json.dumps(meta, ensure_ascii=False)
    if success:
        row.last_success_at = datetime.now(timezone.utc)
    db.flush()
    return row


def get_sync_state(db: Session, key: str) -> Optional[SystemSyncState]:
    return db.query(SystemSyncState).filter(SystemSyncState.key == key).first()


def list_feishu_sync_status(db: Session) -> dict:
    contact = get_sync_state(db, SYNC_KEY_CONTACT)
    attendance = get_sync_state(db, SYNC_KEY_ATTENDANCE)
    items = []
    for key, row in ((SYNC_KEY_CONTACT, contact), (SYNC_KEY_ATTENDANCE, attendance)):
        items.append(
            {
                "key": key,
                "status": row.status if row else "unknown",
                "last_success_at": row.last_success_at if row else None,
                "last_error": row.last_error if row else None,
            }
        )

    statuses = [x["status"] for x in items]
    last_ats = [x["last_success_at"] for x in items if x["last_success_at"]]
    last_sync_at = max(last_ats) if last_ats else None

    if any(s == "error" for s in statuses):
        overall_status, overall_label = "error", "飞书同步异常"
    elif any(s == "ok" for s in statuses):
        overall_status, overall_label = "ok", "飞书同步正常"
    elif any(s == "pending" for s in statuses):
        overall_status, overall_label = "pending", "飞书同步中"
    else:
        overall_status, overall_label = "unknown", "飞书尚未同步"

    return {
        "overall_status": overall_status,
        "overall_label": overall_label,
        "last_sync_at": last_sync_at,
        "items": items,
    }
