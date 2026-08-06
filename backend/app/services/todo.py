"""我的待办：聚合审批、工单、线索、任务、排期、资源确认。"""
from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.rbac import collect_permission_codes, user_can
from app.models.lead import LEAD_STATUS_ASSIGNED, LEAD_STATUS_FOLLOWING
from app.models.schedule import SCHEDULE_STATUS_PENDING
from app.models.ticket import (
    TICKET_STATUS_PENDING_ACCEPT,
    TICKET_STATUS_PENDING_CONFIRM,
    TICKET_STATUS_PROCESSING,
)
from app.models.user import User
from app.schemas.todo import TodoCounts, TodoItemOut, TodoListOut
from app.services import approval as approval_service
from app.services import lead as lead_service
from app.services import project as project_service
from app.services import project_resource as resource_service
from app.services import schedule as schedule_service
from app.services import ticket as ticket_service

logger = logging.getLogger(__name__)

_LIMIT = 25
_FAR_FUTURE = datetime(9999, 12, 31)


def _has(user: User, code: str) -> bool:
    codes = collect_permission_codes(user)
    if "*" in codes:
        return True
    return user_can(user, code)


def _urgency_rank(u: str) -> int:
    return {"high": 0, "normal": 1, "low": 2}.get(u, 9)


def list_my_todos(db: Session, user: User) -> TodoListOut:
    items: list[TodoItemOut] = []
    partial_errors: list[str] = []

    if _has(user, "approval:center"):
        try:
            for a in approval_service.list_pending_approvals(db, user, limit=_LIMIT):
                items.append(
                    TodoItemOut(
                        id=f"approval:{a.id}",
                        category="approval",
                        category_label="待我审批",
                        title=a.title,
                        subtitle=f"{a.category} · {a.applicant_name}",
                        status_label=a.status_label or a.node or "待审批",
                        urgency="high",
                        path=a.deep_link or "/approvals",
                        due_at=None,
                    )
                )
        except Exception:
            logger.exception("todo source failed: approval user_id=%s", user.id)
            partial_errors.append("approval")

    if _has(user, "ticket:view"):
        try:
            for status, action in (
                (TICKET_STATUS_PENDING_ACCEPT, "请接单"),
                (TICKET_STATUS_PROCESSING, "请处理"),
            ):
                _, assigned = ticket_service.list_tickets(
                    db,
                    user,
                    status=status,
                    scope_filter="mine_assigned",
                    page=1,
                    page_size=_LIMIT,
                )
                for t in assigned:
                    urgent = "high" if getattr(t, "is_overdue", False) else "normal"
                    items.append(
                        TodoItemOut(
                            id=f"ticket:{t.id}",
                            category="ticket",
                            category_label="协作工单",
                            title=t.title,
                            subtitle=f"{t.ticket_no} · {action}",
                            status_label=action,
                            urgency=urgent,
                            path=f"/tickets/{t.id}",
                            due_at=t.due_at,
                        )
                    )
            _, created = ticket_service.list_tickets(
                db,
                user,
                status=TICKET_STATUS_PENDING_CONFIRM,
                scope_filter="mine_created",
                page=1,
                page_size=_LIMIT,
            )
            seen_ticket_ids = {x.id for x in items if x.id.startswith("ticket:")}
            for t in created:
                if f"ticket:{t.id}" in seen_ticket_ids:
                    continue
                items.append(
                    TodoItemOut(
                        id=f"ticket-confirm:{t.id}",
                        category="ticket",
                        category_label="工单待确认",
                        title=t.title,
                        subtitle=f"{t.ticket_no} · 请验收关闭",
                        status_label="待确认",
                        urgency="normal",
                        path=f"/tickets/{t.id}",
                        due_at=t.due_at,
                    )
                )
        except Exception:
            logger.exception("todo source failed: ticket user_id=%s", user.id)
            partial_errors.append("ticket")

    if _has(user, "lead:view"):
        try:
            for status, tip in (
                (LEAD_STATUS_ASSIGNED, "待首次跟进"),
                (LEAD_STATUS_FOLLOWING, "跟进中"),
            ):
                _, leads = lead_service.list_leads(
                    db,
                    user,
                    pool="mine",
                    status=status,
                    page=1,
                    page_size=_LIMIT,
                )
                for lead in leads:
                    items.append(
                        TodoItemOut(
                            id=f"lead:{lead.id}",
                            category="lead",
                            category_label="我的线索",
                            title=lead.company_name or lead.name or f"线索 #{lead.id}",
                            subtitle=f"{lead.name} · {tip}" if lead.name else tip,
                            status_label=tip,
                            urgency="normal",
                            path=f"/leads/{lead.id}",
                            due_at=None,
                        )
                    )
        except Exception:
            logger.exception("todo source failed: lead user_id=%s", user.id)
            partial_errors.append("lead")

    if _has(user, "project:view"):
        try:
            _, tasks = project_service.list_tasks(
                db,
                user,
                status="open",
                scope_filter="mine",
                page=1,
                page_size=_LIMIT,
            )
            today = date.today()
            for task in tasks:
                overdue = bool(task.due_date and task.due_date < today)
                items.append(
                    TodoItemOut(
                        id=f"task:{task.id}",
                        category="task",
                        category_label="项目任务",
                        title=task.title,
                        subtitle=f"{task.task_no or ''} · 项目#{task.project_id}".strip(" ·"),
                        status_label="已逾期" if overdue else "待完成",
                        urgency="high" if overdue else "normal",
                        path=(
                            f"/projects/delivery?tab=execute&mode=tasks"
                            f"&project_id={task.project_id}"
                        ),
                        due_at=datetime.combine(task.due_date, datetime.min.time())
                        if task.due_date
                        else None,
                    )
                )
        except Exception:
            logger.exception("todo source failed: task user_id=%s", user.id)
            partial_errors.append("task")

        try:
            resources = resource_service.list_pending_resources(
                db,
                user,
                only_pending=True,
                suggested_user_id=user.id,
            )
            for need in resources[:_LIMIT]:
                items.append(
                    TodoItemOut(
                        id=f"resource:{need.id}",
                        category="resource",
                        category_label="资源确认",
                        title=f"确认资源：{need.role_name or '角色'}",
                        subtitle=getattr(need, "project_name", None) or f"项目#{need.project_id}",
                        status_label="待确认投入",
                        urgency="normal",
                        path="/projects/delivery?tab=initiation",
                        due_at=None,
                    )
                )
        except Exception:
            logger.exception("todo source failed: resource user_id=%s", user.id)
            partial_errors.append("resource")

    if _has(user, "schedule:view"):
        try:
            _, schedules = schedule_service.list_schedules(
                db,
                user,
                status=SCHEDULE_STATUS_PENDING,
                employee_id=user.id,
                scope_filter="mine",
                page=1,
                page_size=_LIMIT,
            )
            for s in schedules:
                items.append(
                    TodoItemOut(
                        id=f"schedule:{s.id}",
                        category="schedule",
                        category_label="人员档期",
                        title=s.title,
                        subtitle="请确认本人档期",
                        status_label="待确认",
                        urgency="normal",
                        path=f"/schedules/{s.id}",
                        due_at=s.start_time,
                    )
                )
        except Exception:
            logger.exception("todo source failed: schedule user_id=%s", user.id)
            partial_errors.append("schedule")

    items.sort(key=lambda x: (_urgency_rank(x.urgency), x.due_at or _FAR_FUTURE))

    counts = TodoCounts(
        approval=sum(1 for x in items if x.category == "approval"),
        ticket=sum(1 for x in items if x.category == "ticket"),
        lead=sum(1 for x in items if x.category == "lead"),
        task=sum(1 for x in items if x.category == "task"),
        schedule=sum(1 for x in items if x.category == "schedule"),
        resource=sum(1 for x in items if x.category == "resource"),
    )
    return TodoListOut(
        total=len(items),
        counts=counts,
        items=items,
        partial_errors=partial_errors,
    )
