"""S2 日报/周报：只返回系统事实，禁止编造。"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from langchain_core.tools import tool
from sqlalchemy import or_

from app.agent.runtime import require_db, require_user
from app.models.project import Project, ProjectMilestone
from app.services import project as project_service
from app.services import timesheet as timesheet_service
from app.services import todo as todo_service


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _parse_day(raw: Optional[str]) -> date:
    text = (raw or "").strip()
    if not text:
        return date.today()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return date.today()


def _span(period: str, day: date) -> tuple[date, date]:
    if (period or "").strip().lower() in {"week", "weekly", "周", "本周"}:
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    return day, day


@tool
def get_work_report_facts(period: str = "today", work_date: Optional[str] = None) -> dict:
    """汇总当前用户可用于起草日报/周报的系统事实：工时、任务、里程碑、待办。
    只返回数据库里已有的记录。没有的字段就是没有，禁止用常识补。
    用户说「写日报/周报/今日工作」时必须先调此工具。不要提交日报，只提供事实。

    Args:
        period: today 或 week
        work_date: 可选 YYYY-MM-DD，默认今天
    """
    db, user = require_db(), require_user()
    day = _parse_day(work_date)
    date_from, date_to = _span(period, day)
    _, sheets = timesheet_service.list_timesheets(
        db,
        user,
        date_from=date_from,
        date_to=date_to,
        scope_filter="mine",
        page=1,
        page_size=50,
    )
    timesheets = [
        {
            "date": str(ts.work_date),
            "hours": float(ts.hours or 0),
            "work_type": ts.work_type,
            "project": getattr(ts, "project_name", None),
            "content": ts.content,
            "status": ts.status,
        }
        for ts in sheets
    ]
    _, tasks = project_service.list_tasks(
        db, user, scope_filter="mine", page=1, page_size=50
    )
    task_done = []
    task_open = []
    for t in tasks:
        item = {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "project": getattr(t, "project_name", None),
            "due_date": str(t.due_date) if t.due_date else None,
        }
        done_on = _as_date(t.updated_at) if t.status == "done" else None
        if t.status == "done" and done_on and date_from <= done_on <= date_to:
            task_done.append(item)
        elif t.status != "done":
            task_open.append(item)

    milestones = (
        db.query(ProjectMilestone)
        .join(Project, Project.id == ProjectMilestone.project_id)
        .filter(or_(Project.manager_id == user.id, Project.creator_id == user.id))
        .order_by(ProjectMilestone.deadline.asc(), ProjectMilestone.id.asc())
        .limit(30)
        .all()
    )
    milestone_rows = []
    for ms in milestones:
        deadline = ms.deadline
        in_window = deadline is not None and date_from <= deadline <= date_to
        overdue = ms.status != "done" and deadline is not None and deadline < date_from
        if not in_window and not overdue and ms.status == "done":
            continue
        if not in_window and not overdue and ms.status != "doing":
            continue
        milestone_rows.append(
            {
                "id": ms.id,
                "name": ms.name,
                "status": ms.status,
                "deadline": str(deadline) if deadline else None,
                "project_id": ms.project_id,
                "overdue": overdue,
            }
        )

    todos = []
    try:
        todo_out = todo_service.list_my_todos(db, user)
        for item in (todo_out.items or [])[:15]:
            todos.append(
                {
                    "title": item.title,
                    "category": item.category,
                    "status_label": item.status_label,
                    "urgency": item.urgency,
                }
            )
    except Exception:
        todos = []

    hours_total = round(sum(x["hours"] for x in timesheets), 2)
    return {
        "period": "week" if date_from != date_to else "today",
        "date_from": str(date_from),
        "date_to": str(date_to),
        "hours_total": hours_total,
        "timesheets": timesheets,
        "tasks_done": task_done,
        "tasks_open": task_open,
        "milestones": milestone_rows,
        "todos": todos,
        "rule": "只用以上事实起草，禁止编造。明日计划只能来自 tasks_open / todos。不要提交，只出草稿。",
    }
