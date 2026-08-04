"""
排期业务逻辑：申请、确认、协调、开始、完成（写工时）、取消、冲突与负载。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

try:
    from zoneinfo import ZoneInfo

    _APP_TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # pragma: no cover
    _APP_TZ = timezone(timedelta(hours=8))

from app.core.rbac import collect_data_scopes, widest_data_scope
from app.models.project import Project, ProjectTask
from app.models.schedule import (
    FEISHU_SYNC_PENDING,
    SCHEDULE_ACTIVE_STATUSES,
    SCHEDULE_RESOURCE_OTHER,
    SCHEDULE_RESOURCE_TYPES,
    SCHEDULE_STATUS_CANCELLED,
    SCHEDULE_STATUS_COMPLETED,
    SCHEDULE_STATUS_CONFIRMED,
    SCHEDULE_STATUS_IN_PROGRESS,
    SCHEDULE_STATUS_PENDING,
    SCHEDULE_TYPE_OTHER,
    SCHEDULE_TYPES,
    Schedule,
)
from app.models.ticket import Ticket
from app.models.timesheet import (
    TIMESHEET_STATUS_DRAFT,
    TIMESHEET_TYPE_PROJECT,
    TIMESHEET_TYPE_TRAINING,
    Timesheet,
)
from app.models.user import User
from app.schemas.schedule import (
    ScheduleCancelRequest,
    ScheduleCompleteRequest,
    ScheduleCoordinateRequest,
    ScheduleCreate,
    ScheduleUpdate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """统一为 UTC。无时区的时间按业务时区 Asia/Shanghai 解释（前端表单墙钟时间）。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_APP_TZ).astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return None
    return u.real_name or u.username


def _planned_hours(item: Schedule) -> float:
    start = _as_utc(item.start_time)
    end = _as_utc(item.end_time)
    return max(0.0, round((end - start).total_seconds() / 3600, 2))


def _find_conflicts(
    db: Session,
    *,
    employee_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_id: Optional[int] = None,
) -> list[Schedule]:
    start = _as_utc(start_time)
    end = _as_utc(end_time)
    q = db.query(Schedule).filter(
        Schedule.employee_id == employee_id,
        Schedule.status.in_(list(SCHEDULE_ACTIVE_STATUSES)),
        Schedule.start_time < end,
        Schedule.end_time > start,
    )
    if exclude_id:
        q = q.filter(Schedule.id != exclude_id)
    return q.order_by(Schedule.start_time.asc()).all()


def enrich_schedule(db: Session, item: Schedule, *, with_conflicts: bool = True) -> Schedule:
    item.employee_name = _user_name(db, item.employee_id)  # type: ignore[attr-defined]
    item.creator_name = _user_name(db, item.creator_id)  # type: ignore[attr-defined]
    item.confirmed_by_name = _user_name(db, item.confirmed_by)  # type: ignore[attr-defined]
    item.planned_hours = _planned_hours(item)  # type: ignore[attr-defined]
    if item.project_id:
        project = db.query(Project).filter(Project.id == item.project_id).first()
        item.project_no = project.project_no if project else None  # type: ignore[attr-defined]
        item.project_name = project.name if project else None  # type: ignore[attr-defined]
    else:
        item.project_no = None  # type: ignore[attr-defined]
        item.project_name = None  # type: ignore[attr-defined]
    if item.project_task_id:
        task = db.query(ProjectTask).filter(ProjectTask.id == item.project_task_id).first()
        item.task_no = task.task_no if task else None  # type: ignore[attr-defined]
        item.task_title = task.title if task else None  # type: ignore[attr-defined]
    else:
        item.task_no = None  # type: ignore[attr-defined]
        item.task_title = None  # type: ignore[attr-defined]
    if item.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == item.ticket_id).first()
        item.ticket_no = ticket.ticket_no if ticket else None  # type: ignore[attr-defined]
    else:
        item.ticket_no = None  # type: ignore[attr-defined]

    conflicts: list[dict] = []
    if with_conflicts and item.status in SCHEDULE_ACTIVE_STATUSES:
        for c in _find_conflicts(
            db,
            employee_id=item.employee_id,
            start_time=item.start_time,
            end_time=item.end_time,
            exclude_id=item.id,
        ):
            conflicts.append(
                {
                    "id": c.id,
                    "title": c.title,
                    "start_time": c.start_time,
                    "end_time": c.end_time,
                    "status": c.status,
                }
            )
    item.has_conflict = bool(conflicts)  # type: ignore[attr-defined]
    item.conflicts = conflicts  # type: ignore[attr-defined]
    return item


