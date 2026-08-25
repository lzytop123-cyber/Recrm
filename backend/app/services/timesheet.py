"""
工时业务逻辑：登记、提交、审批/驳回、列表统计。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.rbac import resolve_data_scope, user_can
from app.models.project import Project
from app.models.timesheet import (
    TIMESHEET_STATUS_APPROVED,
    TIMESHEET_STATUS_DRAFT,
    TIMESHEET_STATUS_REJECTED,
    TIMESHEET_STATUS_SUBMITTED,
    TIMESHEET_TYPE_PROJECT,
    TIMESHEET_TYPES,
    Timesheet,
)
from app.models.user import User
from app.schemas.timesheet import TimesheetCreate, TimesheetRejectRequest, TimesheetUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return None
    return u.real_name or u.username


def enrich_timesheet(db: Session, ts: Timesheet) -> Timesheet:
    ts.user_name = _user_name(db, ts.user_id)  # type: ignore[attr-defined]
    ts.approver_name = _user_name(db, ts.approver_id)  # type: ignore[attr-defined]
    if ts.project_id:
        project = db.query(Project).filter(Project.id == ts.project_id).first()
        ts.project_no = project.project_no if project else None  # type: ignore[attr-defined]
        ts.project_name = project.name if project else None  # type: ignore[attr-defined]
    else:
        ts.project_no = None  # type: ignore[attr-defined]
        ts.project_name = None  # type: ignore[attr-defined]
    from app.services import approval_flow

    open_id = approval_flow.find_open_item_id(db, "timesheet", ts.id)
    ts.approval_in_center = open_id is not None  # type: ignore[attr-defined]
    ts.open_approval_id = open_id  # type: ignore[attr-defined]
    return ts


def assert_can_view(user: User, ts: Timesheet) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes:
        return
    if ts.user_id == user.id:
        return
    scope = resolve_data_scope(user, "timesheet")
    if scope == "company":
        return
    if scope == "department" and user.department_id and ts.department_id == user.department_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该工时")


def can_approve(user: User) -> bool:
    if user_can(user, "timesheet:approve"):
        return True
    return "admin" in {r.code for r in user.roles}


def create_timesheet(db: Session, user: User, payload: TimesheetCreate) -> Timesheet:
    if payload.work_type not in TIMESHEET_TYPES:
        raise HTTPException(status_code=400, detail="无效的工时类型")
    if payload.work_type == TIMESHEET_TYPE_PROJECT and not payload.project_id:
        raise HTTPException(status_code=400, detail="项目工时必须关联项目")
    if payload.project_id:
        project = db.query(Project).filter(Project.id == payload.project_id).first()
        if not project:
            raise HTTPException(status_code=400, detail="项目不存在")

    ts = Timesheet(
        user_id=user.id,
        work_date=payload.work_date,
        hours=payload.hours,
        work_type=payload.work_type,
        project_id=payload.project_id,
        content=payload.content.strip(),
        status=TIMESHEET_STATUS_DRAFT,
        department_id=user.department_id,
        remark=payload.remark,
    )
    db.add(ts)
    db.commit()
    db.refresh(ts)
    return enrich_timesheet(db, ts)


def update_timesheet(db: Session, user: User, ts_id: int, payload: TimesheetUpdate) -> Timesheet:
    ts = db.query(Timesheet).filter(Timesheet.id == ts_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="工时记录不存在")
    assert_can_view(user, ts)
    if ts.user_id != user.id and "admin" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="只能编辑自己的工时")
    if ts.status not in {TIMESHEET_STATUS_DRAFT, TIMESHEET_STATUS_REJECTED}:
        raise HTTPException(status_code=400, detail="仅草稿或已驳回可编辑")

    data = payload.model_dump(exclude_unset=True)
    if "work_type" in data and data["work_type"] not in TIMESHEET_TYPES:
        raise HTTPException(status_code=400, detail="无效的工时类型")
    work_type = data.get("work_type", ts.work_type)
    project_id = data.get("project_id", ts.project_id)
    if work_type == TIMESHEET_TYPE_PROJECT and not project_id:
        raise HTTPException(status_code=400, detail="项目工时必须关联项目")
    if "project_id" in data and data["project_id"]:
        project = db.query(Project).filter(Project.id == data["project_id"]).first()
        if not project:
            raise HTTPException(status_code=400, detail="项目不存在")

    for k, v in data.items():
        setattr(ts, k, v)
    if ts.status == TIMESHEET_STATUS_REJECTED:
        ts.status = TIMESHEET_STATUS_DRAFT
        ts.reject_reason = None
    db.commit()
    db.refresh(ts)
    return enrich_timesheet(db, ts)


def list_timesheets(
    db: Session,
    user: User,
    *,
    status: Optional[str] = None,
    work_type: Optional[str] = None,
    project_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    scope_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Timesheet]]:
    q = db.query(Timesheet)
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    scope = resolve_data_scope(user, "timesheet")

    if scope_filter == "mine":
        q = q.filter(Timesheet.user_id == user.id)
    elif not is_admin:
        if scope == "personal":
            q = q.filter(Timesheet.user_id == user.id)
        elif scope == "department" and user.department_id:
            q = q.filter(
                or_(Timesheet.department_id == user.department_id, Timesheet.user_id == user.id)
            )

    if status:
        q = q.filter(Timesheet.status == status)
    if work_type:
        q = q.filter(Timesheet.work_type == work_type)
    if project_id:
        q = q.filter(Timesheet.project_id == project_id)
    if date_from:
        q = q.filter(Timesheet.work_date >= date_from)
    if date_to:
        q = q.filter(Timesheet.work_date <= date_to)

    total = q.count()
    items = (
        q.order_by(Timesheet.work_date.desc(), Timesheet.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, [enrich_timesheet(db, x) for x in items]


def get_timesheet(db: Session, user: User, ts_id: int) -> Timesheet:
    ts = db.query(Timesheet).filter(Timesheet.id == ts_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="工时记录不存在")
    assert_can_view(user, ts)
    return enrich_timesheet(db, ts)


def submit_timesheet(db: Session, user: User, ts_id: int) -> Timesheet:
    ts = db.query(Timesheet).filter(Timesheet.id == ts_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="工时记录不存在")
    if ts.user_id != user.id and "admin" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="只能提交自己的工时")
    if ts.status not in {TIMESHEET_STATUS_DRAFT, TIMESHEET_STATUS_REJECTED}:
        raise HTTPException(status_code=400, detail="仅草稿或已驳回可提交")
    ts.status = TIMESHEET_STATUS_SUBMITTED
    ts.reject_reason = None

    # AP-15 工时月度审批：部门负责人审批
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "timesheet", ts.id) is None and \
            approval_flow.select_rule(db, "timesheet", {}) is not None:
        approval_flow.start_instance(
            db,
            biz_type="timesheet",
            biz_id=ts.id,
            initiator=user,
            title=f"工时 {ts.work_date} · {ts.hours}h",
            summary=(ts.content or None),
            department_id=ts.department_id,
            deep_link=f"/timesheets/{ts.id}",
            commit=False,
        )
    db.commit()
    db.refresh(ts)
    return enrich_timesheet(db, ts)


def on_timesheet_flow_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-15 终审回调：直接落工时状态（引擎已授权，避免二次范围校验）。"""
    from app.services import approval_flow

    ts = db.query(Timesheet).filter(Timesheet.id == instance.biz_id).first()
    if not ts or ts.status != TIMESHEET_STATUS_SUBMITTED:
        return
    if withdrawn:
        ts.status = TIMESHEET_STATUS_DRAFT
    elif approved:
        ts.status = TIMESHEET_STATUS_APPROVED
        ts.approver_id = approval_flow.last_actor_id(instance)
        ts.approved_at = _now()
        ts.reject_reason = None
    else:
        ts.status = TIMESHEET_STATUS_REJECTED
        ts.approver_id = approval_flow.last_actor_id(instance)
        ts.approved_at = _now()
        ts.reject_reason = instance.reject_reason or "审批驳回"


