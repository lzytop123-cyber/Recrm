"""Prompt 版本、场景开关、token 限额、调用审计字段。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent import AiPrompt, AiSceneRun
from app.models.audit_log import AuditLog
from app.models.platform import SystemConfig
from app.models.user import User

SCENES = {
    "knowledge_ask": "知识问答",
    "daily_report": "日报周报",
    "followup_summary": "跟进摘要",
    "ticket_recommend": "工单推荐",
    "approval_precheck": "审批预审",
}
_SCENES_KEY = "ai.scenes"
_BUDGETS_KEY = "ai.budgets"
_CAP_KEY = "ai.auto_pass_max_amount"


def _cfg(db: Session, key: str) -> Optional[SystemConfig]:
    return db.query(SystemConfig).filter(SystemConfig.key == key).first()


def _put_cfg(db: Session, user: User, key: str, value: str, description: str) -> None:
    row = _cfg(db, key)
    if row is None:
        row = SystemConfig(key=key, description=description)
        db.add(row)
    row.value = value
    row.description = description
    row.updated_by = user.id
    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            action="update",
            module="ai",
            target_type="system_config",
            target_id=key,
            detail=value[:500],
        )
    )


def scene_map(db: Session) -> dict[str, bool]:
    row = _cfg(db, _SCENES_KEY)
    stored = {}
    if row and row.value:
        try:
            stored = json.loads(row.value)
        except json.JSONDecodeError:
            stored = {}
    return {code: bool(stored.get(code, True)) for code in SCENES}


def scene_enabled(db: Session, code: str) -> bool:
    return scene_map(db).get(code, True)


def list_scenes(db: Session) -> list[dict]:
    flags = scene_map(db)
    return [{"code": code, "name": name, "enabled": flags[code]} for code, name in SCENES.items()]


def set_scene(db: Session, user: User, code: str, enabled: bool) -> dict:
    if code not in SCENES:
        raise HTTPException(status_code=404, detail="场景不存在")
    flags = scene_map(db)
    flags[code] = enabled
    _put_cfg(db, user, _SCENES_KEY, json.dumps(flags, ensure_ascii=False), "AI 场景开关")
    db.commit()
    return {"code": code, "name": SCENES[code], "enabled": enabled}


def list_budgets(db: Session) -> dict:
    row = _cfg(db, _BUDGETS_KEY)
    items = []
    if row and row.value:
        try:
            items = json.loads(row.value)
        except json.JSONDecodeError:
            items = []
    cap = _cfg(db, _CAP_KEY)
    return {"items": items, "auto_pass_max_amount": cap.value if cap else None}


def save_budgets(
    db: Session,
    user: User,
    items: list[dict],
    auto_pass_max_amount: Optional[str],
) -> dict:
    clean = []
    for item in items:
        scope = item.get("scope")
        if scope not in {"user", "department"}:
            raise HTTPException(status_code=400, detail="scope 仅支持 user 或 department")
        scope_id = int(item["scope_id"])
        monthly = int(item["monthly_tokens"])
        if scope_id < 1 or monthly < 0:
            raise HTTPException(status_code=400, detail="限额参数不合法")
        clean.append({"scope": scope, "scope_id": scope_id, "monthly_tokens": monthly})
    _put_cfg(db, user, _BUDGETS_KEY, json.dumps(clean, ensure_ascii=False), "AI 月度 token 限额")
    if auto_pass_max_amount is not None:
        text = str(auto_pass_max_amount).strip()
        try:
            Decimal(text)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="自动通过限额不是数字") from exc
        _put_cfg(db, user, _CAP_KEY, text, "L1 自动通过金额上限")
    db.commit()
    return list_budgets(db)


def auto_pass_cap(db: Session) -> Optional[Decimal]:
    row = _cfg(db, _CAP_KEY)
    if row is None or not (row.value or "").strip():
        return None
    return Decimal(row.value)


def assert_budget(db: Session, user: User) -> None:
    """未配置不限额。已用 token 达到上限则拒绝，不改业务数据。"""
    data = list_budgets(db)
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for item in data["items"]:
        q = db.query(func.coalesce(func.sum(AiSceneRun.tokens), 0)).filter(AiSceneRun.created_at >= start)
        if item["scope"] == "user":
            if item["scope_id"] != user.id:
                continue
            q = q.filter(AiSceneRun.user_id == user.id)
        else:
            if user.department_id != item["scope_id"]:
                continue
            q = q.join(User, User.id == AiSceneRun.user_id).filter(User.department_id == item["scope_id"])
        used = int(q.scalar() or 0)
        if used >= int(item["monthly_tokens"]):
            raise HTTPException(status_code=429, detail="本月 token 已达上限")


def published_model_version(db: Session, scene: str) -> str:
    row = (
        db.query(AiPrompt)
        .filter(AiPrompt.code == scene, AiPrompt.status == "published")
        .order_by(AiPrompt.version.desc())
        .first()
    )
    if row is None:
        return "facts-v1"
    return f"{row.code}@v{row.version}"


def create_prompt(db: Session, user: User, *, code: str, name: str, content: str) -> AiPrompt:
    code = code.strip()
    if code not in SCENES:
        raise HTTPException(status_code=400, detail="code 必须是已有场景")
    current = db.query(func.max(AiPrompt.version)).filter(AiPrompt.code == code).scalar()
    row = AiPrompt(
        code=code,
        name=name.strip(),
        content=content,
        version=int(current or 0) + 1,
        status="draft",
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_prompts(db: Session) -> list[AiPrompt]:
    return db.query(AiPrompt).order_by(AiPrompt.code.asc(), AiPrompt.version.desc()).all()


def get_prompt(db: Session, prompt_id: int) -> tuple[AiPrompt, list[AiPrompt]]:
    row = db.query(AiPrompt).filter(AiPrompt.id == prompt_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    versions = (
        db.query(AiPrompt).filter(AiPrompt.code == row.code).order_by(AiPrompt.version.desc()).all()
    )
    return row, versions


def publish_prompt(db: Session, user: User, prompt_id: int) -> AiPrompt:
    row, versions = get_prompt(db, prompt_id)
    for other in versions:
        if other.id != row.id and other.status == "published":
            other.status = "archived"
    row.status = "published"
    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            action="publish",
            module="ai",
            target_type="ai_prompt",
            target_id=str(row.id),
            detail=f"{row.code}@v{row.version}",
        )
    )
    db.commit()
    db.refresh(row)
    return row


def prompt_out(row: AiPrompt, versions: Optional[list[AiPrompt]] = None) -> dict:
    data = {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "content": row.content,
        "version": row.version,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if versions is not None:
        data["versions"] = [prompt_out(v) for v in versions]
    return data


def call_view(row: AiSceneRun, *, detail: bool = False) -> dict:
    result = row.result or {}
    data = {
        "id": row.id,
        "user_id": row.user_id,
        "scene": row.scene,
        "status": row.status,
        "target_id": row.target_id,
        "model_version": row.model_version,
        "tokens": int(row.tokens or 0),
        "elapsed_ms": int(row.elapsed_ms or 0),
        "cost": float(row.cost or 0),
        "summary": (result.get("summary") or result.get("rule") or result.get("message") or "")[:200],
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if detail:
        data["result"] = result
        data["body"] = row.body
    return data


def list_spot_checks(db: Session, *, page: int, page_size: int) -> tuple[int, list[AiSceneRun]]:
    q = db.query(AiSceneRun).filter(AiSceneRun.scene == "spot_check")
    total = q.count()
    items = q.order_by(AiSceneRun.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return total, items


def review_spot_check(db: Session, user: User, check_id: int, *, conclusion: str, comment: str) -> dict:
    if conclusion not in {"pass", "fail"}:
        raise HTTPException(status_code=400, detail="conclusion 仅支持 pass 或 fail")
    row = (
        db.query(AiSceneRun)
        .filter(AiSceneRun.id == check_id, AiSceneRun.scene == "spot_check")
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="抽查记录不存在")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="抽查已复核")
    result = dict(row.result or {})
    result["conclusion"] = conclusion
    result["comment"] = comment
    result["reviewer_id"] = user.id
    row.result = result
    row.body = comment
    row.status = "reviewed"
    row.submitted_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            action="review",
            module="ai",
            target_type="spot_check",
            target_id=str(row.id),
            detail=conclusion,
        )
    )
    db.commit()
    db.refresh(row)
    return call_view(row, detail=True)
