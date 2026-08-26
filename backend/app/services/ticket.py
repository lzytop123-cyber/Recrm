"""
工单业务逻辑：创建、分派、受理、转派、评论、完成、确认评价、关闭、退回、重开、SLA 扫描升级。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import extract, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import resolve_data_scope
from app.models.department import Department
from app.models.project import (
    PROJECT_STATUS_COMPLETED,
    PROJECT_STATUS_TERMINATED,
    TASK_STATUS_DONE,
    Project,
    ProjectTask,
)
from app.models.ticket import (
    TICKET_PRIORITIES,
    TICKET_PRIORITY_NORMAL,
    TICKET_REOPEN_BUSINESS_DAYS,
    TICKET_SLA_HOURS,
    TICKET_STATUS_CLOSED,
    TICKET_STATUS_COMPLETED,
    TICKET_STATUS_PENDING_ACCEPT,
    TICKET_STATUS_PENDING_ASSIGN,
    TICKET_STATUS_PENDING_CONFIRM,
    TICKET_STATUS_PROCESSING,
    TICKET_TYPE_COLLAB,
    TICKET_TYPES,
    Ticket,
    TicketAssigneeCandidate,
    TicketRecord,
)
from app.models.user import User
from app.schemas.ticket import (
    TicketAssignRequest,
    TicketCloseRequest,
    TicketCommentRequest,
    TicketCompleteRequest,
    TicketConfirmRequest,
    TicketCreate,
    TicketReopenRequest,
    TicketReturnRequest,
    TicketTransferRequest,
    TicketUpdate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return None
    return u.real_name or u.username


def _gen_ticket_no(db: Session) -> str:
    today = _now().strftime("%Y%m%d")
    prefix = f"GD{today}"
    last = (
        db.query(Ticket.ticket_no)
        .filter(Ticket.ticket_no.like(f"{prefix}%"))
        .order_by(Ticket.ticket_no.desc())
        .first()
    )
    seq = int(last[0][-4:]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _effective_now(ticket: Ticket) -> datetime:
    """待确认期间暂停 SLA：有效当前时间回退到暂停起点。"""
    now = _now()
    paused = _aware(ticket.sla_paused_at)
    if paused and ticket.status == TICKET_STATUS_PENDING_CONFIRM:
        return paused
    return now


def _is_overdue(ticket: Ticket) -> bool:
    if not ticket.due_at:
        return False
    if ticket.status in {TICKET_STATUS_COMPLETED, TICKET_STATUS_CLOSED, TICKET_STATUS_PENDING_CONFIRM}:
        return False
    due = _aware(ticket.due_at)
    return bool(due and due < _effective_now(ticket))


def _sla_used_ratio(ticket: Ticket) -> Optional[float]:
    created = _aware(ticket.created_at)
    due = _aware(ticket.due_at)
    if not created or not due or due <= created:
        return None
    total = (due - created).total_seconds()
    if total <= 0:
        return None
    used = (_effective_now(ticket) - created).total_seconds()
    return max(0.0, used / total)


def _is_near_sla(ticket: Ticket) -> bool:
    if ticket.status in {TICKET_STATUS_COMPLETED, TICKET_STATUS_CLOSED, TICKET_STATUS_PENDING_CONFIRM}:
        return False
    if _is_overdue(ticket):
        return False
    ratio = _sla_used_ratio(ticket)
    return bool(ratio is not None and ratio >= 0.5)


def _add_business_days(start: date, days: int) -> date:
    cur = start
    added = 0
    while added < days:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur


def _can_reopen(ticket: Ticket) -> bool:
    if ticket.status != TICKET_STATUS_CLOSED or not ticket.closed_at:
        return False
    closed = _aware(ticket.closed_at)
    if not closed:
        return False
    deadline = _add_business_days(closed.date(), TICKET_REOPEN_BUSINESS_DAYS)
    return _now().date() <= deadline


def _pause_sla(ticket: Ticket) -> None:
    if not ticket.sla_paused_at:
        ticket.sla_paused_at = _now()


def _resume_sla(ticket: Ticket) -> None:
    paused = _aware(ticket.sla_paused_at)
    if not paused:
        return
    delta = _now() - paused
    if ticket.due_at:
        due = _aware(ticket.due_at)
        if due:
            ticket.due_at = due + delta
    ticket.sla_paused_at = None


def _add_record(
    db: Session,
    ticket: Ticket,
    user: User,
    action: str,
    content: Optional[str] = None,
) -> None:
    db.add(
        TicketRecord(
            ticket_id=ticket.id,
            user_id=user.id,
            action=action,
            content=content,
        )
    )


def _resolve_task(
    db: Session, project_id: Optional[int], task_id: Optional[int]
) -> Optional[ProjectTask]:
    if not task_id:
        return None
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=400, detail="关联项目任务不存在")
    if project_id and task.project_id != project_id:
        raise HTTPException(status_code=400, detail="项目任务不属于所选项目")
    return task


def _link_task(db: Session, ticket: Ticket, task: Optional[ProjectTask]) -> None:
    if task is None:
        return
    ticket.task_id = task.id
    if not ticket.project_id:
        ticket.project_id = task.project_id
    task.ticket_id = ticket.id


def _find_dept_manager(db: Session, department_id: Optional[int]) -> Optional[User]:
    if not department_id:
        return None
    users = (
        db.query(User)
        .filter(User.department_id == department_id, User.is_active.is_(True))
        .order_by(User.id.asc())
        .all()
    )
    for u in users:
        if can_manage(u):
            return u
    return users[0] if users else None


def enrich_ticket(db: Session, ticket: Ticket, user: Optional[User] = None) -> Ticket:
    ticket.creator_name = _user_name(db, ticket.creator_id)  # type: ignore[attr-defined]
    ticket.assignee_name = _user_name(db, ticket.assignee_id)  # type: ignore[attr-defined]
    candidates = (
        db.query(TicketAssigneeCandidate)
        .filter(TicketAssigneeCandidate.ticket_id == ticket.id)
        .order_by(TicketAssigneeCandidate.id.asc())
        .all()
    )
    ticket.candidate_ids = [c.user_id for c in candidates]  # type: ignore[attr-defined]
    ticket.candidate_names = [  # type: ignore[attr-defined]
        _user_name(db, c.user_id) or f"#{c.user_id}" for c in candidates
    ]
    ticket.is_overdue = _is_overdue(ticket)  # type: ignore[attr-defined]
    ticket.sla_used_ratio = _sla_used_ratio(ticket)  # type: ignore[attr-defined]
    ticket.is_near_sla = _is_near_sla(ticket)  # type: ignore[attr-defined]
    ticket.can_reopen = _can_reopen(ticket)  # type: ignore[attr-defined]
    if ticket.department_id:
        dept = db.query(Department).filter(Department.id == ticket.department_id).first()
        ticket.department_name = dept.name if dept else None  # type: ignore[attr-defined]
    else:
        ticket.department_name = None  # type: ignore[attr-defined]
    if ticket.project_id:
        project = db.query(Project).filter(Project.id == ticket.project_id).first()
        ticket.project_name = project.name if project else None  # type: ignore[attr-defined]
    else:
        ticket.project_name = None  # type: ignore[attr-defined]
    if ticket.task_id:
        task = db.query(ProjectTask).filter(ProjectTask.id == ticket.task_id).first()
        ticket.task_no = task.task_no if task else None  # type: ignore[attr-defined]
        ticket.task_title = task.title if task else None  # type: ignore[attr-defined]
    else:
        ticket.task_no = None  # type: ignore[attr-defined]
        ticket.task_title = None  # type: ignore[attr-defined]
    if user is not None:
        _attach_action_flags(user, ticket)
    return ticket


def enrich_detail(db: Session, ticket: Ticket, user: Optional[User] = None) -> Ticket:
    enrich_ticket(db, ticket, user=user)
    records = (
        db.query(TicketRecord)
        .filter(TicketRecord.ticket_id == ticket.id)
        .order_by(TicketRecord.id.asc())
        .all()
    )
    for r in records:
        r.user_name = _user_name(db, r.user_id)  # type: ignore[attr-defined]
    ticket.records = records  # type: ignore[attr-defined]
    return ticket


def _candidate_user_ids(db: Session, ticket_id: int) -> set[int]:
    rows = (
        db.query(TicketAssigneeCandidate.user_id)
        .filter(TicketAssigneeCandidate.ticket_id == ticket_id)
        .all()
    )
    return {r[0] for r in rows}


def assert_can_view(user: User, ticket: Ticket) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes:
        return
    if ticket.creator_id == user.id or ticket.assignee_id == user.id:
        return
    cand_ids = getattr(ticket, "candidate_ids", None)
    if cand_ids is not None and user.id in cand_ids:
        return
    from sqlalchemy.orm import object_session

    session = object_session(ticket)
    if session is not None and user.id in _candidate_user_ids(session, ticket.id):
        return
    scope = resolve_data_scope(user, "ticket")
    if scope == "company":
        return
    if scope == "department" and user.department_id and ticket.department_id == user.department_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该工单")


def can_manage(user: User) -> bool:
    """部门侧管理角色（用于 SLA 找负责人等），不等于可代办全部工单动作。"""
    role_codes = {r.code for r in user.roles}
    return bool(
        "admin" in role_codes
        or "center_lead" in role_codes
        or "gm" in role_codes
        or "vp" in role_codes
        or "pm" in role_codes
        or "middle_manager" in role_codes
        or "executive" in role_codes
        or "delivery_lead" in role_codes
    )


def _is_admin(user: User) -> bool:
    return "admin" in {r.code for r in user.roles}


def _is_undertaking_dept_lead(user: User, ticket: Ticket) -> bool:
    """承接部门负责人：同部门且为中层/交付负责人/管理层。"""
    if not ticket.department_id or user.department_id != ticket.department_id:
        return False
    return can_manage(user)


def _can_assign(user: User, ticket: Ticket) -> bool:
    return _is_admin(user) or ticket.creator_id == user.id or _is_undertaking_dept_lead(user, ticket)


def _base_can_accept(user: User, ticket: Ticket) -> bool:
    if _is_admin(user):
        return True
    if ticket.assignee_id == user.id:
        return True
    cand_ids = getattr(ticket, "candidate_ids", None)
    if cand_ids is not None and user.id in cand_ids:
        return True
    from sqlalchemy.orm import object_session

    session = object_session(ticket)
    if session is not None and user.id in _candidate_user_ids(session, ticket.id):
        return True
    return _is_undertaking_dept_lead(user, ticket)


def _ticket_flow_hint(db: Session, ticket: Ticket, user: User):
    """AP-12 接单审批上下文：返回 (open_instance, my_assignee_task, hint)。

    - open_instance: 当前工单是否有进行中的接单审批实例
    - my_assignee_task: 若当前节点为"本人确认接单"且待办人是 user，返回该任务；否则 None
    - hint: 供覆盖 next_actor_hint / 拒绝时的提示文案；无实例时为 None
    """
    from app.models.approval_flow import INSTANCE_BLOCKED, NODE_ASSIGNEE, TASK_ACTIVE
    from app.services import approval_flow

    inst = approval_flow.find_open_instance(db, "ticket", ticket.id)
    if inst is None:
        return None, None, None
    if inst.status == INSTANCE_BLOCKED:
        return inst, None, "接单审批已挂起（无可用审批人），请联系管理员"
    active = [t for t in inst.tasks if t.status == TASK_ACTIVE and t.seq == inst.current_seq]
    mine = next(
        (t for t in active if t.node_type == NODE_ASSIGNEE and t.assignee_id == user.id),
        None,
    )
    if mine is not None:
        return inst, mine, "等你确认接单"
    node_names = "、".join(t.name for t in active) or "审批"
    return inst, None, f"接单审批中：{node_names}"


def _can_accept(user: User, ticket: Ticket) -> bool:
    if not _base_can_accept(user, ticket):
        return False
    from sqlalchemy.orm import object_session

    session = object_session(ticket)
    if session is None:
        return True
    inst, mine, _ = _ticket_flow_hint(session, ticket, user)
    if inst is None:
        return True
    # 系统管理员始终可代接（应急路径）
    if _is_admin(user):
        return True
    return mine is not None


def _can_process(user: User, ticket: Ticket) -> bool:
    """提交处理结果：仅当前处理人或系统管理员（应急）。"""
    return _is_admin(user) or ticket.assignee_id == user.id


def _can_transfer(user: User, ticket: Ticket) -> bool:
    return _is_admin(user) or ticket.assignee_id == user.id or _is_undertaking_dept_lead(user, ticket)


def _base_can_confirm(user: User, ticket: Ticket) -> bool:
    return _is_admin(user) or ticket.creator_id == user.id


def _cross_accept_flow_hint(db: Session, ticket: Ticket, user: User):
    """AP-13 跨部门工单验收上下文：返回 (open_instance, my_assignee_task, hint)。"""
    from app.models.approval_flow import INSTANCE_BLOCKED, NODE_ASSIGNEE, TASK_ACTIVE
    from app.services import approval_flow

    inst = approval_flow.find_open_instance(db, "ticket_cross_accept", ticket.id)
    if inst is None:
        return None, None, None
    if inst.status == INSTANCE_BLOCKED:
        return inst, None, "跨部门验收已挂起（无可用审批人），请联系管理员"
    active = [t for t in inst.tasks if t.status == TASK_ACTIVE and t.seq == inst.current_seq]
    mine = next(
        (t for t in active if t.node_type == NODE_ASSIGNEE and t.assignee_id == user.id),
        None,
    )
    if mine is not None:
        return inst, mine, "等你验收"
    node_names = "、".join(t.name for t in active) or "审批"
    return inst, None, f"跨部门验收审批中：{node_names}"


def _can_confirm(user: User, ticket: Ticket) -> bool:
    """验收/退回/关闭：仅发起人或系统管理员（应急）。"""
    if not _base_can_confirm(user, ticket):
        return False
    from sqlalchemy.orm import object_session

    session = object_session(ticket)
    if session is None:
        return True
    # 只有跨部门工单会起 AP-13 实例；其他情况无影响
    inst, mine, _ = _cross_accept_flow_hint(session, ticket, user)
    if inst is None:
        return True
    if _is_admin(user):
        return True
    return mine is not None


def _next_actor_hint(ticket: Ticket) -> str:
    if ticket.status == TICKET_STATUS_PENDING_ASSIGN:
        return "请承接部门负责人分派处理人"
    if ticket.status == TICKET_STATUS_PENDING_ACCEPT:
        names = getattr(ticket, "candidate_names", None) or []
        if len(names) > 1:
            return f"请候选处理人接单（{ '、'.join(names) }；部门负责人可代接）"
        return "请指定处理人接单（承接部门负责人可代接）"
    if ticket.status == TICKET_STATUS_PROCESSING:
        return "请处理人提交处理结果"
    if ticket.status == TICKET_STATUS_PENDING_CONFIRM:
        return "请发起人验收并关闭"
    if ticket.status == TICKET_STATUS_COMPLETED:
        return "请发起人评价并关闭"
    return ""


def _attach_action_flags(user: User, ticket: Ticket) -> None:
    ticket.can_assign = _can_assign(user, ticket) and ticket.status in {  # type: ignore[attr-defined]
        TICKET_STATUS_PENDING_ASSIGN,
        TICKET_STATUS_PENDING_ACCEPT,
    }
    ticket.can_accept = _can_accept(user, ticket) and ticket.status in {  # type: ignore[attr-defined]
        TICKET_STATUS_PENDING_ASSIGN,
        TICKET_STATUS_PENDING_ACCEPT,
    }
    ticket.can_transfer = _can_transfer(user, ticket) and ticket.status in {  # type: ignore[attr-defined]
        TICKET_STATUS_PENDING_ACCEPT,
        TICKET_STATUS_PROCESSING,
        TICKET_STATUS_PENDING_CONFIRM,
    }
    ticket.can_complete = _can_process(user, ticket) and ticket.status == TICKET_STATUS_PROCESSING  # type: ignore[attr-defined]
    ticket.can_confirm = _can_confirm(user, ticket) and ticket.status in {  # type: ignore[attr-defined]
        TICKET_STATUS_PENDING_CONFIRM,
        TICKET_STATUS_COMPLETED,
    }
    ticket.can_return = _can_confirm(user, ticket) and ticket.status == TICKET_STATUS_PENDING_CONFIRM  # type: ignore[attr-defined]
    ticket.can_reopen = _can_reopen(ticket) and _can_confirm(user, ticket)  # type: ignore[attr-defined]
    ticket.next_actor_hint = _next_actor_hint(ticket)  # type: ignore[attr-defined]
    from sqlalchemy.orm import object_session

    session = object_session(ticket)
    if session is not None:
        if ticket.status in {TICKET_STATUS_PENDING_ASSIGN, TICKET_STATUS_PENDING_ACCEPT}:
            inst, _mine, hint = _ticket_flow_hint(session, ticket, user)
            if inst is not None and hint:
                ticket.next_actor_hint = hint  # type: ignore[attr-defined]
        elif ticket.status == TICKET_STATUS_PENDING_CONFIRM:
            inst, _mine, hint = _cross_accept_flow_hint(session, ticket, user)
            if inst is not None and hint:
                ticket.next_actor_hint = hint  # type: ignore[attr-defined]


def _replace_candidates(db: Session, ticket: Ticket, user_ids: list[int]) -> None:
    db.query(TicketAssigneeCandidate).filter(
        TicketAssigneeCandidate.ticket_id == ticket.id
    ).delete(synchronize_session=False)
    seen: set[int] = set()
    for uid in user_ids:
        if uid in seen:
            continue
        seen.add(uid)
        db.add(TicketAssigneeCandidate(ticket_id=ticket.id, user_id=uid))


def _is_cross_dept_ticket(db: Session, ticket: Ticket) -> bool:
    """发起人部门与承接部门不同视为跨部门工单。"""
    if not ticket.department_id:
        return False
    creator = db.query(User).filter(User.id == ticket.creator_id).first()
    if not creator or not creator.department_id:
        return False
    return creator.department_id != ticket.department_id


def _maybe_start_ticket_approval(db: Session, ticket: Ticket, initiator: User) -> None:
    """AP-12 工单审批与接单：有执行人时发起部门负责人→执行人确认。"""
    from app.services import approval_flow

    if not ticket.assignee_id:
        return
    if approval_flow.find_open_instance(db, "ticket", ticket.id) is not None:
        return
    if approval_flow.select_rule(db, "ticket", {}) is None:
        return
    approval_flow.start_instance(
        db,
        biz_type="ticket",
        biz_id=ticket.id,
        initiator=initiator,
        title=approval_flow.approval_title("工单接单", ticket.title),
        summary=(ticket.content or "")[:120] or None,
        department_id=ticket.department_id,
        deep_link=f"/tickets/{ticket.id}",
        assignees={"executor_id": ticket.assignee_id},
        commit=False,
    )


def _apply_accept_from_flow(db: Session, ticket: Ticket, actor: User, note: str) -> None:
    if ticket.status not in {TICKET_STATUS_PENDING_ASSIGN, TICKET_STATUS_PENDING_ACCEPT}:
        return
    if not ticket.assignee_id:
        ticket.assignee_id = actor.id
    ticket.status = TICKET_STATUS_PROCESSING
    ticket.accepted_at = _now()
    _add_record(db, ticket, actor, "accept", note)


def on_ticket_flow_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-12 终审回调：通过则自动接单，驳回/撤回保持待接单。"""
    from app.services import approval_flow

    ticket = db.query(Ticket).filter(Ticket.id == instance.biz_id).first()
    if not ticket:
        return
    if approved:
        actor = approval_flow.last_actor(db, instance)
        if actor is not None:
            _apply_accept_from_flow(db, ticket, actor, "审批通过自动接单")
    elif not withdrawn:
        actor = approval_flow.last_actor(db, instance)
        if actor is not None:
            _add_record(db, ticket, actor, "reject", instance.reject_reason or "接单审批驳回")


