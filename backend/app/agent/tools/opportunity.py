"""商机只读 / 写操作工具。"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from langchain_core.tools import tool

from app.agent.runtime import require_db, require_user
from app.agent.tools.base import write_operation
from app.schemas.opportunity import (
    OpportunityActivityCreate,
    OpportunityCreate,
    OpportunityStageChange,
)
from app.services import opportunity as opp_service


def _opp_brief(o) -> dict:
    amount = getattr(o, "expected_amount", None)
    try:
        amount_f = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount_f = None
    return {
        "id": o.id,
        "title": o.title,
        "stage": o.stage,
        "expected_amount": amount_f,
        "owner": getattr(o, "owner_name", None),
        "customer_id": getattr(o, "customer_id", None),
        "customer_name": getattr(o, "customer_name", None),
        "opportunity_no": getattr(o, "opportunity_no", None),
    }


@tool
def list_my_opportunities(
    stage: Optional[str] = None,
    keyword: Optional[str] = None,
) -> list:
    """列出当前用户负责的商机。

    Args:
        stage: 可选阶段过滤
        keyword: 可选标题/编号关键词
    """
    db, user = require_db(), require_user()
    _, items = opp_service.list_opportunities(
        db,
        user,
        stage=(stage or "").strip() or None,
        keyword=(keyword or "").strip() or None,
        scope_filter="mine",
        page=1,
        page_size=20,
    )
    return [_opp_brief(o) for o in items]


@tool
def search_opportunities(keyword: str) -> list:
    """按标题/编号搜索商机。"""
    db, user = require_db(), require_user()
    _, items = opp_service.list_opportunities(
        db, user, keyword=keyword.strip(), page=1, page_size=10
    )
    return [_opp_brief(o) for o in items]


@tool
def get_opportunity_detail(opportunity_id: int) -> dict:
    """查询商机详情（阶段、金额、近期活动摘要）。

    Args:
        opportunity_id: 商机 ID
    """
    db, user = require_db(), require_user()
    try:
        o = opp_service.get_opportunity_detail(db, user, opportunity_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    out = _opp_brief(o)
    out["requirement_summary"] = getattr(o, "requirement_summary", None)
    activities = getattr(o, "activities", None) or []
    out["recent_activities"] = [
        {
            "id": a.id,
            "content": (getattr(a, "content", None) or "")[:200],
            "user_name": getattr(a, "user_name", None),
            "created_at": str(getattr(a, "created_at", None) or ""),
        }
        for a in activities[:8]
    ]
    out["linked_contract_id"] = getattr(o, "linked_contract_id", None)
    return out


@write_operation("新建商机", permission="opportunity:view")
@tool
def create_opportunity(
    title: str,
    customer_id: int,
    requirement_summary: str,
    expected_amount: Optional[float] = None,
    business_type: str = "other",
    stage: str = "need_confirm",
) -> dict:
    """新建商机（写操作，需要用户确认）。

    Args:
        title: 商机标题
        customer_id: 客户 ID
        requirement_summary: 需求与成交依据（必填）
        expected_amount: 预计金额
        business_type: 业务类型
        stage: 初始阶段，默认 need_confirm
    """
    db, user = require_db(), require_user()
    try:
        o = opp_service.create_opportunity(
            db,
            user,
            OpportunityCreate(
                title=title.strip(),
                customer_id=customer_id,
                requirement_summary=requirement_summary.strip(),
                expected_amount=Decimal(str(expected_amount)) if expected_amount is not None else None,
                business_type=(business_type or "other").strip() or "other",
                stage=(stage or "need_confirm").strip() or "need_confirm",
            ),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "opportunity_id": o.id,
        "title": o.title,
        "stage": o.stage,
        "message": f"已创建商机 {o.title}",
    }


@write_operation("推进商机阶段", permission="opportunity:view")
@tool
def change_opportunity_stage(
    opportunity_id: int,
    stage: str,
    evidence: str,
    lost_reason: Optional[str] = None,
) -> dict:
    """变更商机阶段（写操作，需要用户确认）。阶段变更必须写依据。

    Args:
        opportunity_id: 商机 ID
        stage: 目标阶段 contact/need_confirm/proposal/negotiation/won/lost/paused
        evidence: 变更依据（必填）
        lost_reason: 输单原因（stage=lost 时必填）
    """
    db, user = require_db(), require_user()
    try:
        o = opp_service.change_stage(
            db,
            user,
            opportunity_id,
            OpportunityStageChange(
                stage=stage.strip(),
                evidence=evidence.strip(),
                lost_reason=(lost_reason or "").strip() or None,
            ),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "opportunity_id": o.id,
        "stage": o.stage,
        "message": f"商机已推进到 {o.stage}",
    }


@write_operation("写商机跟进", permission="opportunity:view")
@tool
def add_opportunity_activity(
    opportunity_id: int,
    content: str,
    evidence: Optional[str] = None,
    next_action_note: Optional[str] = None,
) -> dict:
    """给商机写一条跟进/活动记录（写操作，需要用户确认）。

    Args:
        opportunity_id: 商机 ID
        content: 跟进内容
        evidence: 依据，可空
        next_action_note: 下一步动作备注，可空
    """
    db, user = require_db(), require_user()
    try:
        act = opp_service.add_activity(
            db,
            user,
            opportunity_id,
            OpportunityActivityCreate(
                content=content.strip(),
                evidence=(evidence or "").strip() or None,
                next_action_note=(next_action_note or "").strip() or None,
            ),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "activity_id": act.id,
        "opportunity_id": opportunity_id,
        "message": "已写入商机跟进",
    }