def assert_can_view(user: User, item: Schedule) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes:
        return
    if item.employee_id == user.id or item.creator_id == user.id:
        return
    scope = widest_data_scope(collect_data_scopes(user))
    if scope == "company":
        return
    if scope == "department" and user.department_id and item.department_id == user.department_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该排期")


def can_manage(user: User) -> bool:
    role_codes = {r.code for r in user.roles}
    return bool(
        "admin" in role_codes
        or "middle_manager" in role_codes
        or "executive" in role_codes
        or "delivery_lead" in role_codes
    )


def _validate_time_range(start_time: datetime, end_time: datetime) -> None:
    start = _as_utc(start_time)
    end = _as_utc(end_time)
    if end <= start:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")


def create_schedule(db: Session, user: User, payload: ScheduleCreate) -> Schedule:
    resource_type = payload.resource_type or SCHEDULE_RESOURCE_OTHER
    if resource_type not in SCHEDULE_RESOURCE_TYPES:
        raise HTTPException(status_code=400, detail="无效的资源类型")
    schedule_type = payload.schedule_type or SCHEDULE_TYPE_OTHER
    if schedule_type not in SCHEDULE_TYPES:
        raise HTTPException(status_code=400, detail="无效的排期类型")
    _validate_time_range(payload.start_time, payload.end_time)

    employee = db.query(User).filter(User.id == payload.employee_id, User.is_active.is_(True)).first()
    if not employee:
        raise HTTPException(status_code=400, detail="被排期人员不存在或已停用")

    project_id = payload.project_id
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=400, detail="项目不存在")

    project_task_id = payload.project_task_id
    if project_task_id:
        task = db.query(ProjectTask).filter(ProjectTask.id == project_task_id).first()
        if not task:
            raise HTTPException(status_code=400, detail="项目任务不存在")
        if project_id and task.project_id != project_id:
            raise HTTPException(status_code=400, detail="任务不属于所选项目")
        if not project_id:
            project_id = task.project_id

    if payload.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=400, detail="工单不存在")

    item = Schedule(
        title=payload.title.strip(),
        schedule_type=schedule_type,
        resource_type=resource_type,
        employee_id=employee.id,
        project_id=project_id,
        project_task_id=project_task_id,
        ticket_id=payload.ticket_id,
        start_time=_as_utc(payload.start_time),
        end_time=_as_utc(payload.end_time),
        status=SCHEDULE_STATUS_PENDING,
        creator_id=user.id,
        department_id=user.department_id,
        location=payload.location,
        content=payload.content,
        remark=payload.remark,
        feishu_sync_status=FEISHU_SYNC_PENDING,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return enrich_schedule(db, item)


def update_schedule(db: Session, user: User, schedule_id: int, payload: ScheduleUpdate) -> Schedule:
    item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="排期不存在")
    assert_can_view(user, item)
    if item.creator_id != user.id and not can_manage(user):
        raise HTTPException(status_code=403, detail="仅申请人或管理者可编辑")
    if item.status not in {SCHEDULE_STATUS_PENDING, SCHEDULE_STATUS_CONFIRMED}:
        raise HTTPException(status_code=400, detail="仅待确认/已确认排期可编辑")

    data = payload.model_dump(exclude_unset=True)
    if "resource_type" in data and data["resource_type"] not in SCHEDULE_RESOURCE_TYPES:
        raise HTTPException(status_code=400, detail="无效的资源类型")
    if "schedule_type" in data and data["schedule_type"] not in SCHEDULE_TYPES:
        raise HTTPException(status_code=400, detail="无效的排期类型")
    if "employee_id" in data:
        employee = (
            db.query(User).filter(User.id == data["employee_id"], User.is_active.is_(True)).first()
        )
        if not employee:
            raise HTTPException(status_code=400, detail="被排期人员不存在或已停用")
    if "project_id" in data and data["project_id"]:
        project = db.query(Project).filter(Project.id == data["project_id"]).first()
        if not project:
            raise HTTPException(status_code=400, detail="项目不存在")
    if "title" in data and data["title"]:
        data["title"] = data["title"].strip()
    if "start_time" in data:
        data["start_time"] = _as_utc(data["start_time"])
    if "end_time" in data:
        data["end_time"] = _as_utc(data["end_time"])

    for k, v in data.items():
        setattr(item, k, v)
    _validate_time_range(item.start_time, item.end_time)
    # 变更后需重新确认
    if item.status == SCHEDULE_STATUS_CONFIRMED:
        item.status = SCHEDULE_STATUS_PENDING
        item.confirmed_by = None
        item.confirmed_at = None
        item.feishu_sync_status = FEISHU_SYNC_PENDING

    db.commit()
    db.refresh(item)
    return enrich_schedule(db, item)