def approve_timesheet(db: Session, user: User, ts_id: int) -> Timesheet:
    if not can_approve(user):
        raise HTTPException(status_code=403, detail="无权审批工时")
    ts = db.query(Timesheet).filter(Timesheet.id == ts_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="工时记录不存在")
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "timesheet", ts.id) is not None:
        raise HTTPException(status_code=409, detail="该工时已进入审批流程，请在审批中心处理")
    assert_can_view(user, ts)
    if ts.status != TIMESHEET_STATUS_SUBMITTED:
        raise HTTPException(status_code=400, detail="仅待审批工时可审批")
    ts.status = TIMESHEET_STATUS_APPROVED
    ts.approver_id = user.id
    ts.approved_at = _now()
    ts.reject_reason = None
    db.commit()
    db.refresh(ts)
    return enrich_timesheet(db, ts)


def reject_timesheet(
    db: Session, user: User, ts_id: int, payload: TimesheetRejectRequest
) -> Timesheet:
    if not can_approve(user):
        raise HTTPException(status_code=403, detail="无权驳回工时")
    ts = db.query(Timesheet).filter(Timesheet.id == ts_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="工时记录不存在")
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "timesheet", ts.id) is not None:
        raise HTTPException(status_code=409, detail="该工时已进入审批流程，请在审批中心处理")
    assert_can_view(user, ts)
    if ts.status != TIMESHEET_STATUS_SUBMITTED:
        raise HTTPException(status_code=400, detail="仅待审批工时可驳回")
    ts.status = TIMESHEET_STATUS_REJECTED
    ts.approver_id = user.id
    ts.approved_at = _now()
    ts.reject_reason = payload.reason
    db.commit()
    db.refresh(ts)
    return enrich_timesheet(db, ts)


def timesheet_stats(db: Session, user: User) -> dict:
    _, all_items = list_timesheets(db, user, page=1, page_size=10000)
    _, mine_items = list_timesheets(db, user, scope_filter="mine", page=1, page_size=10000)

    def _sum_hours(items: list[Timesheet], *, status: Optional[str] = None) -> Decimal:
        total = Decimal("0")
        for x in items:
            if status and x.status != status:
                continue
            total += x.hours or Decimal("0")
        return total

    return {
        "total": len(all_items),
        "draft": sum(1 for x in all_items if x.status == TIMESHEET_STATUS_DRAFT),
        "submitted": sum(1 for x in all_items if x.status == TIMESHEET_STATUS_SUBMITTED),
        "approved": sum(1 for x in all_items if x.status == TIMESHEET_STATUS_APPROVED),
        "rejected": sum(1 for x in all_items if x.status == TIMESHEET_STATUS_REJECTED),
        "mine": len(mine_items),
        "my_hours": _sum_hours(mine_items),
        "approved_hours": _sum_hours(all_items, status=TIMESHEET_STATUS_APPROVED),
    }
