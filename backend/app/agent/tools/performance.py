"""绩效 / KPI 只读与写操作工具。"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from langchain_core.tools import tool

from app.agent.runtime import require_db, require_user
from app.agent.tools.base import write_operation
from app.models.performance import PerformanceCycle
from app.schemas.performance import AppealCreate, ManagerRateRequest, SelfRateRequest
from app.services import performance as perf_svc
from app.services import performance_assessment_batch as batch_svc


def _assessment_brief(row) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "user_name": getattr(row, "user_name", None),
        "period_label": getattr(row, "period_label", None),
        "status": row.status,
        "self_score": row.self_score,
        "leader_score": row.leader_score,
        "final_score": row.final_score,
        "grade": row.grade,
        "cycle_id": row.cycle_id,
        "batch_id": getattr(row, "batch_id", None),
    }


def _item_brief(item) -> dict:
    return {
        "id": item.id,
        "title": getattr(item, "title", None) or getattr(item, "name", None),
        "weight": getattr(item, "weight", None),
        "self_score": getattr(item, "self_score", None),
        "leader_score": getattr(item, "leader_score", None),
        "system_score": getattr(item, "system_score", None),
        "final_score": getattr(item, "final_score", None),
    }


@tool
def list_my_assessments() -> dict:
    """列出当前用户的绩效考核记录与分数趋势。"""
    db, user = require_db(), require_user()
    data = perf_svc.list_my_assessments(db, user)
    assessments = [_assessment_brief(a) for a in (data.get("assessments") or [])]
    return {
        "count": len(assessments),
        "assessments": assessments[:20],
        "trend": (data.get("trend") or [])[-12:],
    }


@tool
def list_team_assessments(
    scope: str = "direct",
    period_label: Optional[str] = None,
) -> dict:
    """列出下属团队的绩效考核（主管视角）。

    Args:
        scope: direct=直属下属，all=递归下属
        period_label: 可选周期，如 2026-08、2026-Q3
    """
    db, user = require_db(), require_user()
    scope_norm = (scope or "direct").strip().lower()
    if scope_norm not in {"direct", "all"}:
        scope_norm = "direct"
    rows = perf_svc.list_team_assessments(
        db,
        user,
        scope=scope_norm,
        period_label=(period_label or "").strip() or None,
    )
    items = [_assessment_brief(r) for r in rows[:50]]
    pending = [x for x in items if x.get("status") not in {"completed", "archived", "confirmed"}]
    return {
        "scope": scope_norm,
        "period_label": period_label,
        "count": len(items),
        "pending_count": len(pending),
        "assessments": items,
    }


@tool
def get_assessment_detail(assessment_id: int) -> dict:
    """查询单条绩效考核详情（分数、等级、指标项）。

    Args:
        assessment_id: 考核记录 ID
    """
    db, user = require_db(), require_user()
    try:
        row = perf_svc.get_assessment_detail(db, user, assessment_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    out = _assessment_brief(row)
    items = getattr(row, "items", None) or []
    out["items"] = [_item_brief(i) for i in items[:40]]
    out["timeline_count"] = len(getattr(row, "timeline", None) or [])
    return out


@tool
def get_cycle_launch_progress(
    cycle_id: Optional[int] = None,
    period_label: Optional[str] = None,
) -> dict:
    """查询某考核周期的多部门发起进度看板（批次/部门完成情况）。

    Args:
        cycle_id: 考核周期 ID（优先）
        period_label: 周期标签，如 2026-08；未传 cycle_id 时按此查找
    """
    db, user = require_db(), require_user()
    _ = user
    cid = cycle_id
    if not cid:
        label = (period_label or "").strip()
        if not label:
            return {"error": "请提供 cycle_id 或 period_label", "status_code": 400}
        cycle = (
            db.query(PerformanceCycle)
            .filter(PerformanceCycle.period_label == label)
            .order_by(PerformanceCycle.id.desc())
            .first()
        )
        if not cycle:
            return {"error": f"未找到周期 {label}", "status_code": 404}
        cid = cycle.id
    try:
        board = batch_svc.list_cycle_batch_progress(db, cid)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    # 压缩返回，避免 token 过大
    departments = []
    for d in board.get("departments") or []:
        departments.append(
            {
                "department_id": d.get("department_id"),
                "department_name": d.get("department_name"),
                "template_names": d.get("template_names") or [],
                "total": d.get("total"),
                "pending_employee": d.get("pending_employee"),
                "pending_manager": d.get("pending_manager"),
                "pending_hr_review": d.get("pending_hr_review"),
                "pending_confirm": d.get("pending_confirm"),
                "appealing": d.get("appealing"),
                "completed": d.get("completed"),
            }
        )
    return {
        "cycle_id": board.get("cycle_id"),
        "period_label": board.get("period_label"),
        "totals": board.get("totals"),
        "departments": departments,
        "batch_count": len(board.get("batches") or []),
    }


@write_operation("提交绩效自评", permission="okr:view")
@tool
def submit_self_rate(assessment_id: int, self_score: int) -> dict:
    """提交本人绩效考核自评分数（写操作，需要用户确认）。

    Args:
        assessment_id: 考核记录 ID
        self_score: 自评总分 0-100
    """
    db, user = require_db(), require_user()
    try:
        row = perf_svc.rate_self(
            db, user, assessment_id, SelfRateRequest(self_score=self_score)
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "assessment_id": row.id,
        "self_score": row.self_score,
        "flow_status": row.status,
        "message": f"已提交自评 {row.self_score} 分",
    }


@write_operation("提交主管绩效评价", permission="okr:view")
@tool
def submit_manager_rate(
    assessment_id: int,
    okr_score: int,
    kpi_score: int,
    behavior_score: int,
    comment: str,
) -> dict:
    """提交对下属的主管评价（写操作，需要用户确认）。

    Args:
        assessment_id: 考核记录 ID
        okr_score: OKR 分 0-100
        kpi_score: KPI 分 0-100
        behavior_score: 行为分 0-100
        comment: 主管评语（必填）
    """
    db, user = require_db(), require_user()
    try:
        row = perf_svc.rate_manager(
            db,
            user,
            assessment_id,
            ManagerRateRequest(
                okr_score=okr_score,
                kpi_score=kpi_score,
                behavior_score=behavior_score,
                comment=comment.strip(),
            ),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "assessment_id": row.id,
        "leader_score": row.leader_score,
        "final_score": row.final_score,
        "flow_status": row.status,
        "message": "已提交主管评价",
    }


@write_operation("发起绩效申诉", permission="okr:view")
@tool
def create_performance_appeal(
    assessment_id: int,
    reason: str,
    request_score: int,
) -> dict:
    """对考核结果发起申诉（写操作，需要用户确认）。

    Args:
        assessment_id: 考核记录 ID
        reason: 申诉理由
        request_score: 期望分数 0-100
    """
    db, user = require_db(), require_user()
    try:
        appeal = perf_svc.create_appeal(
            db,
            user,
            assessment_id,
            AppealCreate(reason=reason.strip(), request_score=request_score),
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "appeal_id": appeal.id,
        "assessment_id": assessment_id,
        "request_score": appeal.request_score,
        "message": "已发起绩效申诉",
    }
