"""
系统平台：通知、配置、字典、委托、导出、账号。
"""
from __future__ import annotations

import json
import re
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
    SystemDictionaryUpdate,
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
    ensure_business_type_dictionary(db)
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
    if code == BUSINESS_TYPE_DICT_CODE:
        return ensure_business_type_dictionary(db)
    row = db.query(SystemDictionary).filter(SystemDictionary.code == code).first()
    if not row:
        raise HTTPException(status_code=404, detail="字典不存在")
    return row


def update_dictionary(
    db: Session, code: str, payload: SystemDictionaryUpdate
) -> SystemDictionary:
    row = get_dictionary(db, code)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        name = str(data["name"]).strip()
        if not name:
            raise HTTPException(status_code=400, detail="字典名称不能为空")
        row.name = name
    if "items_json" in data:
        # 统一走规范化，避免脏数据
        if code == BUSINESS_TYPE_DICT_CODE:
            raw_items = json.loads(data["items_json"] or "[]")
            if not isinstance(raw_items, list):
                raise HTTPException(status_code=400, detail="字典项格式无效")
            row.items_json = json.dumps(
                _normalize_business_type_items(raw_items),
                ensure_ascii=False,
            )
        else:
            row.items_json = data["items_json"]
    db.commit()
    db.refresh(row)
    return row


# ---- business type dictionary ----

BUSINESS_TYPE_DICT_CODE = "business_type"

DEFAULT_BUSINESS_TYPE_ITEMS: list[dict] = [
    {"value": "ai_product", "label": "AI产品销售", "enabled": True, "sort": 10},
    {"value": "ai_custom", "label": "AI定制开发", "enabled": True, "sort": 20},
    {"value": "media_ops", "label": "自媒体代运营", "enabled": True, "sort": 30},
    {"value": "other", "label": "其他", "enabled": True, "sort": 90},
]

_VALUE_RE = re.compile(r"^[a-z][a-z0-9_]{0,29}$")


def _normalize_business_type_items(raw: list) -> list[dict]:
    cleaned: list[dict] = []
    seen: set[str] = set()
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail=f"第 {idx + 1} 项格式无效")
        value = str(item.get("value") or "").strip()
        label = str(item.get("label") or "").strip()
        if not value or not label:
            raise HTTPException(status_code=400, detail=f"第 {idx + 1} 项编码和名称必填")
        if not _VALUE_RE.match(value):
            raise HTTPException(
                status_code=400,
                detail=f"编码「{value}」仅支持小写字母开头，字母/数字/下划线，最长 30",
            )
        if value in seen:
            raise HTTPException(status_code=400, detail=f"编码重复：{value}")
        seen.add(value)
        enabled = bool(item.get("enabled", True))
        try:
            sort = int(item.get("sort", (idx + 1) * 10))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"编码「{value}」排序值无效") from exc
        cleaned.append(
            {"value": value, "label": label[:80], "enabled": enabled, "sort": sort}
        )
    if not cleaned:
        raise HTTPException(status_code=400, detail="至少保留一个业务类型")
    if "other" not in seen:
        raise HTTPException(status_code=400, detail="请保留编码为 other 的「其他」类型")
    if not any(x["enabled"] for x in cleaned):
        raise HTTPException(status_code=400, detail="至少启用一个业务类型")
    cleaned.sort(key=lambda x: (x["sort"], x["value"]))
    return cleaned


def ensure_business_type_dictionary(db: Session) -> SystemDictionary:
    row = (
        db.query(SystemDictionary)
        .filter(SystemDictionary.code == BUSINESS_TYPE_DICT_CODE)
        .first()
    )
    if row:
        return row
    row = SystemDictionary(
        code=BUSINESS_TYPE_DICT_CODE,
        name="业务类型",
        items_json=json.dumps(DEFAULT_BUSINESS_TYPE_ITEMS, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def parse_dictionary_items(items_json: Optional[str]) -> list[dict]:
    if not items_json:
        return []
    try:
        data = json.loads(items_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value") or "").strip()
        label = str(item.get("label") or "").strip()
        if not value or not label:
            continue
        out.append(
            {
                "value": value,
                "label": label,
                "enabled": bool(item.get("enabled", True)),
                "sort": int(item.get("sort") or 100),
            }
        )
    out.sort(key=lambda x: (x["sort"], x["value"]))
    return out


def list_business_type_items(db: Session, *, enabled_only: bool = False) -> list[dict]:
    row = ensure_business_type_dictionary(db)
    items = parse_dictionary_items(row.items_json)
    if not items:
        items = list(DEFAULT_BUSINESS_TYPE_ITEMS)
    if enabled_only:
        items = [x for x in items if x.get("enabled", True)]
    return items


def business_type_values(db: Session, *, enabled_only: bool = False) -> set[str]:
    return {x["value"] for x in list_business_type_items(db, enabled_only=enabled_only)}


def business_type_label_map(db: Session) -> dict[str, str]:
    return {x["value"]: x["label"] for x in list_business_type_items(db, enabled_only=False)}


def assert_business_type(db: Session, value: str, *, enabled_only: bool = True) -> str:
    code = (value or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="业务类型不能为空")
    allowed = business_type_values(db, enabled_only=enabled_only)
    if code not in allowed:
        # 兼容：已停用但仍存在的类型，在非 enabled_only 场景可用
        if enabled_only and code in business_type_values(db, enabled_only=False):
            raise HTTPException(status_code=400, detail="该业务类型已停用")
        raise HTTPException(status_code=400, detail="无效的业务类型")
    return code


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
