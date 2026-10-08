"""S3 销售跟进摘要：只读跟进记录，不落业务动作。"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from langchain_core.tools import tool

from app.agent.runtime import require_db, require_user
from app.services import customer as customer_service
from app.services import lead as lead_service
from app.services import opportunity as opportunity_service


def _iso(value) -> Optional[str]:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


@tool
def get_followup_records(
    lead_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
) -> dict:
    """读取线索/客户/商机的跟进与沟通记录，供摘要和下一步建议。
    只返回已有记录。建议仅作提示，禁止改状态、写跟进、创建任务。
    用户说「跟进摘要/沟通要点/下一步」且当前在线索、客户或商机页时用此工具。

    Args:
        lead_id: 线索 ID
        customer_id: 客户 ID
        opportunity_id: 商机 ID
    """
    if not any((lead_id, customer_id, opportunity_id)):
        return {"error": "请提供 lead_id、customer_id 或 opportunity_id"}
    db, user = require_db(), require_user()
    out: dict = {
        "records": [],
        "rule": "只做摘要和建议，不要执行任何写操作或业务动作。",
    }
    try:
        if lead_id:
            lead = lead_service.get_lead_detail(db, user, lead_id)
            out["lead"] = {
                "id": lead.id,
                "name": lead.name,
                "company": lead.company_name,
                "status": lead.status,
                "need": (lead.need_desc or "")[:200],
            }
            for fu in (lead.follow_ups or [])[:20]:
                out["records"].append(
                    {
                        "source": "lead",
                        "at": _iso(fu.follow_at),
                        "method": fu.method,
                        "content": fu.content,
                        "feedback": fu.customer_feedback,
                        "result": fu.result,
                        "next_follow_at": _iso(fu.next_follow_at),
                    }
                )
        if customer_id:
            customer = customer_service.get_customer_detail(db, user, customer_id)
            out["customer"] = {
                "id": customer.id,
                "name": customer.name,
                "status": customer.status,
                "owner": getattr(customer, "owner_name", None),
            }
            for fu in (customer.follow_ups or [])[:20]:
                out["records"].append(
                    {
                        "source": "customer",
                        "at": _iso(fu.follow_at),
                        "method": fu.method,
                        "content": fu.content,
                        "next_follow_at": _iso(fu.next_follow_at),
                    }
                )
        if opportunity_id:
            opp = opportunity_service.get_opportunity_detail(db, user, opportunity_id)
            out["opportunity"] = {
                "id": opp.id,
                "title": opp.title,
                "stage": opp.stage,
                "expected_amount": float(opp.expected_amount or 0),
                "next_action_note": opp.next_action_note,
                "next_action_at": _iso(opp.next_action_at),
            }
            for act in (opp.activities or [])[:20]:
                out["records"].append(
                    {
                        "source": "opportunity",
                        "at": _iso(act.created_at),
                        "type": act.activity_type,
                        "content": act.content,
                        "evidence": act.evidence,
                        "next_action_at": _iso(act.next_action_at),
                    }
                )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return out
