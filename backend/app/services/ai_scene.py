"""S2–S5 场景接口：复用已有取数工具，只拼系统事实，不调 LLM。"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agent.runtime import agent_runtime
from app.agent.tools.approval import precheck_approval
from app.agent.tools.followup import get_followup_records
from app.agent.tools.ticket import recommend_ticket_solutions
from app.agent.tools.work_report import get_work_report_facts
from app.core.rbac import user_can
from app.models.agent import AiSceneRun
from app.models.approval_flow import ApprovalInstance
from app.models.user import User
from app.services import ai_admin
from app.services.approval_flow import ITEM_PREFIX

# ponytail: 不调模型，避免日报/摘要编造。要润色再接 get_llm，并单独记 token。
MODEL_VERSION = "facts-v1"
_INFO_RISK = "不能代替人工审批"


def _call(db: Session, user: User, tool, args: dict) -> dict:
    with agent_runtime(db, user):
        data = tool.invoke(args)
    if isinstance(data, dict) and data.get("error"):
        raise HTTPException(status_code=int(data.get("status_code") or 400), detail=data["error"])
    return data


def _prepare(db: Session, user: User, scene: str) -> None:
    ai_admin.assert_budget(db, user)
    if not ai_admin.scene_enabled(db, scene):
        raise HTTPException(status_code=409, detail="场景已停用")


def _save(
    db: Session,
    user: User,
    *,
    scene: str,
    result: dict,
    status: str = "done",
    target_id: Optional[str] = None,
    elapsed_ms: int = 0,
) -> AiSceneRun:
    row = AiSceneRun(
        user_id=user.id,
        scene=scene,
        status=status,
        target_id=target_id,
        result=result,
        model_version=ai_admin.published_model_version(db, scene),
        tokens=0,
        elapsed_ms=elapsed_ms,
        cost=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _stamp(row: AiSceneRun, payload: dict) -> dict:
    out = dict(payload)
    out["id"] = row.id
    out["model_version"] = row.model_version
    out["tokens"] = int(row.tokens or 0)
    out["elapsed_ms"] = int(row.elapsed_ms or 0)
    out["cost"] = float(row.cost or 0)
    out["created_at"] = row.created_at.isoformat() if row.created_at else None
    return out


def _timed(db: Session, user: User, tool, args: dict) -> tuple[dict, int]:
    started = time.perf_counter()
    data = _call(db, user, tool, args)
    return data, int((time.perf_counter() - started) * 1000)


def _lines(facts: dict) -> dict:
    today = []
    outputs = []
    for ts in facts.get("timesheets") or []:
        content = (ts.get("content") or "").strip()
        today.append(
            " ".join(
                x
                for x in (
                    str(ts.get("date") or ""),
                    f"{ts.get('hours')}h" if ts.get("hours") is not None else "",
                    ts.get("project") or "",
                    content,
                )
                if x
            )
        )
        if content:
            outputs.append(content)
    for task in facts.get("tasks_done") or []:
        title = (task.get("title") or "").strip()
        if title:
            today.append(f"完成任务：{title}")
    tomorrow = []
    for task in facts.get("tasks_open") or []:
        title = (task.get("title") or "").strip()
        if title:
            tomorrow.append(title)
    for todo in facts.get("todos") or []:
        title = (todo.get("title") or "").strip()
        if title and title not in tomorrow:
            tomorrow.append(title)
    milestones = []
    for ms in facts.get("milestones") or []:
        name = (ms.get("name") or "").strip()
        if name:
            milestones.append(f"{name}（{ms.get('status') or ''}）")
    return {
        "period": facts.get("period"),
        "date_from": facts.get("date_from"),
        "date_to": facts.get("date_to"),
        "today_work": today,
        "tomorrow_plan": tomorrow,
        "outputs": outputs,
        "hours_total": facts.get("hours_total") or 0,
        "milestones": milestones,
        "facts": facts,
        "rule": "草稿只含系统事实。确认前不会提交。",
    }


def create_daily_report(
    db: Session, user: User, *, work_date: Optional[str] = None, week: Optional[str] = None
) -> dict:
    _prepare(db, user, "daily_report")
    period = "week" if (week or "").strip() else "today"
    day = (week or work_date or "").strip() or None
    facts, elapsed = _timed(db, user, get_work_report_facts, {"period": period, "work_date": day})
    draft = _lines(facts)
    row = _save(
        db, user, scene="daily_report", result=draft, status="draft", target_id=draft.get("date_from"), elapsed_ms=elapsed
    )
    return _stamp(row, {**draft, "status": "draft"})


def submit_daily_report(db: Session, user: User, run_id: int, body: str) -> dict:
    text = (body or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请确认正文后再提交")
    row = (
        db.query(AiSceneRun)
        .filter(AiSceneRun.id == run_id, AiSceneRun.user_id == user.id, AiSceneRun.scene == "daily_report")
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="日报草稿不存在")
    if row.status != "draft":
        raise HTTPException(status_code=409, detail="日报已提交")
    row.body = text
    row.status = "submitted"
    row.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "status": row.status,
        "body": row.body,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
    }


def followup_summary(
    db: Session,
    user: User,
    *,
    lead_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
) -> dict:
    _prepare(db, user, "followup_summary")
    data, elapsed = _timed(
        db,
        user,
        get_followup_records,
        {
            "lead_id": lead_id,
            "customer_id": customer_id,
            "opportunity_id": opportunity_id,
        },
    )
    points: list[str] = []
    next_actions: list[dict] = []
    for rec in data.get("records") or []:
        content = (rec.get("content") or "").strip()
        if content and content not in points:
            points.append(content[:200])
        when = rec.get("next_follow_at") or rec.get("next_action_at")
        if when:
            next_actions.append({"text": "记录中的下次跟进", "at": when, "source": rec.get("source")})
    opp = data.get("opportunity") or {}
    note = (opp.get("next_action_note") or "").strip()
    if note:
        next_actions.insert(0, {"text": note, "at": opp.get("next_action_at"), "source": "opportunity"})
    subject = data.get("lead") or data.get("customer") or data.get("opportunity") or {}
    title = subject.get("name") or subject.get("title") or ""
    card = {
        "title": title,
        "summary": "；".join(points[:5]) if points else "没有可引用的跟进记录",
        "points": points[:8],
        "next_actions": next_actions[:5],
        "record_count": len(data.get("records") or []),
        "executed": False,
        "rule": data.get("rule"),
    }
    target = ",".join(
        f"{k}:{v}"
        for k, v in (("lead", lead_id), ("customer", customer_id), ("opportunity", opportunity_id))
        if v
    )
    row = _save(
        db, user, scene="followup_summary", result=card, target_id=target or None, elapsed_ms=elapsed
    )
    return _stamp(row, card)


def ticket_recommendations(db: Session, user: User, ticket_id: int) -> dict:
    _prepare(db, user, "ticket_recommend")
    data, elapsed = _timed(db, user, recommend_ticket_solutions, {"ticket_id": ticket_id})
    row = _save(
        db, user, scene="ticket_recommend", result=data, target_id=str(ticket_id), elapsed_ms=elapsed
    )
    return _stamp(row, data)


def _manual(message: str, level: str) -> dict:
    return {"passed": False, "level": level, "fallback": "manual", "message": message}


def approval_precheck(db: Session, user: User, approval_id: str) -> dict:
    ai_admin.assert_budget(db, user)
    if not ai_admin.scene_enabled(db, "approval_precheck"):
        # 停用后不挡审批，只说明改走人工。
        row = _save(
            db,
            user,
            scene="approval_precheck",
            result={"fallback": "manual", "message": "预审已停用，请人工审批", "risks": []},
            target_id=approval_id,
        )
        return _stamp(row, row.result or {})
    try:
        data, elapsed = _timed(db, user, precheck_approval, {"approval_id": approval_id})
    except HTTPException:
        raise
    except Exception:
        row = _save(
            db,
            user,
            scene="approval_precheck",
            result={"fallback": "manual", "message": "预审失败，请人工审批", "risks": []},
            target_id=approval_id,
        )
        return _stamp(row, row.result or {})
    row = _save(db, user, scene="approval_precheck", result=data, target_id=approval_id, elapsed_ms=elapsed)
    return _stamp(row, data)


def _amount(db: Session, approval_id: str) -> Decimal:
    if not approval_id.startswith(f"{ITEM_PREFIX}:"):
        return Decimal(0)
    try:
        instance_id = int(approval_id.split(":", 1)[1])
    except ValueError:
        return Decimal(0)
    row = db.query(ApprovalInstance).filter(ApprovalInstance.id == instance_id).first()
    if row is None or row.amount is None:
        return Decimal(0)
    return Decimal(row.amount)


def _level(risks: list[str], amount: Decimal, cap: Optional[Decimal]) -> str:
    blocking = [r for r in risks if _INFO_RISK not in r]
    if blocking or cap is None or amount > cap:
        return "L2"
    return "L1"


def auto_pass(db: Session, user: User, approval_id: str) -> dict:
    """L1 才通过。失败只返回人工回退，不改审批单。"""
    if not ai_admin.scene_enabled(db, "approval_precheck"):
        return _manual("预审已停用，请人工审批", "L3")
    try:
        report = approval_precheck(db, user, approval_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise
        return _manual("预审失败，请人工审批", "L3")
    except Exception:
        return _manual("预审失败，请人工审批", "L3")
    if report.get("fallback") == "manual":
        return _manual(report.get("message") or "请人工审批", "L3")
    cap = ai_admin.auto_pass_cap(db)
    level = _level(list(report.get("risks") or []), _amount(db, approval_id), cap)
    if level != "L1":
        reason = "未配置自动通过限额" if cap is None else "不是低风险单据"
        return {**_manual(f"{reason}，请人工审批", level), "risks": report.get("risks") or []}
    if _INFO_RISK not in " ".join(report.get("risks") or []):
        return _manual("当前用户不能审批这张单，请人工处理", "L2")
    from app.schemas.approval import ApprovalActRequest
    from app.services.approval import act_approval

    try:
        acted = act_approval(
            db,
            user,
            approval_id,
            "approve",
            ApprovalActRequest(comment="L1 低风险自动通过"),
        )
    except HTTPException as exc:
        return _manual(str(exc.detail), "L2")
    passed = _save(
        db,
        user,
        scene="auto_pass",
        result={"approval_id": approval_id, "level": "L1", "message": acted.message},
        target_id=approval_id,
    )
    # ponytail: 每 10 单抽 1，固定抽样不是随机。
    done = db.query(AiSceneRun).filter(AiSceneRun.scene == "auto_pass", AiSceneRun.status == "done").count()
    spot_id = None
    if done % 10 == 0:
        spot = _save(
            db,
            user,
            scene="spot_check",
            result={"approval_id": approval_id, "auto_pass_id": passed.id},
            status="pending",
            target_id=approval_id,
        )
        spot_id = spot.id
    return {
        "passed": True,
        "level": "L1",
        "fallback": None,
        "approval_id": acted.approval_id,
        "message": acted.message,
        "call_id": passed.id,
        "spot_check_id": spot_id,
    }


def get_call(db: Session, user: User, call_id: int) -> AiSceneRun:
    row = db.query(AiSceneRun).filter(AiSceneRun.id == call_id).first()
    if row is None or (row.user_id != user.id and not user_can(user, "system:view")):
        raise HTTPException(status_code=404, detail="调用记录不存在")
    return row


def list_calls(db: Session, user: User, *, page: int = 1, page_size: int = 20) -> tuple[int, list[AiSceneRun]]:
    q = db.query(AiSceneRun)
    if not user_can(user, "system:view"):
        q = q.filter(AiSceneRun.user_id == user.id)
    total = q.count()
    items = (
        q.order_by(AiSceneRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, items