def list_schedules(
    db: Session,
    user: User,
    *,
    status: Optional[str] = None,
    resource_type: Optional[str] = None,
    employee_id: Optional[int] = None,
    project_id: Optional[int] = None,
    project_task_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    scope_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Schedule]]:
    q = db.query(Schedule)
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    scope = widest_data_scope(collect_data_scopes(user)) if not is_admin else "company"

    if scope_filter == "mine":
        q = q.filter(or_(Schedule.employee_id == user.id, Schedule.creator_id == user.id))
    elif not is_admin:
        if scope == "personal":
            q = q.filter(or_(Schedule.employee_id == user.id, Schedule.creator_id == user.id))
        elif scope == "department" and user.department_id:
            q = q.filter(
                or_(
                    Schedule.department_id == user.department_id,
                    Schedule.employee_id == user.id,
                    Schedule.creator_id == user.id,
                )
            )

    if status:
        q = q.filter(Schedule.status == status)
    if resource_type:
        q = q.filter(Schedule.resource_type == resource_type)
    if employee_id:
        q = q.filter(Schedule.employee_id == employee_id)
    if project_id:
        q = q.filter(Schedule.project_id == project_id)
    if project_task_id:
        q = q.filter(Schedule.project_task_id == project_task_id)
    if date_from:
        q = q.filter(Schedule.end_time >= _as_utc(date_from))
    if date_to:
        q = q.filter(Schedule.start_time <= _as_utc(date_to))

    total = q.count()
    items = (
        q.order_by(Schedule.start_time.asc(), Schedule.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, [enrich_schedule(db, x) for x in items]


def get_schedule(db: Session, user: User, schedule_id: int) -> Schedule:
    item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="排期不存在")
    assert_can_view(user, item)
    return enrich_schedule(db, item)


def confirm_schedule(db: Session, user: User, schedule_id: int) -> Schedule:
    item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="排期不存在")
    assert_can_view(user, item)
    # 本人可确认档期；管理者也可确认
    if item.employee_id != user.id and not can_manage(user):
        raise HTTPException(status_code=403, detail="仅资源本人或管理者可确认")
    if item.status != SCHEDULE_STATUS_PENDING:
        raise HTTPException(status_code=400, detail="仅待确认排期可确认")

    conflicts = _find_conflicts(
        db,
        employee_id=item.employee_id,
        start_time=item.start_time,
        end_time=item.end_time,
        exclude_id=item.id,
    )
    hard = [c for c in conflicts if c.status in {SCHEDULE_STATUS_CONFIRMED, SCHEDULE_STATUS_IN_PROGRESS}]
    if hard:
        titles = "、".join(c.title for c in hard[:3])
        raise HTTPException(status_code=400, detail=f"存在时间冲突，无法确认：{titles}")

    item.status = SCHEDULE_STATUS_CONFIRMED
    item.confirmed_by = user.id
    item.confirmed_at = _now()
    item.feishu_sync_status = FEISHU_SYNC_PENDING
    db.commit()
    db.refresh(item)
    return enrich_schedule(db, item)


