"""工单查询 + 方案推荐。"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import HTTPException
from langchain_core.tools import tool

from app.agent.runtime import require_db, require_user
from app.core.rbac import user_can
from app.schemas.knowledge import KnowledgeAskRequest
from app.services import knowledge as knowledge_service
from app.services import ticket as ticket_service


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]{2,}", (text or "").lower()))


def _ticket_brief(t) -> dict:
    return {
        "id": t.id,
        "ticket_no": t.ticket_no,
        "title": t.title,
        "status": t.status,
        "ticket_type": getattr(t, "ticket_type", None),
        "priority": getattr(t, "priority", None),
        "assignee": getattr(t, "assignee_name", None),
        "creator": getattr(t, "creator_name", None),
    }


@tool
def list_my_tickets(
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    scope: str = "mine",
) -> list:
    """列出与我相关的工单。

    Args:
        status: 可选状态过滤
        keyword: 标题/编号关键词
        scope: mine=我创建或处理；mine_assigned=我负责；mine_created=我创建
    """
    db, user = require_db(), require_user()
    scope_norm = (scope or "mine").strip() or "mine"
    if scope_norm not in {"mine", "mine_assigned", "mine_created"}:
        scope_norm = "mine"
    _, items = ticket_service.list_tickets(
        db,
        user,
        status=(status or "").strip() or None,
        keyword=(keyword or "").strip() or None,
        scope_filter=scope_norm,
        page=1,
        page_size=20,
    )
    return [_ticket_brief(t) for t in items]


@tool
def get_ticket_detail(ticket_id: int) -> dict:
    """查询工单详情（状态、内容、处理结果摘要）。

    Args:
        ticket_id: 工单 ID
    """
    db, user = require_db(), require_user()
    try:
        t = ticket_service.get_ticket(db, user, ticket_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    out = _ticket_brief(t)
    out["content"] = (getattr(t, "content", None) or "")[:800]
    out["result"] = getattr(t, "result", None)
    records = getattr(t, "records", None) or []
    out["recent_records"] = [
        {
            "action": getattr(r, "action", None),
            "content": (getattr(r, "content", None) or "")[:200],
            "created_at": str(getattr(r, "created_at", None) or ""),
        }
        for r in list(records)[-8:]
    ]
    return out


@tool
def recommend_ticket_solutions(ticket_id: int) -> dict:
    """处理工单时检索相似历史工单和已发布知识方案。必须带来源。
    没有相似工单且知识未命中时明确说没有依据，禁止编造处理步骤。
    用户说「这单怎么处理/工单方案/相似工单」时用此工具。

    Args:
        ticket_id: 工单 ID
    """
    db, user = require_db(), require_user()
    try:
        ticket = ticket_service.get_ticket(db, user, ticket_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}

    blob = f"{ticket.title} {ticket.content or ''}"
    tokens = _tokens(blob)
    _, items = ticket_service.list_tickets(db, user, page=1, page_size=50)
    scored: list[tuple[int, object]] = []
    for other in items:
        if other.id == ticket.id:
            continue
        overlap = len(tokens & _tokens(f"{other.title} {other.content or ''}"))
        if other.ticket_type == ticket.ticket_type:
            overlap += 1
        if overlap <= 0:
            continue
        scored.append((overlap, other))
    scored.sort(key=lambda x: (-x[0], -x[1].id))
    similar = []
    for score, other in scored[:5]:
        similar.append(
            {
                "id": other.id,
                "ticket_no": other.ticket_no,
                "title": other.title,
                "status": other.status,
                "result": (other.result or "")[:300],
                "score": score,
            }
        )

    knowledge = {"found": False, "citations": []}
    if user_can(user, "knowledge:view"):
        question = (ticket.title or "").strip() or "工单处理"
        asked = knowledge_service.ask(db, user, KnowledgeAskRequest(question=question[:500]))
        citations = asked.get("citations") or []
        knowledge = {
            "found": int(asked.get("matched_count") or 0) > 0,
            "ask_id": asked.get("ask_id"),
            "citations": [
                {
                    "title": c.get("title"),
                    "source": c.get("source_label"),
                    "version": c.get("version"),
                    "snippet": c.get("snippet"),
                    "source_url": c.get("source_url"),
                }
                for c in citations
            ],
        }

    return {
        "ticket": {
            "id": ticket.id,
            "ticket_no": ticket.ticket_no,
            "title": ticket.title,
            "content": (ticket.content or "")[:500],
            "status": ticket.status,
            "ticket_type": ticket.ticket_type,
            "result": ticket.result,
        },
        "similar_tickets": similar,
        "knowledge": knowledge,
        "rule": "推荐必须带来源（工单编号或知识标题+版本）。两边都空时明确说没有依据。",
    }
