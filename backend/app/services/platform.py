"""
系统平台：通知、配置、字典、委托、导出、账号。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.platform import (
    Delegation,
    ExportJob,
    Notification,
    SystemConfig,
    SystemDictionary,
)
from app.models.user import User
from app.schemas.system import (
    AccountUpdate,
    DelegationCreate,
    DelegationUpdate,
    ExportJobCreate,
    SystemConfigCreate,
    SystemConfigUpdate,
    SystemDictionaryCreate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    return (u.real_name or u.username) if u else None


# ---- notifications ----


def list_notifications(db: Session, user: User) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.id.desc())
        .all()
    )


def get_notification(db: Session, user: User, notification_id: int) -> Notification:
    row = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="通知不存在")
    return row


def mark_notification_read(db: Session, user: User, notification_id: int) -> Notification:
    row = get_notification(db, user, notification_id)
    row.is_read = True
    db.commit()
    db.refresh(row)
    return row


def mark_all_notifications_read(db: Session, user: User) -> dict:
    (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.is_read.is_(False))
        .update({"is_read": True})
    )
    db.commit()
    return {"ok": True}


def create_notification(
    db: Session,
    *,
    user_id: int,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    category: Optional[str] = None,
) -> Notification:
    row = Notification(
        user_id=user_id,
        title=title,
        body=body,
        link=link,
        category=category,
        is_read=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---- configs / dictionaries ----


def list_configs(db: Session) -> list[SystemConfig]:
    return db.query(SystemConfig).order_by(SystemConfig.key.asc()).all()


def create_config(db: Session, user: User, payload: SystemConfigCreate) -> SystemConfig:
    key = payload.key.strip()
    if db.query(SystemConfig).filter(SystemConfig.key == key).first():
        raise HTTPException(status_code=400, detail="配置键已存在")
    row = SystemConfig(
        key=key,
        value=payload.value,
        description=payload.description,
        updated_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_config(db: Session, key: str) -> SystemConfig:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not row:
        raise HTTPException(status_code=404, detail="配置不存在")
    return row


def update_config(db: Session, user: User, key: str, payload: SystemConfigUpdate) -> SystemConfig:
    row = get_config(db, key)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return row


def list_dictionaries(db: Session) -> list[SystemDictionary]:
    return db.query(SystemDictionary).order_by(SystemDictionary.code.asc()).all()


def create_dictionary(db: Session, payload: SystemDictionaryCreate) -> SystemDictionary:
    code = payload.code.strip()
    if db.query(SystemDictionary).filter(SystemDictionary.code == code).first():
        raise HTTPException(status_code=400, detail="字典编码已存在")
    row = SystemDictionary(code=code, name=payload.name.strip(), items_json=payload.items_json)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_dictionary(db: Session, code: str) -> SystemDictionary:
    row = db.query(SystemDictionary).filter(SystemDictionary.code == code).first()
    if not row:
        raise HTTPException(status_code=404, detail="字典不存在")
    return row


# ---- delegations ----


def _enrich_delegation(db: Session, row: Delegation) -> Delegation:
    row.granter_name = _user_name(db, row.granter_id)  # type: ignore[attr-defined]
    row.grantee_name = _user_name(db, row.grantee_id)  # type: ignore[attr-defined]
    return row


def list_delegations(db: Session, user: User) -> list[Delegation]:
    rows = (
        db.query(Delegation)
        .filter((Delegation.granter_id == user.id) | (Delegation.grantee_id == user.id))
        .order_by(Delegation.id.desc())
        .all()
    )
    return [_enrich_delegation(db, x) for x in rows]


def create_delegation(db: Session, user: User, payload: DelegationCreate) -> Delegation:
    if payload.grantee_id == user.id:
        raise HTTPException(status_code=400, detail="不能委托给自己")
    grantee = db.query(User).filter(User.id == payload.grantee_id).first()
    if not grantee:
        raise HTTPException(status_code=400, detail="被委托人不存在")
    if payload.ends_at and payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")
    row = Delegation(
        granter_id=user.id,
        grantee_id=payload.grantee_id,
        scope=payload.scope.strip() or "all",
        reason=payload.reason,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _enrich_delegation(db, row)


def update_delegation(
    db: Session, user: User, delegation_id: int, payload: DelegationUpdate
) -> Delegation:
    row = db.query(Delegation).filter(Delegation.id == delegation_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="委托不存在")
    if row.granter_id != user.id:
        raise HTTPException(status_code=403, detail="仅委托人可修改")
    if row.status != "active":
        raise HTTPException(status_code=400, detail="仅生效中委托可修改")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return _enrich_delegation(db, row)


def revoke_delegation(db: Session, user: User, delegation_id: int) -> Delegation:
    row = db.query(Delegation).filter(Delegation.id == delegation_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="委托不存在")
    if row.granter_id != user.id:
        raise HTTPException(status_code=403, detail="仅委托人可撤销")
    if row.status != "active":
        raise HTTPException(status_code=400, detail="委托已非生效状态")
    row.status = "revoked"
    db.commit()
    db.refresh(row)
    return _enrich_delegation(db, row)


# ---- exports / jobs ----


def create_export_job(db: Session, user: User, payload: ExportJobCreate) -> ExportJob:
    row = ExportJob(
        type=payload.type.strip(),
        status="pending",
        requested_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    # stub: mark done without real file
    row.status = "done"
    row.finished_at = _now()
    row.file_path = f"/exports/stub/{row.id}.csv"
    db.commit()
    db.refresh(row)
    return row


def export_download(db: Session, user: User, job_id: int) -> dict:
    row = db.query(ExportJob).filter(ExportJob.id == job_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="导出任务不存在")
    if row.requested_by != user.id:
        role_codes = {r.code for r in user.roles}
        if "admin" not in role_codes:
            raise HTTPException(status_code=403, detail="无权下载该导出")
    if not row.file_path:
        return {
            "id": row.id,
            "status": row.status,
            "download_url": None,
            "message": "文件尚未生成",
        }
    return {
        "id": row.id,
        "status": row.status,
        "download_url": row.file_path,
        "message": "ok",
    }


def list_jobs(db: Session) -> list[ExportJob]:
    return db.query(ExportJob).order_by(ExportJob.id.desc()).limit(100).all()


def list_dead_letters() -> list:
    return []


def retry_job(db: Session, job_id: int) -> ExportJob:
    row = db.query(ExportJob).filter(ExportJob.id == job_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    row.status = "pending"
    row.error = None
    row.finished_at = None
    db.commit()
    row.status = "done"
    row.finished_at = _now()
    row.file_path = row.file_path or f"/exports/stub/{row.id}.csv"
    db.commit()
    db.refresh(row)
    return row


# ---- accounts ----


def list_accounts(db: Session) -> list[dict]:
    users = (
        db.query(User)
        .options(joinedload(User.roles))
        .order_by(User.id.asc())
        .all()
    )
    return [
        {
            "id": u.id,
            "username": u.username,
            "real_name": u.real_name,
            "email": u.email,
            "is_active": u.is_active,
            "role_codes": [r.code for r in u.roles],
            "department_id": u.department_id,
        }
        for u in users
    ]


def update_account(db: Session, account_id: int, payload: AccountUpdate) -> dict:
    user = db.query(User).options(joinedload(User.roles)).filter(User.id == account_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "email": user.email,
        "is_active": user.is_active,
        "role_codes": [r.code for r in user.roles],
        "department_id": user.department_id,
    }


def set_account_active(db: Session, account_id: int, *, active: bool) -> dict:
    return update_account(db, account_id, AccountUpdate(is_active=active))