def request_coordination(
    db: Session, user: User, schedule_id: int, payload: ScheduleCoordinateRequest
) -> Schedule:
    item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="排期不存在")
    assert_can_view(user, item)
    if item.employee_id != user.id and not can_manage(user):
        raise HTTPException(status_code=403, detail="仅资源本人或管理者可请求协调")
    if item.status != SCHEDULE_STATUS_PENDING:
        raise HTTPException(status_code=400, detail="仅待确认排期可请求协调")
    item.coordination_note = payload.note.strip()
    db.commit()
    db.refresh(item)
    return enrich_schedule(db, item)


def start_schedule(db: Session, user: User, schedule_id: int) -> Schedule:
    item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="排期不存在")
    assert_can_view(user, item)
    if item.employee_id != user.id and not can_manage(user):
        raise HTTPException(status_code=403, detail="仅资源本人或管理者可开始")
    if item.status != SCHEDULE_STATUS_CONFIRMED:
        raise HTTPException(status_code=400, detail="仅已确认排期可开始")
    item.status = SCHEDULE_STATUS_IN_PROGRESS
    db.commit()
    db.refresh(item)
    return enrich_schedule(db, item)


def complete_schedule(
    db: Session,
    user: User,
    schedule_id: int,
    payload: Optional[ScheduleCompleteRequest] = None,
) -> Schedule:
    item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="排期不存在")
    assert_can_view(user, item)
    if item.employee_id != user.id and not can_manage(user):
        raise HTTPException(status_code=403, detail="仅资源本人或管理者可完成")
    if item.status not in {SCHEDULE_STATUS_CONFIRMED, SCHEDULE_STATUS_IN_PROGRESS}:
        raise HTTPException(status_code=400, detail="仅已确认/进行中排期可完成")

    if payload:
        item.result = payload.result.strip()
        item.actual_hours = payload.actual_hours
        if payload.create_timesheet and not item.timesheet_id:
            work_type = (
                TIMESHEET_TYPE_TRAINING
                if item.schedule_type in {"internal_training", "external_salon"}
                else TIMESHEET_TYPE_PROJECT
            )
            ts = Timesheet(
                user_id=item.employee_id,
                work_date=_as_utc(item.start_time).date(),
                hours=payload.actual_hours,
                work_type=work_type if item.project_id or work_type == TIMESHEET_TYPE_TRAINING else TIMESHEET_TYPE_PROJECT,
                project_id=item.project_id,
                content=f"[排期#{item.id}] {item.title}：{payload.result.strip()}",
                status=TIMESHEET_STATUS_DRAFT,
                department_id=item.department_id,
                remark=f"由排期自动生成，计划 {_planned_hours(item)}h / 实际 {payload.actual_hours}h",
            )
            db.add(ts)
            db.flush()
            item.timesheet_id = ts.id

    item.status = SCHEDULE_STATUS_COMPLETED

    # 轻量痕迹：写回任务/项目备注，不改进度
    try:
        who = _user_name(db, item.employee_id) or "—"
        start_local = _as_utc(item.start_time).astimezone(_APP_TZ)
        end_local = _as_utc(item.end_time).astimezone(_APP_TZ)
        trail = (
            f"[排期完成] {start_local.strftime('%m-%d %H:%M')}-"
            f"{end_local.strftime('%H:%M')} · {who} · {item.title}"
        )
        if item.project_task_id:
            task = db.query(ProjectTask).filter(ProjectTask.id == item.project_task_id).first()
            if task:
                prev = (task.remark or "").rstrip()
                task.remark = f"{prev}\n{trail}".strip() if prev else trail
        if item.project_id:
            project = db.query(Project).filter(Project.id == item.project_id).first()
            if project:
                prev = (project.remark or "").rstrip()
                project.remark = f"{prev}\n{trail}".strip() if prev else trail
    except Exception:
        pass

    db.commit()
    db.refresh(item)
    return enrich_schedule(db, item)


