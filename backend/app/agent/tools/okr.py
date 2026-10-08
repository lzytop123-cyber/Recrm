"""OKR 只读 / 写操作工具。"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from langchain_core.tools import tool

from app.agent.runtime import require_db, require_user
from app.agent.tools.base import write_operation
from app.schemas.okr import KeyResultCreate
from app.services import okr as okr_service


@tool
def list_my_okrs(period_label: Optional[str] = None, keyword: Optional[str] = None) -> list:
    """列出当前用户负责或创建的 OKR。

    Args:
        period_label: 可选周期标签，如 2026-Q3、2026
        keyword: 可选，按目标标题关键词过滤
    """
    db, user = require_db(), require_user()
    _, items = okr_service.list_okrs(
        db,
        user,
        period_label=period_label,
        keyword=keyword,
        scope_filter="mine",
        page=1,
        page_size=20,
    )
    return [
        {
            "id": o.id,
            "title": o.title,
            "status": o.status,
            "level": o.level,
            "period_label": o.period_label,
            "progress": getattr(o, "progress", None),
            "owner": getattr(o, "owner_name", None),
            "kr_count": getattr(o, "kr_count", None),
        }
        for o in items
    ]


@tool
def get_okr_detail(okr_id: int) -> dict:
    """查询 OKR 详情，包含关键结果进度。"""
    db, user = require_db(), require_user()
    try:
        o = okr_service.get_okr_detail(db, user, okr_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    krs = []
    for kr in o.key_results or []:
        krs.append(
            {
                "id": kr.id,
                "title": kr.title,
                "progress": getattr(kr, "progress", None),
                "current_value": float(kr.current_value or 0),
                "target_value": float(kr.target_value or 0),
                "unit": kr.unit,
            }
        )
    return {
        "id": o.id,
        "title": o.title,
        "status": o.status,
        "level": o.level,
        "period_label": o.period_label,
        "progress": getattr(o, "progress", None),
        "owner": getattr(o, "owner_name", None),
        "key_results": krs,
    }


@tool
def my_okr_stats(period_label: Optional[str] = None) -> dict:
    """汇总当前用户可见的 OKR 统计（总数、进行中、平均进度等）。"""
    db, user = require_db(), require_user()
    return okr_service.okr_stats(db, user, period_label=period_label)


@write_operation("给 OKR 添加关键结果", permission="okr:view")
@tool
def create_key_result(
    okr_id: int,
    title: str,
    target_value: float = 100.0,
    unit: Optional[str] = "%",
) -> dict:
    """给指定 OKR 添加关键结果 KR（写操作，需要用户确认）。

    Args:
        okr_id: OKR ID
        title: KR 标题
        target_value: 目标值，默认 100
        unit: 单位，默认 %
    """
    db, user = require_db(), require_user()
    try:
        kr = okr_service.add_key_result(
            db,
            user,
            okr_id,
            KeyResultCreate(
                title=title.strip(),
                target_value=Decimal(str(target_value)),
                unit=(unit or "%").strip() or "%",
            ),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "okr_id": okr_id,
        "kr_id": kr.id,
        "title": kr.title,
        "message": f"已添加关键结果 {kr.title}",
    }