def on_ticket_cross_accept_result(
    db: Session, instance, *, approved: bool, withdrawn: bool = False
) -> None:
    """AP-13 终审回调：跨部门验收通过则确认完成。"""
    from app.services import approval_flow

    ticket = db.query(Ticket).filter(Ticket.id == instance.biz_id).first()
    if not ticket or ticket.status != TICKET_STATUS_PENDING_CONFIRM:
        return
    if not approved:
        if not withdrawn:
            actor = approval_flow.last_actor(db, instance)
            if actor is not None:
                _add_record(db, ticket, actor, "reject", instance.reject_reason or "验收驳回")
        return
    actor = approval_flow.last_actor(db, instance)
    if actor is None:
        creator = db.query(User).filter(User.id == ticket.creator_id).first()
        if not creator:
            return
        actor = creator
    _resume_sla(ticket)
    ticket.status = TICKET_STATUS_COMPLETED
    _add_record(db, ticket, actor, "confirm", "审批通过自动确认完成")


def create_ticket(db: Session, user: User, payload: TicketCreate) -> Ticket:
    ticket_type = payload.ticket_type or TICKET_TYPE_COLLAB
    if ticket_type not in TICKET_TYPES:
        raise HTTPException(status_code=400, detail="无效的工单类型")
    priority = payload.priority or TICKET_PRIORITY_NORMAL
    if priority not in TICKET_PRIORITIES:
        raise HTTPException(status_code=400, detail="无效的优先级")

    assignee_ids: list[int] = []
    for uid in list(payload.assignee_ids or []):
        if uid and uid not in assignee_ids:
            assignee_ids.append(uid)
    if payload.assignee_id and payload.assignee_id not in assignee_ids:
        assignee_ids.insert(0, payload.assignee_id)

    assignees: list[User] = []
    if assignee_ids:
        rows = (
            db.query(User)
            .filter(User.id.in_(assignee_ids), User.is_active.is_(True))
            .all()
        )
        by_id = {u.id: u for u in rows}
        missing = [uid for uid in assignee_ids if uid not in by_id]
        if missing:
            raise HTTPException(status_code=400, detail="处理人不存在或已停用")
        assignees = [by_id[uid] for uid in assignee_ids]

    project_id = payload.project_id
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=400, detail="项目不存在")
        if project.status in {PROJECT_STATUS_COMPLETED, PROJECT_STATUS_TERMINATED}:
            raise HTTPException(
                status_code=400,
                detail="项目已结项或已终止，不可再发起协作工单",
            )

    task = _resolve_task(db, project_id, payload.task_id)
    if task and not project_id:
        project_id = task.project_id
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.status in {PROJECT_STATUS_COMPLETED, PROJECT_STATUS_TERMINATED}:
            raise HTTPException(
                status_code=400,
                detail="项目已结项或已终止，不可再发起协作工单",
            )
    if task and task.status == TASK_STATUS_DONE:
        raise HTTPException(status_code=400, detail="关联任务已完成，请换未完成的任务或不选任务")

    department_id = payload.department_id
    if department_id is not None:
        dept = db.query(Department).filter(Department.id == department_id).first()
        if not dept:
            raise HTTPException(status_code=400, detail="承接部门不存在")
        if (dept.code or "").upper() == "ROOT":
            raise HTTPException(
                status_code=400,
                detail="请选择具体业务部门作为承接部门，不能选总公司/根部门",
            )
    elif assignees:
        department_id = assignees[0].department_id

    if department_id is not None:
        dept = db.query(Department).filter(Department.id == department_id).first()
        if dept and (dept.code or "").upper() == "ROOT":
            department_id = None

    if department_id is None:
        raise HTTPException(status_code=400, detail="请选择承接部门")

    for a in assignees:
        if a.department_id != department_id:
            raise HTTPException(
                status_code=400,
                detail=f"处理人「{_user_name(db, a.id)}」不属于所选承接部门",
            )

    sla_hours = TICKET_SLA_HOURS.get(ticket_type, 72)
    due_at = _now() + timedelta(hours=sla_hours)
    # 多人候选：待接收，主处理人暂空，任一候选接单后落主责
    # 单人：直接指定为处理人，待其接单
    if len(assignees) == 1:
        status_val = TICKET_STATUS_PENDING_ACCEPT
        primary_id = assignees[0].id
    elif len(assignees) > 1:
        status_val = TICKET_STATUS_PENDING_ACCEPT
        primary_id = None
    else:
        status_val = TICKET_STATUS_PENDING_ASSIGN
        primary_id = None

    ticket = Ticket(
        ticket_no=_gen_ticket_no(db),
        title=payload.title.strip(),
        ticket_type=ticket_type,
        priority=priority,
        status=status_val,
        content=payload.content.strip(),
        creator_id=user.id,
        assignee_id=primary_id,
        department_id=department_id,
        project_id=project_id,
        due_at=due_at,
        remark=payload.remark,
        sla_remind_level=0,
        escalated_level=0,
    )
    db.add(ticket)
    db.flush()
    if assignees:
        _replace_candidates(db, ticket, [a.id for a in assignees])
    _link_task(db, ticket, task)
    _add_record(db, ticket, user, "create", f"创建工单：{ticket.title}")
    if task:
        _add_record(db, ticket, user, "link_task", f"关联任务 {task.task_no} · {task.title}")
    if assignees:
        names = "、".join(_user_name(db, a.id) or f"#{a.id}" for a in assignees)
        if len(assignees) == 1:
            _add_record(db, ticket, user, "assign", f"指定处理人：{names}")
        else:
            _add_record(db, ticket, user, "assign", f"指定候选处理人：{names}（谁先接单谁主责）")
    _maybe_start_ticket_approval(db, ticket, user)
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def update_ticket(db: Session, user: User, ticket_id: int, payload: TicketUpdate) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    if ticket.creator_id != user.id and not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅发起人或系统管理员可编辑")
    if ticket.status in {TICKET_STATUS_COMPLETED, TICKET_STATUS_CLOSED}:
        raise HTTPException(status_code=400, detail="已完成/已关闭工单不可编辑")

    data = payload.model_dump(exclude_unset=True)
    if "ticket_type" in data and data["ticket_type"] not in TICKET_TYPES:
        raise HTTPException(status_code=400, detail="无效的工单类型")
    if "priority" in data and data["priority"] not in TICKET_PRIORITIES:
        raise HTTPException(status_code=400, detail="无效的优先级")
    if "title" in data and data["title"]:
        data["title"] = data["title"].strip()
    if "content" in data and data["content"]:
        data["content"] = data["content"].strip()

    task_id = data.pop("task_id", None) if "task_id" in data else None
    for k, v in data.items():
        setattr(ticket, k, v)
    if task_id is not None:
        task = _resolve_task(db, ticket.project_id, task_id)
        _link_task(db, ticket, task)
    _add_record(db, ticket, user, "update", "更新工单信息")
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def list_tickets(
    db: Session,
    user: User,
    *,
    status: Optional[str] = None,
    ticket_type: Optional[str] = None,
    priority: Optional[str] = None,
    keyword: Optional[str] = None,
    project_id: Optional[int] = None,
    department_id: Optional[int] = None,
    scope_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Ticket]]:
    q = db.query(Ticket)
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    scope = resolve_data_scope(user, "ticket")

    if scope_filter == "mine_created":
        q = q.filter(Ticket.creator_id == user.id)
    elif scope_filter == "mine_assigned":
        cand_ticket_ids = db.query(TicketAssigneeCandidate.ticket_id).filter(
            TicketAssigneeCandidate.user_id == user.id
        )
        q = q.filter(
            or_(Ticket.assignee_id == user.id, Ticket.id.in_(cand_ticket_ids))
        )
    elif scope_filter == "mine":
        cand_ticket_ids = db.query(TicketAssigneeCandidate.ticket_id).filter(
            TicketAssigneeCandidate.user_id == user.id
        )
        q = q.filter(
            or_(
                Ticket.creator_id == user.id,
                Ticket.assignee_id == user.id,
                Ticket.id.in_(cand_ticket_ids),
            )
        )
    elif not is_admin:
        if scope == "personal":
            cand_ticket_ids = db.query(TicketAssigneeCandidate.ticket_id).filter(
                TicketAssigneeCandidate.user_id == user.id
            )
            q = q.filter(
                or_(
                    Ticket.creator_id == user.id,
                    Ticket.assignee_id == user.id,
                    Ticket.id.in_(cand_ticket_ids),
                )
            )
        elif scope == "department" and user.department_id:
            q = q.filter(
                or_(
                    Ticket.department_id == user.department_id,
                    Ticket.creator_id == user.id,
                    Ticket.assignee_id == user.id,
                )
            )

    if status:
        q = q.filter(Ticket.status == status)
    if ticket_type:
        q = q.filter(Ticket.ticket_type == ticket_type)
    if priority:
        q = q.filter(Ticket.priority == priority)
    if project_id:
        q = q.filter(Ticket.project_id == project_id)
    if department_id:
        q = q.filter(Ticket.department_id == department_id)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(or_(Ticket.title.like(like), Ticket.ticket_no.like(like), Ticket.content.like(like)))

    total = q.count()
    items = (
        q.order_by(Ticket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, [enrich_ticket(db, x, user=user) for x in items]


def get_ticket(db: Session, user: User, ticket_id: int) -> Ticket:
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.records))
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    return enrich_detail(db, ticket, user=user)