def cancel_schedule(
    db: Session, user: User, schedule_id: int, payload: ScheduleCancelRequest
) -> Schedule:
    item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="排期不存在")
    assert_can_view(user, item)
    if item.creator_id != user.id and item.employee_id != user.id and not can_manage(user):
        raise HTTPException(status_code=403, detail="仅申请人、资源本人或管理者可取消")
    if item.status in {SCHEDULE_STATUS_COMPLETED, SCHEDULE_STATUS_CANCELLED}:
        raise HTTPException(status_code=400, detail="已完成/已取消排期不可再取消")
    item.status = SCHEDULE_STATUS_CANCELLED
    item.cancel_reason = payload.reason
    db.commit()
    db.refresh(item)
    return enrich_schedule(db, item)


def list_resource_options(db: Session) -> list[dict]:
    users = (
        db.query(User)
        .filter(User.is_active.is_(True))
        .order_by(User.id.asc())
        .limit(200)
        .all()
    )
    return [{"id": u.id, "name": u.real_name or u.username} for u in users]


def resource_load(
    db: Session,
    user: User,
    *,
    resource_type: str,
    date_from: datetime,
    date_to: datetime,
) -> list[dict]:
    if resource_type not in SCHEDULE_RESOURCE_TYPES:
        raise HTTPException(status_code=400, detail="无效的资源类型")
    _, items = list_schedules(
        db,
        user,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
        page=1,
        page_size=100,
    )
    active = [x for x in items if x.status in SCHEDULE_ACTIVE_STATUSES | {SCHEDULE_STATUS_COMPLETED}]
    # 假定一周满负荷 40h
    capacity = 40.0
    buckets: dict[int, dict] = {}
    for x in active:
        b = buckets.setdefault(
            x.employee_id,
            {
                "employee_id": x.employee_id,
                "employee_name": getattr(x, "employee_name", None) or f"#{x.employee_id}",
                "resource_type": resource_type,
                "planned_hours": 0.0,
                "item_count": 0,
            },
        )
        b["planned_hours"] += float(getattr(x, "planned_hours", 0) or _planned_hours(x))
        b["item_count"] += 1
    out = []
    for b in buckets.values():
        hours = round(b["planned_hours"], 1)
        out.append(
            {
                **b,
                "planned_hours": hours,
                "load_percent": min(100, int(round(hours * 100 / capacity))) if capacity else 0,
            }
        )
    out.sort(key=lambda x: x["load_percent"], reverse=True)
    return out


def schedule_stats(db: Session, user: User) -> dict:
    _, all_items = list_schedules(db, user, page=1, page_size=10000)
    _, mine_items = list_schedules(db, user, scope_filter="mine", page=1, page_size=10000)
    return {
        "total": len(all_items),
        "pending": sum(1 for x in all_items if x.status == SCHEDULE_STATUS_PENDING),
        "confirmed": sum(1 for x in all_items if x.status == SCHEDULE_STATUS_CONFIRMED),
        "in_progress": sum(1 for x in all_items if x.status == SCHEDULE_STATUS_IN_PROGRESS),
        "completed": sum(1 for x in all_items if x.status == SCHEDULE_STATUS_COMPLETED),
        "cancelled": sum(1 for x in all_items if x.status == SCHEDULE_STATUS_CANCELLED),
        "conflict_count": sum(1 for x in all_items if getattr(x, "has_conflict", False)),
        "mine": len(mine_items),
    }
