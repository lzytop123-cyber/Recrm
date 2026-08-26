"""飞书审批通知：待办激活 / 催办 / 终审结果 → 私聊文本（同步发送，失败不阻断业务）。"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.approval_flow import TASK_ACTIVE, ApprovalInstance
from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)

REMIND_COOLDOWN = timedelta(minutes=30)


def _settings(settings: Settings | None = None) -> Settings:
    return settings or get_settings()


def notify_ready(settings: Settings | None = None) -> bool:
    return _settings(settings).feishu_notify_ready


def _tenant_access_token(settings: Settings) -> str:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    body = {"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret}
    with httpx.Client(timeout=15.0) as client:
        data = client.post(url, json=body).json()
    if data.get("code", 0) != 0 or not data.get("tenant_access_token"):
        raise RuntimeError(data.get("msg") or "获取 tenant_access_token 失败")
    return str(data["tenant_access_token"])


def send_text_to_open_id(
    open_id: str,
    text: str,
    *,
    settings: Settings | None = None,
) -> bool:
    """同步发送文本私聊。未配置/关闭通知时返回 False，不抛错。"""
    cfg = _settings(settings)
    if not cfg.feishu_notify_ready or not open_id or not text.strip():
        return False
    try:
        token = _tenant_access_token(cfg)
        content = json.dumps({"text": text.strip()}, ensure_ascii=False)
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                params={"receive_id_type": "open_id"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json={
                    "receive_id": open_id,
                    "msg_type": "text",
                    "content": content,
                },
            )
            data = resp.json()
        if data.get("code", 0) != 0:
            logger.warning("飞书发消息失败 open_id=%s msg=%s", open_id, data.get("msg"))
            return False
        return True
    except Exception:
        logger.exception("飞书发消息异常 open_id=%s", open_id)
        return False


def approval_center_url(instance: ApprovalInstance, *, settings: Settings | None = None) -> str:
    cfg = _settings(settings)
    base = (cfg.app_public_url or "").rstrip("/")
    item_id = f"approval_instance:{instance.id}"
    if not base:
        return f"/approvals?id={item_id}"
    return f"{base}/approvals?id={item_id}"


def _open_ids_for_users(db: Session, user_ids: Iterable[int]) -> list[tuple[int, str]]:
    ids = {int(x) for x in user_ids if x}
    if not ids:
        return []
    rows = (
        db.query(User.id, User.feishu_open_id)
        .filter(User.id.in_(ids), User.is_active.is_(True), User.feishu_open_id.isnot(None))
        .all()
    )
    return [(int(r[0]), str(r[1])) for r in rows if r[1]]


def _active_candidate_ids(db: Session, instance: ApprovalInstance) -> set[int]:
    from app.services import approval_flow

    out: set[int] = set()
    for t in instance.tasks:
        if t.status != TASK_ACTIVE:
            continue
        ids, resolution = approval_flow._resolve_task_candidates(db, instance, t)
        if resolution == "ok":
            out |= set(ids)
    return out


def _pending_message(instance: ApprovalInstance, *, remind: bool = False) -> str:
    node = ""
    active = [t for t in instance.tasks if t.status == TASK_ACTIVE]
    if active:
        names = sorted({t.name for t in active if t.name})
        node = "、".join(names)
    kind = "审批催办" if remind else "审批待办"
    lines = [
        f"【{kind}】{instance.title}",
        f"单号：{instance.code}",
        f"发起人：{instance.initiator_name or '—'}",
    ]
    if node:
        lines.append(f"当前节点：{node}")
    if instance.summary:
        lines.append(f"摘要：{instance.summary[:80]}")
    lines.append(f"请到审批中心处理：{approval_center_url(instance)}")
    return "\n".join(lines)


def notify_active_approvers(
    db: Session,
    instance: ApprovalInstance,
    *,
    remind: bool = False,
    exclude_user_ids: Optional[set[int]] = None,
) -> int:
    """向当前 active 节点候选人发飞书私聊。返回成功发送人数。失败静默。"""
    if not notify_ready():
        return 0
    candidate_ids = _active_candidate_ids(db, instance)
    if exclude_user_ids:
        candidate_ids -= exclude_user_ids
    sent = 0
    text = _pending_message(instance, remind=remind)
    for _uid, open_id in _open_ids_for_users(db, candidate_ids):
        if send_text_to_open_id(open_id, text):
            sent += 1
    return sent


def _result_message(instance: ApprovalInstance, *, approved: bool) -> str:
    kind = "审批已通过" if approved else "审批已驳回"
    lines = [
        f"【{kind}】{instance.title}",
        f"单号：{instance.code}",
    ]
    if not approved and instance.reject_reason:
        lines.append(f"驳回原因：{instance.reject_reason[:120]}")
    if instance.summary:
        lines.append(f"摘要：{instance.summary[:80]}")
    lines.append(f"查看详情：{approval_center_url(instance)}")
    return "\n".join(lines)


def notify_initiator_result(
    db: Session,
    instance: ApprovalInstance,
    *,
    approved: bool,
) -> int:
    """终审通过/驳回后通知发起人。返回成功发送人数（0 或 1）。失败静默。"""
    if not notify_ready() or not instance.initiator_id:
        return 0
    pairs = _open_ids_for_users(db, [instance.initiator_id])
    if not pairs:
        return 0
    text = _result_message(instance, approved=approved)
    _uid, open_id = pairs[0]
    return 1 if send_text_to_open_id(open_id, text) else 0


def _recent_remind_exists(db: Session, instance: ApprovalInstance) -> bool:
    since = datetime.now(timezone.utc) - REMIND_COOLDOWN
    q = (
        db.query(AuditLog.id)
        .filter(
            AuditLog.module == "approval",
            AuditLog.action == "approval_flow_remind",
            AuditLog.target_id == str(instance.id),
            AuditLog.created_at >= since,
        )
        .limit(1)
    )
    return q.first() is not None


def remind_approvers(
    db: Session,
    user: User,
    instance: ApprovalInstance,
    *,
    commit: bool = True,
) -> int:
    """催办当前节点审批人（30 分钟内限一次）。返回发送成功人数。"""
    from app.services import approval_flow
    from app.models.approval_flow import INSTANCE_OPEN_STATUSES

    if instance.status not in INSTANCE_OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="该审批单已结束，无法催办")
    if instance.initiator_id != user.id and not approval_flow._is_flow_superuser(user):
        raise HTTPException(status_code=403, detail="仅发起人或系统管理员可催办")
    if _recent_remind_exists(db, instance):
        raise HTTPException(status_code=429, detail="30 分钟内已催办过，请稍后再试")

    sent = notify_active_approvers(db, instance, remind=True, exclude_user_ids={user.id})
    approval_flow._audit(
        db,
        user,
        instance,
        action="remind",
        detail=f"催办已发送 {sent} 人" if sent else "催办已记录（无可达飞书账号）",
    )
    if commit:
        db.commit()
    return sent