def assign_ticket(
    db: Session, user: User, ticket_id: int, payload: TicketAssignRequest
) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    if not _can_assign(user, ticket):
        raise HTTPException(status_code=403, detail="仅发起人、承接部门负责人或系统管理员可分派")
    if ticket.status not in {TICKET_STATUS_PENDING_ASSIGN, TICKET_STATUS_PENDING_ACCEPT}:
        raise HTTPException(status_code=400, detail="当前状态不可分派")

    assignee = db.query(User).filter(User.id == payload.assignee_id, User.is_active.is_(True)).first()
    if not assignee:
        raise HTTPException(status_code=400, detail="处理人不存在或已停用")

    ticket.assignee_id = assignee.id
    ticket.department_id = assignee.department_id or ticket.department_id
    ticket.status = TICKET_STATUS_PENDING_ACCEPT
    _replace_candidates(db, ticket, [assignee.id])
    note = payload.remark or f"分派给 {_user_name(db, assignee.id)}"
    _add_record(db, ticket, user, "assign", note)
    _maybe_start_ticket_approval(db, ticket, user)
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def accept_ticket(db: Session, user: User, ticket_id: int) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    if ticket.status not in {TICKET_STATUS_PENDING_ASSIGN, TICKET_STATUS_PENDING_ACCEPT}:
        raise HTTPException(status_code=400, detail="仅待分派/待接收工单可接单")
    from app.services import approval_flow

    inst, mine, hint = _ticket_flow_hint(db, ticket, user)
    if inst is not None:
        if mine is not None:
            # AP-12 本人确认接单：把弹窗点击等价成 assignee 节点的通过
            approval_flow.act(db, user, inst, approve=True, comment="确认接单")
            db.refresh(ticket)
            return enrich_detail(db, ticket, user=user)
        if _is_admin(user):
            # 管理员应急代接：撤销进行中的实例，再走后续原生落库
            approval_flow.cancel_instance(db, inst, reason="系统管理员应急代接", commit=False)
        else:
            raise HTTPException(status_code=409, detail=hint or "接单审批中，请等待审批")
    if not _can_accept(user, ticket):
        raise HTTPException(
            status_code=403,
            detail="仅指定处理人或承接部门负责人可接单（系统管理员可应急代接）",
        )

    if ticket.status == TICKET_STATUS_PENDING_ASSIGN and not ticket.assignee_id:
        cand_ids = _candidate_user_ids(db, ticket.id)
        if user.id in cand_ids:
            ticket.assignee_id = user.id
            _add_record(db, ticket, user, "assign", "候选处理人接单成为主责")
        elif not (_is_undertaking_dept_lead(user, ticket) or _is_admin(user)):
            raise HTTPException(status_code=403, detail="未分派工单请由承接部门负责人认领或先分派")
        else:
            ticket.assignee_id = user.id
            _add_record(db, ticket, user, "assign", "部门负责人认领并接单")
    elif ticket.assignee_id and ticket.assignee_id != user.id:
        cand_ids = _candidate_user_ids(db, ticket.id)
        if user.id in cand_ids:
            old = _user_name(db, ticket.assignee_id)
            ticket.assignee_id = user.id
            _add_record(db, ticket, user, "assign", f"候选处理人接单（原指定 {old}）")
        elif _is_undertaking_dept_lead(user, ticket) or _is_admin(user):
            old = _user_name(db, ticket.assignee_id)
            ticket.assignee_id = user.id
            _add_record(db, ticket, user, "assign", f"部门负责人代接（原处理人 {old}）")
        else:
            raise HTTPException(status_code=403, detail="仅指定/候选处理人或部门负责人可接单")
    elif not ticket.assignee_id:
        # 多人候选、尚无主责
        cand_ids = _candidate_user_ids(db, ticket.id)
        if user.id in cand_ids or _is_undertaking_dept_lead(user, ticket) or _is_admin(user):
            ticket.assignee_id = user.id
            _add_record(db, ticket, user, "assign", "候选处理人接单成为主责")
        else:
            raise HTTPException(status_code=403, detail="仅候选处理人或部门负责人可接单")

    ticket.status = TICKET_STATUS_PROCESSING
    ticket.accepted_at = _now()
    _add_record(db, ticket, user, "accept", "已接单处理")
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def transfer_ticket(
    db: Session, user: User, ticket_id: int, payload: TicketTransferRequest
) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    if not _can_transfer(user, ticket):
        raise HTTPException(status_code=403, detail="仅处理人、承接部门负责人或系统管理员可转派")
    if ticket.status not in {
        TICKET_STATUS_PENDING_ACCEPT,
        TICKET_STATUS_PROCESSING,
        TICKET_STATUS_PENDING_CONFIRM,
    }:
        raise HTTPException(status_code=400, detail="当前状态不可转派")

    assignee = db.query(User).filter(User.id == payload.assignee_id, User.is_active.is_(True)).first()
    if not assignee:
        raise HTTPException(status_code=400, detail="处理人不存在或已停用")
    if assignee.id == ticket.assignee_id:
        raise HTTPException(status_code=400, detail="不能转派给当前处理人")

    if ticket.status == TICKET_STATUS_PENDING_CONFIRM:
        _resume_sla(ticket)

    old_name = _user_name(db, ticket.assignee_id)
    ticket.assignee_id = assignee.id
    ticket.department_id = assignee.department_id or ticket.department_id
    ticket.status = TICKET_STATUS_PENDING_ACCEPT
    ticket.accepted_at = None
    _replace_candidates(db, ticket, [assignee.id])
    reason = payload.reason or ""
    _add_record(
        db,
        ticket,
        user,
        "transfer",
        f"由 {old_name} 转派给 {_user_name(db, assignee.id)}"
        + (f"：{reason}" if reason else ""),
    )
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def complete_ticket(
    db: Session, user: User, ticket_id: int, payload: TicketCompleteRequest
) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    if not _can_process(user, ticket):
        raise HTTPException(status_code=403, detail="仅当前处理人可提交结果（系统管理员可应急代办）")
    if ticket.status != TICKET_STATUS_PROCESSING:
        raise HTTPException(status_code=400, detail="仅处理中工单可提交完成")
    ticket.result = payload.result.strip()
    ticket.status = TICKET_STATUS_PENDING_CONFIRM
    ticket.completed_at = _now()
    _pause_sla(ticket)
    note = ticket.result
    if _is_admin(user) and ticket.assignee_id != user.id:
        note = f"[管理员代办] {note}"
    _add_record(db, ticket, user, "complete", note)

    # AP-13 跨部门工单验收：发起人本人确认
    from app.services import approval_flow

    if (
        _is_cross_dept_ticket(db, ticket)
        and approval_flow.select_rule(db, "ticket_cross_accept", {}) is not None
    ):
        approval_flow.start_instance(
            db,
            biz_type="ticket_cross_accept",
            biz_id=ticket.id,
            initiator=user,
            title=approval_flow.approval_title("跨部门工单验收", ticket.title),
            summary=(ticket.result or "")[:120] or None,
            department_id=ticket.department_id,
            deep_link=f"/tickets/{ticket.id}",
            assignees={"creator_id": ticket.creator_id},
            commit=False,
        )
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def return_ticket(
    db: Session, user: User, ticket_id: int, payload: TicketReturnRequest
) -> Ticket:
    """发起人退回处理（待确认 → 处理中）。"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    if not _can_confirm(user, ticket):
        raise HTTPException(status_code=403, detail="仅发起人可退回处理（系统管理员可应急代办）")
    if ticket.status != TICKET_STATUS_PENDING_CONFIRM:
        raise HTTPException(status_code=400, detail="仅待确认工单可退回")
    # 退回时若跨部门验收实例还挂着，一并撤销，避免下一轮 complete 后起单被卡
    from app.services import approval_flow

    open_inst = approval_flow.find_open_instance(db, "ticket_cross_accept", ticket.id)
    if open_inst is not None:
        approval_flow.cancel_instance(db, open_inst, reason="发起人退回处理", commit=False)
    _resume_sla(ticket)
    ticket.status = TICKET_STATUS_PROCESSING
    ticket.completed_at = None
    ticket.result = None
    _add_record(db, ticket, user, "return", payload.reason.strip())
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def confirm_ticket(
    db: Session,
    user: User,
    ticket_id: int,
    payload: Optional[TicketConfirmRequest] = None,
) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    if not _can_confirm(user, ticket):
        raise HTTPException(status_code=403, detail="仅发起人可确认完成（系统管理员可应急代办）")
    if ticket.status != TICKET_STATUS_PENDING_CONFIRM:
        raise HTTPException(status_code=400, detail="仅待确认工单可确认")
    from app.services import approval_flow

    applied_by_flow = False
    if _is_cross_dept_ticket(db, ticket):
        inst, mine, hint = _cross_accept_flow_hint(db, ticket, user)
        if inst is not None:
            if mine is not None:
                # AP-13 发起人本人验收：把「验收并关闭」的点击等价成 assignee 节点的通过
                approval_flow.act(db, user, inst, approve=True, comment="确认完成")
                # 回调 on_ticket_cross_accept_result 已 _resume_sla + status=COMPLETED + record
                db.refresh(ticket)
                applied_by_flow = True
            elif _is_admin(user):
                approval_flow.cancel_instance(db, inst, reason="系统管理员应急代验收", commit=False)
            else:
                raise HTTPException(status_code=409, detail=hint or "跨部门验收审批中，请等待审批")

    if not applied_by_flow:
        _resume_sla(ticket)
    close = True
    if payload:
        ticket.satisfaction = payload.satisfaction
        ticket.satisfaction_comment = (payload.comment or "").strip() or None
        close = payload.close
        _add_record(
            db,
            ticket,
            user,
            "rate",
            f"满意度 {payload.satisfaction}/5"
            + (f"：{ticket.satisfaction_comment}" if ticket.satisfaction_comment else ""),
        )
    if not applied_by_flow:
        ticket.status = TICKET_STATUS_COMPLETED
        _add_record(db, ticket, user, "confirm", "确认完成")
    if close:
        ticket.status = TICKET_STATUS_CLOSED
        ticket.closed_at = _now()
        if ticket.satisfaction is None:
            raise HTTPException(status_code=400, detail="验收关闭需填写 1-5 分满意度")
        _add_record(db, ticket, user, "close", "验收并关闭")
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def close_ticket(
    db: Session,
    user: User,
    ticket_id: int,
    payload: Optional[TicketCloseRequest] = None,
) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    if not _can_confirm(user, ticket):
        raise HTTPException(status_code=403, detail="仅发起人可关闭（系统管理员可应急代办）")
    if ticket.status not in {TICKET_STATUS_COMPLETED, TICKET_STATUS_PENDING_CONFIRM}:
        raise HTTPException(status_code=400, detail="仅已完成/待确认工单可关闭")

    if ticket.status == TICKET_STATUS_PENDING_CONFIRM:
        _resume_sla(ticket)

    if payload and payload.satisfaction is not None:
        ticket.satisfaction = payload.satisfaction
        ticket.satisfaction_comment = (payload.comment or "").strip() or None
        _add_record(
            db,
            ticket,
            user,
            "rate",
            f"满意度 {payload.satisfaction}/5"
            + (f"：{ticket.satisfaction_comment}" if ticket.satisfaction_comment else ""),
        )

    if ticket.satisfaction is None:
        raise HTTPException(status_code=400, detail="关闭工单需填写 1-5 分满意度")

    ticket.status = TICKET_STATUS_CLOSED
    ticket.closed_at = _now()
    _add_record(db, ticket, user, "close", "关闭工单")
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def reopen_ticket(
    db: Session, user: User, ticket_id: int, payload: TicketReopenRequest
) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    if not _can_confirm(user, ticket):
        raise HTTPException(status_code=403, detail="仅发起人可重开（系统管理员可应急代办）")
    if not _can_reopen(ticket):
        raise HTTPException(status_code=400, detail="仅关闭后 3 个工作日内可重开")

    ticket.status = TICKET_STATUS_PENDING_ACCEPT if ticket.assignee_id else TICKET_STATUS_PENDING_ASSIGN
    ticket.closed_at = None
    ticket.completed_at = None
    ticket.result = None
    ticket.satisfaction = None
    ticket.satisfaction_comment = None
    ticket.sla_paused_at = None
    ticket.sla_remind_level = 0
    ticket.escalated_level = 0
    sla_hours = TICKET_SLA_HOURS.get(ticket.ticket_type, 72)
    ticket.due_at = _now() + timedelta(hours=sla_hours)
    _add_record(db, ticket, user, "reopen", payload.reason.strip())
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def comment_ticket(
    db: Session, user: User, ticket_id: int, payload: TicketCommentRequest
) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    assert_can_view(user, ticket)
    if ticket.status == TICKET_STATUS_CLOSED:
        raise HTTPException(status_code=400, detail="已关闭工单不可评论")
    _add_record(db, ticket, user, "comment", payload.content.strip())
    db.commit()
    db.refresh(ticket)
    return enrich_detail(db, ticket, user=user)


def list_assignee_options(db: Session, department_id: Optional[int] = None) -> list[dict]:
    q = db.query(User).filter(User.is_active.is_(True))
    if department_id:
        q = q.filter(User.department_id == department_id)
    users = q.order_by(User.id.asc()).limit(200).all()
    return [
        {
            "id": u.id,
            "name": u.real_name or u.username,
            "department_id": u.department_id,
        }
        for u in users
    ]


def scan_sla(db: Session, actor: User) -> dict:
    """扫描未关闭工单：50%/80% 提醒与超时逐级升级，写入流转记录。"""
    open_statuses = {
        TICKET_STATUS_PENDING_ASSIGN,
        TICKET_STATUS_PENDING_ACCEPT,
        TICKET_STATUS_PROCESSING,
    }
    tickets = db.query(Ticket).filter(Ticket.status.in_(open_statuses)).all()
    reminded_50 = reminded_80 = escalated_l1 = escalated_l2 = 0

    for ticket in tickets:
        ratio = _sla_used_ratio(ticket) or 0.0
        overdue = _is_overdue(ticket)

        # SLA 时限提醒只更新状态，不再写入流转时间线（避免刷屏 & 无意义的"某某 SLA 提醒"）
        if ratio >= 0.5 and ticket.sla_remind_level < 1:
            ticket.sla_remind_level = 1
            reminded_50 += 1
        if ratio >= 0.8 and ticket.sla_remind_level < 2:
            ticket.sla_remind_level = 2
            reminded_80 += 1

        if overdue and ticket.escalated_level < 1:
            ticket.escalated_level = 1
            mgr = _find_dept_manager(db, ticket.department_id)
            mgr_name = _user_name(db, mgr.id) if mgr else "承接部门负责人"
            _add_record(db, ticket, actor, "escalate_l1", f"超时升级至承接部门负责人：{mgr_name}")
            escalated_l1 += 1
        elif overdue and ticket.escalated_level < 2:
            # 二级：项目负责人或发起人部门负责人
            target_name = None
            if ticket.project_id:
                project = db.query(Project).filter(Project.id == ticket.project_id).first()
                if project and project.manager_id:
                    target_name = _user_name(db, project.manager_id)
            if not target_name:
                creator = db.query(User).filter(User.id == ticket.creator_id).first()
                mgr = _find_dept_manager(db, creator.department_id if creator else None)
                target_name = _user_name(db, mgr.id) if mgr else _user_name(db, ticket.creator_id)
            ticket.escalated_level = 2
            _add_record(
                db,
                ticket,
                actor,
                "escalate_l2",
                f"超时二级升级至业务负责人：{target_name or '业务负责人'}",
            )
            escalated_l2 += 1

    db.commit()
    return {
        "scanned": len(tickets),
        "reminded_50": reminded_50,
        "reminded_80": reminded_80,
        "escalated_l1": escalated_l1,
        "escalated_l2": escalated_l2,
    }


def ticket_stats(db: Session, user: User) -> dict:
    _, all_items = list_tickets(db, user, page=1, page_size=10000)
    _, created = list_tickets(db, user, scope_filter="mine_created", page=1, page_size=10000)
    _, assigned = list_tickets(db, user, scope_filter="mine_assigned", page=1, page_size=10000)

    now = _now()
    month_avg = (
        db.query(func.avg(Ticket.satisfaction))
        .filter(
            Ticket.satisfaction.isnot(None),
            extract("year", Ticket.closed_at) == now.year,
            extract("month", Ticket.closed_at) == now.month,
        )
        .scalar()
    )

    return {
        "total": len(all_items),
        "pending_assign": sum(
            1 for x in all_items if x.status == TICKET_STATUS_PENDING_ASSIGN
        ),
        "pending_accept": sum(
            1 for x in all_items if x.status == TICKET_STATUS_PENDING_ACCEPT
        ),
        "processing": sum(1 for x in all_items if x.status == TICKET_STATUS_PROCESSING),
        "pending_confirm": sum(
            1 for x in all_items if x.status == TICKET_STATUS_PENDING_CONFIRM
        ),
        "completed": sum(1 for x in all_items if x.status == TICKET_STATUS_COMPLETED),
        "closed": sum(1 for x in all_items if x.status == TICKET_STATUS_CLOSED),
        "overdue": sum(1 for x in all_items if getattr(x, "is_overdue", False)),
        "near_sla": sum(1 for x in all_items if getattr(x, "is_near_sla", False)),
        "mine_created": len(created),
        "mine_assigned": len(assigned),
        "satisfaction_avg": round(float(month_avg), 1) if month_avg is not None else None,
        "escalated": sum(1 for x in all_items if (x.escalated_level or 0) > 0),
    }
