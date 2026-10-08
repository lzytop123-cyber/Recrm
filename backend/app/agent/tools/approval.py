"""审批相关工具。"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from langchain_core.tools import tool

from app.agent.runtime import require_db, require_user
from app.agent.tools.base import write_operation
from app.schemas.approval import ApprovalActRequest
from app.services import approval as approval_service


def _item_brief(item) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "type": item.type,
        "category": item.category,
        "status": item.status,
        "status_label": item.status_label,
        "node": item.node,
        "applicant": item.applicant_name,
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "summary": (item.summary or "")[:200],
        "can_act": item.can_act,
        "actions": item.actions,
    }


@tool
def list_my_pending_approvals(limit: int = 20) -> list:
    """列出当前用户待办审批任务。用户说"我的审批/待办审批/这周审批"时用此工具。"""
    db, user = require_db(), require_user()
    items = approval_service.list_pending_approvals(db, user, limit=max(1, min(limit, 50)))
    return [_item_brief(x) for x in items]


@tool
def get_approval_status(approval_id: str) -> dict:
    """查询审批单详情与当前进度。

    Args:
        approval_id: 审批单 ID（如 flow:12 或列表返回的 id）
    """
    db, user = require_db(), require_user()
    try:
        detail = approval_service.get_approval(db, user, approval_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    data = _item_brief(detail)
    data["timeline"] = [
        {
            "name": n.name,
            "status": n.status,
            "actor": n.actor_name,
            "comment": n.comment,
            "acted_at": n.acted_at.isoformat() if n.acted_at else None,
        }
        for n in (detail.timeline or detail.nodes or [])[:20]
    ]
    return data


@tool
def precheck_approval(approval_id: str) -> dict:
    """审批预审：返回本单摘要、可核对事实、同类已办参考。只出报告，不要通过或驳回。
    用户说「预审/帮我看看这单审批/有没有风险」时用此工具。

    Args:
        approval_id: 审批单 ID（如 flow:12 或列表返回的 id）
    """
    db, user = require_db(), require_user()
    try:
        detail = approval_service.get_approval(db, user, approval_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}

    facts = []
    for f in getattr(detail, "facts", None) or []:
        facts.append(
            {
                "label": getattr(f, "label", None),
                "value": getattr(f, "value", None),
            }
        )
    timeline = [
        {
            "name": n.name,
            "status": n.status,
            "actor": n.actor_name,
            "comment": n.comment,
        }
        for n in (detail.timeline or detail.nodes or [])[:20]
    ]
    risks: list[str] = []
    if not (detail.summary or "").strip():
        risks.append("申请摘要为空")
    if detail.can_act:
        risks.append("当前用户可操作；预审不能代替人工审批")
    if any((n.get("status") or "") == "rejected" for n in timeline):
        risks.append("流程中已有驳回记录")

    similar = []
    for tab in ("processed", "initiated"):
        listed = approval_service.list_approvals(db, user, tab=tab, page=1, page_size=20)
        for item in listed.items:
            if item.id == detail.id:
                continue
            if item.category != detail.category and item.type != detail.type:
                continue
            similar.append(
                {
                    "id": item.id,
                    "title": item.title,
                    "status": item.status,
                    "status_label": item.status_label,
                    "summary": (item.summary or "")[:200],
                }
            )
            if len(similar) >= 5:
                break
        if len(similar) >= 5:
            break

    return {
        "approval": {
            "id": detail.id,
            "title": detail.title,
            "type": detail.type,
            "category": detail.category,
            "status": detail.status,
            "status_label": detail.status_label,
            "applicant": detail.applicant_name,
            "summary": detail.summary,
            "node": detail.node,
            "submitted_at": detail.submitted_at.isoformat() if detail.submitted_at else None,
            "rule_version": getattr(detail, "rule_version", None),
        },
        "facts": facts,
        "timeline": timeline,
        "risks": risks,
        "similar": similar,
        "rule": "只出预审报告，不要通过或驳回。风险只能引用 risks/facts/similar。",
    }


@write_operation("审批通过或驳回", permission="approval:center")
@tool
def act_on_approval(approval_id: str, action: str, comment: Optional[str] = None) -> dict:
    """对待办审批执行通过或驳回（写操作，需要用户确认）。

    Args:
        approval_id: 审批单 ID
        action: approve（通过）或 reject（驳回）
        comment: 可选意见；驳回时建议填写原因
    """
    db, user = require_db(), require_user()
    action = (action or "").strip().lower()
    if action not in {"approve", "reject"}:
        return {"error": "action 仅支持 approve 或 reject"}
    try:
        result = approval_service.act_approval(
            db,
            user,
            approval_id,
            action,
            ApprovalActRequest(comment=comment, reason=comment),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "ok": result.ok,
        "message": result.message,
        "approval_id": result.approval_id,
        "action": result.action,
    }
