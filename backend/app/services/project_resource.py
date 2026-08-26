"""
立项资源确认：按项目类型生成需求角色，部门确认投入，并做简单排期冲突检查。
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.project import (
    PROJECT_STATUS_INITIATING,
    PROJECT_STATUS_PLANNING,
    RESOURCE_NEED_ACCEPTED,
    RESOURCE_NEED_PENDING,
    RESOURCE_NEED_REJECTED,
    SCHEDULE_CHECK_CLEAR,
    SCHEDULE_CHECK_CONFLICT,
    SCHEDULE_CHECK_PENDING,
    Project,
    ProjectResourceNeed,
    ProjectTask,
)
from app.models.schedule import SCHEDULE_ACTIVE_STATUSES, Schedule
from app.models.user import User
from app.schemas.project_resource import (
    ResourceConfirmRequest,
    ResourceRoleAssignment,
    ResourceRoleMemberOut,
    ResourceRoleOptionOut,
    ResourceRoleOptionsOut,
)
from app.services.project import assert_can_operate, assert_can_view

# 旧版角色名 → 默认投入（新流程以飞书部门名为准）
ROLE_CATALOG: dict[str, dict] = {
    "产品角色": {"department_name": "交付部", "planned_hours": 40},
    "技术负责人": {"department_name": "技术支持", "planned_hours": 160},
    "开发": {"department_name": "技术支持", "planned_hours": 120},
    "测试": {"department_name": "技术支持", "planned_hours": 80},
    "讲师": {"department_name": "讲师部", "planned_hours": 16},
    "实施顾问": {"department_name": "交付部", "planned_hours": 80},
    "内容运营": {"department_name": "新媒体部", "planned_hours": 80},
    "交付经理": {"department_name": "交付部", "planned_hours": 40},
}

# 按交付类型匹配飞书部门名的关键词（含即命中）
DEPT_HINTS: dict[str, list[str]] = {
    "ai_custom": ["讲师", "技术", "交付", "研发", "产品", "AI"],
    "ai_product": ["讲师", "交付", "实施"],
    "media_ops": ["新媒体", "运营", "内容"],
    "other": ["交付", "项目"],
}

# 无飞书部门时的兜底默认名
ROLE_DEFAULTS: dict[str, list[str]] = {
    "ai_custom": ["产品角色", "技术负责人", "开发", "测试", "讲师"],
    "ai_product": ["实施顾问", "讲师"],
    "media_ops": ["内容运营"],
    "other": ["交付经理"],
}

ROLE_TEMPLATES: dict[str, list[dict]] = {
    k: [{"role_name": name, **ROLE_CATALOG[name]} for name in names if name in ROLE_CATALOG]
    for k, names in ROLE_DEFAULTS.items()
}

DEFAULT_PLANNED_HOURS = Decimal("40")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    return (u.real_name or u.username) if u else None


def _dept_by_name(db: Session, name: str) -> Optional[Department]:
    return db.query(Department).filter(Department.name == name).first()


def _pick_member(db: Session, department_id: Optional[int], fallback_id: Optional[int]) -> Optional[int]:
    if department_id:
        u = (
            db.query(User)
            .filter(User.department_id == department_id, User.is_active.is_(True))
            .order_by(User.id.asc())
            .first()
        )
        if u:
            return u.id
    return fallback_id


def _member_out(u: User) -> ResourceRoleMemberOut:
    dept_name = u.department.name if u.department else None
    return ResourceRoleMemberOut(
        id=u.id,
        name=(u.real_name or u.username),
        department_name=dept_name,
        job_title=u.job_title,
    )


def _feishu_users(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.is_active.is_(True), User.feishu_open_id.isnot(None))
        .order_by(User.id.asc())
        .all()
    )


def _feishu_departments(db: Session) -> list[Department]:
    """飞书同步写入的部门：code 形如 FS_{open_department_id}。"""
    return (
        db.query(Department)
        .filter(Department.code.like("FS_%"))
        .order_by(Department.name.asc())
        .all()
    )


def list_resource_role_options(db: Session) -> ResourceRoleOptionsOut:
    """立项所需角色：飞书接口同步回来的真实部门 + 部门内可指定人员。"""
    users = _feishu_users(db)
    if not users:
        users = (
            db.query(User)
            .filter(User.is_active.is_(True))
            .order_by(User.id.asc())
            .all()
        )

    employees = [_member_out(u) for u in users]
    depts = _feishu_departments(db)
    if depts:
        by_dept: dict[int, list[User]] = {}
        for u in users:
            if u.department_id:
                by_dept.setdefault(u.department_id, []).append(u)
        roles = [
            ResourceRoleOptionOut(
                role_name=d.name,
                department_id=d.id,
                member_count=len(by_dept.get(d.id, [])),
                members=[_member_out(m) for m in by_dept.get(d.id, [])],
            )
            for d in depts
        ]
        return ResourceRoleOptionsOut(
            roles=roles,
            employees=employees,
            source="feishu_department",
            hint="（N人）为部门在册人数；指定对接人后，提交由该部门确认投入。",
        )

    # 尚未同步飞书部门时，回退本地目录
    roles = [
        ResourceRoleOptionOut(role_name=name, member_count=0, members=[])
        for name in ROLE_CATALOG.keys()
    ]
    return ResourceRoleOptionsOut(
        roles=roles,
        employees=employees,
        source="catalog_fallback",
        hint="尚未同步到飞书部门，暂用本地目录；请先在组织架构同步飞书通讯录。",
    )


def _resolve_department(
    db: Session, role_name: str, suggested_user_id: Optional[int]
) -> tuple[str, Optional[int]]:
    # 优先：飞书真实部门名
    dept = _dept_by_name(db, role_name)
    if dept:
        return dept.name, dept.id
    meta = ROLE_CATALOG.get(role_name)
    if meta:
        mapped = _dept_by_name(db, meta["department_name"])
        return meta["department_name"], mapped.id if mapped else None
    if suggested_user_id:
        u = db.query(User).filter(User.id == suggested_user_id).first()
        if u and u.department:
            return u.department.name, u.department_id
        if u and u.department_id:
            d = db.query(Department).filter(Department.id == u.department_id).first()
            if d:
                return d.name, d.id
    return "待分配", None


def _planned_hours_for(
    role_name: str, override: Optional[Decimal]
) -> Decimal:
    if override is not None:
        return override
    meta = ROLE_CATALOG.get(role_name)
    if meta:
        return Decimal(str(meta["planned_hours"]))
    return DEFAULT_PLANNED_HOURS


def _project_window(project: Project) -> tuple[datetime, datetime]:
    start_d = project.start_date or date.today()
    end_d = project.end_date or start_d
    start = datetime.combine(start_d, time.min, tzinfo=timezone.utc)
    end = datetime.combine(end_d, time.max, tzinfo=timezone.utc)
    return start, end


def refresh_schedule_check(db: Session, need: ProjectResourceNeed, project: Project) -> str:
    user_id = need.confirmed_user_id or need.suggested_user_id
    if not user_id:
        need.schedule_status = SCHEDULE_CHECK_PENDING
        return need.schedule_status

    win_start, win_end = _project_window(project)
    conflicts = (
        db.query(Schedule)
        .filter(
            Schedule.employee_id == user_id,
            Schedule.status.in_(list(SCHEDULE_ACTIVE_STATUSES)),
            Schedule.start_time < win_end,
            Schedule.end_time > win_start,
        )
        .count()
    )
    need.schedule_status = SCHEDULE_CHECK_CONFLICT if conflicts else SCHEDULE_CHECK_CLEAR
    return need.schedule_status


def enrich_need(db: Session, need: ProjectResourceNeed, project: Optional[Project] = None) -> ProjectResourceNeed:
    project = project or db.query(Project).filter(Project.id == need.project_id).first()
    need.project_no = project.project_no if project else None  # type: ignore[attr-defined]
    need.project_name = project.name if project else None  # type: ignore[attr-defined]
    need.suggested_user_name = _user_name(db, need.suggested_user_id)  # type: ignore[attr-defined]
    need.confirmed_user_name = _user_name(db, need.confirmed_user_id)  # type: ignore[attr-defined]
    need.confirmed_by_name = _user_name(db, need.confirmed_by)  # type: ignore[attr-defined]
    need.handler_role = (  # type: ignore[attr-defined]
        "部门负责人" if need.status == RESOURCE_NEED_PENDING else "已处理"
    )
    if project:
        refresh_schedule_check(db, need, project)
    return need


def seed_resource_needs(
    db: Session,
    project: Project,
    *,
    role_names: Optional[list[str]] = None,
    role_assignments: Optional[list[ResourceRoleAssignment]] = None,
    commit: bool = True,
) -> list[ProjectResourceNeed]:
    existing = (
        db.query(ProjectResourceNeed).filter(ProjectResourceNeed.project_id == project.id).count()
    )
    if existing:
        return (
            db.query(ProjectResourceNeed)
            .filter(ProjectResourceNeed.project_id == project.id)
            .order_by(ProjectResourceNeed.id.asc())
            .all()
        )

    assignments: list[ResourceRoleAssignment] = []
    if role_assignments:
        assignments = [a for a in role_assignments if (a.role_name or "").strip()]
    elif role_names:
        assignments = [
            ResourceRoleAssignment(role_name=n) for n in role_names if (n or "").strip()
        ]
    else:
        defaults = ROLE_DEFAULTS.get(project.project_type) or ROLE_DEFAULTS["other"]
        assignments = [ResourceRoleAssignment(role_name=n) for n in defaults]

    if not assignments:
        templates = ROLE_TEMPLATES.get(project.project_type) or ROLE_TEMPLATES["other"]
        assignments = [ResourceRoleAssignment(role_name=t["role_name"]) for t in templates]

    seen_users: set[int] = set()
    for asg in assignments:
        uid = asg.suggested_user_id
        if uid is None:
            continue
        if uid in seen_users:
            raise HTTPException(status_code=400, detail="对接人不能重复")
        seen_users.add(uid)

    created: list[ProjectResourceNeed] = []
    for asg in assignments:
        role_name = asg.role_name.strip()
        dept_name, dept_id = _resolve_department(db, role_name, asg.suggested_user_id)
        member_id = asg.suggested_user_id
        if member_id:
            member = db.query(User).filter(User.id == member_id, User.is_active.is_(True)).first()
            if not member:
                raise HTTPException(status_code=400, detail=f"指定人员不存在或已停用：{role_name}")
        else:
            member_id = _pick_member(db, dept_id, project.manager_id)
        need = ProjectResourceNeed(
            project_id=project.id,
            role_name=role_name,
            department_name=dept_name,
            department_id=dept_id,
            suggested_user_id=member_id,
            planned_hours=_planned_hours_for(role_name, asg.planned_hours),
            status=RESOURCE_NEED_PENDING,
            schedule_status=SCHEDULE_CHECK_PENDING,
        )
        refresh_schedule_check(db, need, project)
        db.add(need)
        created.append(need)
    if commit:
        db.commit()
        for n in created:
            db.refresh(n)
    else:
        db.flush()
    return created


def ensure_needs_for_initiating(db: Session) -> None:
    """批量补齐立项/计划中项目的资源需求。仅用于运维/迁移，勿在只读 GET 中调用。"""
    projects = (
        db.query(Project)
        .filter(Project.status.in_([PROJECT_STATUS_INITIATING, PROJECT_STATUS_PLANNING]))
        .all()
    )
    for p in projects:
        seed_resource_needs(db, p, commit=False)
    db.commit()


def list_pending_resources(
    db: Session,
    user: User,
    *,
    only_pending: bool = True,
    suggested_user_id: Optional[int] = None,
) -> list[ProjectResourceNeed]:
    """只读列出资源确认项。不会 seed / commit；缺口请在立项流转时 seed_resource_needs。"""
    _ = user
    q = (
        db.query(ProjectResourceNeed)
        .join(Project, Project.id == ProjectResourceNeed.project_id)
        .filter(Project.status.in_([PROJECT_STATUS_INITIATING, PROJECT_STATUS_PLANNING]))
    )
    if only_pending:
        q = q.filter(ProjectResourceNeed.status == RESOURCE_NEED_PENDING)
    if suggested_user_id is not None:
        q = q.filter(ProjectResourceNeed.suggested_user_id == suggested_user_id)
    needs = q.order_by(ProjectResourceNeed.id.desc()).all()
    # enrich 可能改 schedule_status，但本接口不 commit，避免 GET 写库
    return [enrich_need(db, n) for n in needs]


def pending_count_for_project(db: Session, project_id: int) -> int:
    return (
        db.query(ProjectResourceNeed)
        .filter(
            ProjectResourceNeed.project_id == project_id,
            ProjectResourceNeed.status == RESOURCE_NEED_PENDING,
        )
        .count()
    )


def confirm_resource(
    db: Session, user: User, need_id: int, payload: ResourceConfirmRequest
) -> ProjectResourceNeed:
    need = db.query(ProjectResourceNeed).filter(ProjectResourceNeed.id == need_id).first()
    if not need:
        raise HTTPException(status_code=404, detail="资源需求不存在")
    project = db.query(Project).filter(Project.id == need.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_operate(user, project)
    # 资源确认仅限部门负责人（或管理员代审）；防止销售等创建人越权确认
    _role_codes = {r.code for r in (user.roles or [])}
    if "admin" not in _role_codes and "dept_head" not in _role_codes:
        raise HTTPException(status_code=403, detail="仅部门负责人可确认资源投入")
    if need.status != RESOURCE_NEED_PENDING:
        raise HTTPException(status_code=400, detail="该资源需求已处理")

    action = payload.action
    if action not in {"accept", "adjust", "reject"}:
        raise HTTPException(status_code=400, detail="无效操作")

    note = (payload.note or "").strip()
    if action == "reject":
        if len(note) < 2:
            raise HTTPException(status_code=400, detail="拒绝时请填写说明")
        # 拒绝后该条不再计入预算，须仍覆盖已拆任务
        assert_resource_budget_covers_tasks(
            db, need.project_id, exclude_need_id=need.id, override_hours=None
        )
        need.status = RESOURCE_NEED_REJECTED
        need.note = note
    elif action == "accept":
        need.status = RESOURCE_NEED_ACCEPTED
        need.confirmed_user_id = need.suggested_user_id
        need.note = note or "确认投入"
    else:  # adjust
        member_id = payload.confirmed_user_id or need.suggested_user_id
        if not member_id:
            raise HTTPException(status_code=400, detail="请指定确认成员")
        member = db.query(User).filter(User.id == member_id, User.is_active.is_(True)).first()
        if not member:
            raise HTTPException(status_code=400, detail="成员不存在或已停用")
        if payload.planned_hours is not None:
            if payload.planned_hours <= 0:
                raise HTTPException(status_code=400, detail="计划投入须大于 0")
            assert_resource_budget_covers_tasks(
                db,
                need.project_id,
                exclude_need_id=need.id,
                override_hours=payload.planned_hours,
            )
            need.planned_hours = payload.planned_hours
        need.confirmed_user_id = member_id
        need.suggested_user_id = member_id
        need.status = RESOURCE_NEED_ACCEPTED
        need.note = note or "调整后确认"

    need.confirmed_by = user.id
    need.confirmed_at = _now()
    refresh_schedule_check(db, need, project)
    db.commit()
    db.refresh(need)
    return enrich_need(db, need, project)


def assert_resources_ready(db: Session, project_id: int) -> None:
    pending = pending_count_for_project(db, project_id)
    if pending > 0:
        raise HTTPException(
            status_code=400,
            detail=f"仍有 {pending} 项资源待部门确认，请先完成「待确认资源」",
        )


def sum_resource_budget_hours(
    db: Session,
    project_id: int,
    *,
    exclude_need_id: Optional[int] = None,
    override_hours: Optional[Decimal] = None,
) -> Decimal:
    """未拒绝的资源计划投入合计；可用于模拟单条调整/拒绝后的预算。"""
    rows = (
        db.query(ProjectResourceNeed.id, ProjectResourceNeed.planned_hours, ProjectResourceNeed.status)
        .filter(ProjectResourceNeed.project_id == project_id)
        .all()
    )
    total = Decimal("0")
    for need_id, hours, status in rows:
        if status == RESOURCE_NEED_REJECTED:
            continue
        if exclude_need_id is not None and need_id == exclude_need_id:
            if override_hours is None:
                continue
            total += Decimal(str(override_hours))
        else:
            total += Decimal(str(hours or 0))
    return total


def sum_task_planned_hours(
    db: Session, project_id: int, *, exclude_task_id: Optional[int] = None
) -> Decimal:
    q = db.query(func.coalesce(func.sum(ProjectTask.planned_hours), 0)).filter(
        ProjectTask.project_id == project_id
    )
    if exclude_task_id is not None:
        q = q.filter(ProjectTask.id != exclude_task_id)
    return Decimal(str(q.scalar() or 0))


def sum_task_actual_hours(db: Session, project_id: int) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(ProjectTask.actual_hours), 0))
        .filter(ProjectTask.project_id == project_id)
        .scalar()
    )
    return Decimal(str(total or 0))


def get_hours_budget(db: Session, project_id: int) -> dict:
    budget = sum_resource_budget_hours(db, project_id)
    accepted = (
        db.query(func.coalesce(func.sum(ProjectResourceNeed.planned_hours), 0))
        .filter(
            ProjectResourceNeed.project_id == project_id,
            ProjectResourceNeed.status == RESOURCE_NEED_ACCEPTED,
        )
        .scalar()
    )
    task_planned = sum_task_planned_hours(db, project_id)
    task_actual = sum_task_actual_hours(db, project_id)
    accepted_dec = Decimal(str(accepted or 0))
    remaining = budget - task_planned
    return {
        "project_id": project_id,
        "resource_budget_hours": budget,
        "resource_accepted_hours": accepted_dec,
        "task_planned_hours": task_planned,
        "task_actual_hours": task_actual,
        "remaining_hours": remaining,
        "over_budget": bool(budget > 0 and task_planned > budget),
    }


def assert_task_hours_within_budget(
    db: Session,
    project_id: int,
    new_planned_hours: Decimal,
    *,
    exclude_task_id: Optional[int] = None,
) -> None:
    """任务计划工时合计不得超过立项资源承诺（未拒绝项）。无资源需求时不约束。"""
    budget = sum_resource_budget_hours(db, project_id)
    if budget <= 0:
        return
    other = sum_task_planned_hours(db, project_id, exclude_task_id=exclude_task_id)
    total = other + Decimal(str(new_planned_hours or 0))
    if total > budget:
        remaining = budget - other
        raise HTTPException(
            status_code=400,
            detail=(
                f"任务计划工时合计将达 {total}h，超出资源承诺 {budget}h"
                f"（还可拆 {max(remaining, Decimal('0'))}h）。"
                "请下调本任务工时，或先在资源确认中调高部门计划投入。"
            ),
        )


def assert_resource_budget_covers_tasks(
    db: Session,
    project_id: int,
    *,
    exclude_need_id: Optional[int] = None,
    override_hours: Optional[Decimal] = None,
) -> None:
    """降低/拒绝资源投入后，预算仍须覆盖已拆任务计划工时。"""
    task_planned = sum_task_planned_hours(db, project_id)
    if task_planned <= 0:
        return
    budget = sum_resource_budget_hours(
        db,
        project_id,
        exclude_need_id=exclude_need_id,
        override_hours=override_hours,
    )
    if budget < task_planned:
        raise HTTPException(
            status_code=400,
            detail=(
                f"调整后资源承诺仅 {budget}h，低于已拆任务计划 {task_planned}h。"
                "请先下调任务计划工时，或保留足够投入后再确认/拒绝。"
            ),
        )
