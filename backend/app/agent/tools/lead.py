"""线索只读 / 写操作工具。"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from langchain_core.tools import tool
from sqlalchemy import or_

from app.agent.runtime import require_db, require_user
from app.agent.tools.base import write_operation
from app.models.user import User
from app.schemas.lead import (
    LeadAssignRequest,
    LeadConvertRequest,
    LeadCreate,
    LeadFollowUpCreate,
)
from app.services import lead as lead_service


def _resolve_user_by_name(db, name: str) -> User:
    key = (name or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    user = (
        db.query(User)
        .filter(or_(User.real_name == key, User.username == key))
        .first()
    )
    if not user:
        like = f"%{key}%"
        rows = (
            db.query(User)
            .filter(or_(User.real_name.like(like), User.username.like(like)))
            .limit(5)
            .all()
        )
        if len(rows) == 1:
            return rows[0]
        if not rows:
            raise HTTPException(status_code=404, detail=f"未找到用户：{key}")
        names = "、".join((u.real_name or u.username) for u in rows)
        raise HTTPException(status_code=400, detail=f"匹配到多人，请写全名：{names}")
    return user


def _lead_brief(lead) -> dict:
    return {
        "id": lead.id,
        "name": lead.name,
        "company_name": lead.company_name,
        "status": lead.status,
        "phone": lead.phone,
        "owner": getattr(lead, "owner_name", None),
        "source": getattr(lead, "source", None),
    }


@tool
def list_my_leads(status: Optional[str] = None, keyword: Optional[str] = None) -> list:
    """列出当前用户负责的线索。

    Args:
        status: 可选状态过滤
        keyword: 可选公司名/联系人关键词
    """
    db, user = require_db(), require_user()
    _, items = lead_service.list_leads(
        db,
        user,
        status=(status or "").strip() or None,
        keyword=(keyword or "").strip() or None,
        pool="mine",
        page=1,
        page_size=20,
    )
    return [_lead_brief(x) for x in items]


@tool
def search_leads(keyword: str) -> list:
    """按公司名/联系人/电话搜索线索。"""
    db, user = require_db(), require_user()
    _, items = lead_service.list_leads(
        db, user, keyword=keyword.strip(), page=1, page_size=10
    )
    return [_lead_brief(x) for x in items]


@tool
def get_lead_detail(lead_id: int) -> dict:
    """查询线索详情（状态、跟进、转化结果）。

    Args:
        lead_id: 线索 ID
    """
    db, user = require_db(), require_user()
    try:
        lead = lead_service.get_lead_detail(db, user, lead_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    follow_ups = getattr(lead, "follow_ups", None) or []
    return {
        **_lead_brief(lead),
        "need_desc": getattr(lead, "need_desc", None),
        "region": getattr(lead, "region", None),
        "converted_customer_id": getattr(lead, "converted_customer_id", None),
        "converted_opportunity_id": getattr(lead, "converted_opportunity_id", None),
        "follow_up_count": len(follow_ups),
        "recent_follow_ups": [
            {
                "id": f.id,
                "content": (getattr(f, "content", None) or "")[:200],
                "created_at": str(getattr(f, "created_at", None) or ""),
            }
            for f in follow_ups[:5]
        ],
    }


@write_operation("创建线索", permission="lead:view")
@tool
def create_lead(
    company_name: str,
    phone: str,
    contact_name: Optional[str] = None,
    source: Optional[str] = None,
    need_desc: Optional[str] = None,
) -> dict:
    """新建销售线索（写操作，需要用户确认）。

    Args:
        company_name: 客户主体名称
        phone: 联系电话（必填）
        contact_name: 联系人，可空
        source: 来源编码，默认 manual
        need_desc: 需求说明
    """
    db, user = require_db(), require_user()
    try:
        lead = lead_service.create_lead(
            db,
            user,
            LeadCreate(
                company_name=company_name.strip(),
                phone=phone.strip(),
                name=(contact_name or "").strip() or None,
                source=(source or "manual").strip() or "manual",
                need_desc=(need_desc or "").strip() or None,
            ),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "lead_id": lead.id,
        "company_name": lead.company_name,
        "message": f"已创建线索 {lead.company_name}",
    }


@write_operation("写线索跟进", permission="lead:view")
@tool
def add_lead_follow_up(
    lead_id: int,
    content: str,
    method: str = "phone",
    result: str = "keep",
    customer_feedback: Optional[str] = None,
) -> dict:
    """给线索写一条跟进记录（写操作，需要用户确认）。

    Args:
        lead_id: 线索 ID
        content: 沟通内容
        method: phone/wechat/email/visit/meeting
        result: advance/keep/return/lost
        customer_feedback: 客户反馈，可空
    """
    db, user = require_db(), require_user()
    try:
        fu = lead_service.add_follow_up(
            db,
            user,
            lead_id,
            LeadFollowUpCreate(
                method=(method or "phone").strip() or "phone",
                content=content.strip(),
                result=(result or "keep").strip() or "keep",
                customer_feedback=(customer_feedback or "").strip() or None,
            ),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "follow_up_id": fu.id,
        "lead_id": lead_id,
        "message": "已写入线索跟进",
    }


@write_operation("分配线索", permission="lead:view")
@tool
def assign_lead(lead_id: int, owner_name: str, remark: Optional[str] = None) -> dict:
    """把待分配线索分配给指定同事（写操作，需要用户确认）。

    Args:
        lead_id: 线索 ID
        owner_name: 接收人真实姓名或登录名
        remark: 备注，可空
    """
    db, user = require_db(), require_user()
    try:
        owner = _resolve_user_by_name(db, owner_name)
        lead = lead_service.assign_lead(
            db,
            user,
            lead_id,
            LeadAssignRequest(owner_id=owner.id, remark=(remark or "").strip() or None),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "lead_id": lead.id,
        "owner_id": owner.id,
        "owner_name": owner.real_name or owner.username,
        "message": f"已将线索分配给 {owner.real_name or owner.username}",
    }


@write_operation("线索转客户与商机", permission="lead:view")
@tool
def convert_lead(
    lead_id: int,
    customer_name: Optional[str] = None,
    opportunity_title: Optional[str] = None,
    expected_amount: Optional[float] = None,
    business_type: str = "other",
    requirement_summary: Optional[str] = None,
) -> dict:
    """将线索转化为客户与商机（写操作，需要用户确认）。

    Args:
        lead_id: 线索 ID
        customer_name: 客户名，默认用公司名
        opportunity_title: 商机标题，可空
        expected_amount: 预计金额，可空
        business_type: 业务类型编码
        requirement_summary: 需求与成交依据，可空
    """
    db, user = require_db(), require_user()
    try:
        out = lead_service.convert_lead(
            db,
            user,
            lead_id,
            LeadConvertRequest(
                customer_name=(customer_name or "").strip() or None,
                opportunity_title=(opportunity_title or "").strip() or None,
                expected_amount=Decimal(str(expected_amount)) if expected_amount is not None else None,
                business_type=(business_type or "other").strip() or "other",
                requirement_summary=(requirement_summary or "").strip() or None,
            ),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "lead_id": lead_id,
        "customer_id": out.get("customer_id"),
        "opportunity_id": out.get("opportunity_id"),
        "message": "线索已转化为客户与商机",
    }
