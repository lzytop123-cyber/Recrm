"""客户相关只读 / 写操作工具。"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from langchain_core.tools import tool

from app.agent.runtime import require_db, require_user
from app.agent.tools.base import write_operation
from app.schemas.customer import CustomerCreate
from app.services import customer as customer_service


@tool
def list_my_customers(keyword: Optional[str] = None) -> list:
    """列出当前用户负责的客户；可按关键词过滤。"""
    db, user = require_db(), require_user()
    _, items = customer_service.list_customers(
        db, user, keyword=keyword, scope_filter="mine", page=1, page_size=20
    )
    return [
        {
            "id": c.id,
            "name": c.name,
            "status": c.status,
            "owner": getattr(c, "owner_name", None),
            "industry": getattr(c, "industry", None),
        }
        for c in items
    ]


@tool
def search_customers(keyword: str) -> list:
    """按名称/关键词搜索客户。"""
    db, user = require_db(), require_user()
    _, items = customer_service.list_customers(
        db, user, keyword=keyword, page=1, page_size=10
    )
    return [{"id": c.id, "name": c.name, "status": c.status} for c in items]


@tool
def get_customer_detail(customer_id: int) -> dict:
    """查询客户详情（基本信息、跟进、关联商机摘要）。"""
    db, user = require_db(), require_user()
    try:
        c = customer_service.get_customer_detail(db, user, customer_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    opps = getattr(c, "opportunities", None) or []
    return {
        "id": c.id,
        "name": c.name,
        "status": c.status,
        "owner": getattr(c, "owner_name", None),
        "industry": getattr(c, "industry", None),
        "phone": getattr(c, "phone", None),
        "follow_up_count": len(getattr(c, "follow_ups", None) or []),
        "opportunities": [
            {
                "id": o.get("id"),
                "title": o.get("title"),
                "stage": o.get("stage"),
                "expected_amount": o.get("expected_amount"),
            }
            for o in opps[:10]
        ],
    }


@write_operation("新建客户", permission="customer:view")
@tool
def create_customer(
    name: str,
    industry: Optional[str] = None,
    contact_phone: Optional[str] = None,
    contact_name: Optional[str] = None,
) -> dict:
    """新建客户（写操作，需要用户确认）。

    Args:
        name: 客户名称
        industry: 行业，可空
        contact_phone: 联系电话，可空
        contact_name: 联系人，可空
    """
    db, user = require_db(), require_user()
    try:
        c = customer_service.create_customer(
            db,
            user,
            CustomerCreate(
                name=name.strip(),
                industry=(industry or "").strip() or None,
                phone=(contact_phone or "").strip() or None,
                contact_name=(contact_name or "").strip() or None,
            ),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "customer_id": c.id,
        "name": c.name,
        "message": f"已创建客户 {c.name}",
    }
