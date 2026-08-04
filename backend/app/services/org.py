"""
组织员工：部门树、员工账号维护、档案详情与任职经历。
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password
from app.models.department import Department
from app.models.employee_hr import EmployeeHistoryEvent, FeishuAttendanceDaily
from app.models.role import Role
from app.models.user import User
from app.schemas.org import (
    DepartmentCreate,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeResetPassword,
    EmployeeUpdate,
)
from app.services.feishu_attendance import today_status_for_user


def enrich_employee(db: Session, user: User, *, with_overview: bool = False) -> User:
    user.department_name = user.department.name if user.department else None  # type: ignore[attr-defined]
    manager = None
    if user.manager_id:
        if user.manager is not None:
            manager = user.manager
        else:
            manager = db.query(User).filter(User.id == user.manager_id).first()
    user.manager_name = (manager.real_name or manager.username) if manager else None  # type: ignore[attr-defined]
    user.feishu_bound = bool(user.feishu_open_id)  # type: ignore[attr-defined]
    if user.feishu_open_id and (user.feishu_user_id or user.employee_no):
        user.identity_sync = "正常"  # type: ignore[attr-defined]
    elif user.feishu_open_id:
        user.identity_sync = "部分绑定"  # type: ignore[attr-defined]
    else:
        user.identity_sync = "未绑定"  # type: ignore[attr-defined]
    user.today_status = today_status_for_user(db, user.id)  # type: ignore[attr-defined]
    if with_overview:
        user.todos = build_employee_todos(user)  # type: ignore[attr-defined]
    else:
        user.todos = []  # type: ignore[attr-defined]
    return user


def build_employee_todos(user: User) -> list[dict]:
    todos: list[dict] = []
    if user.contract_end:
        days = (user.contract_end - date.today()).days
        if days <= 30:
            todos.append(
                {
                    "key": "contract",
                    "label": "劳动合同到期",
                    "status": "需关注" if days >= 0 else "已过期",
                    "detail": f"{user.contract_end.isoformat()}（{days}天）",
                }
            )
    archive = user.archive_status or "完整"
    todos.append(
        {
            "key": "archive",
            "label": "档案资料",
            "status": "正常" if archive == "完整" else "待补",
            "detail": archive,
        }
    )
    todos.append(
        {
            "key": "account_sync",
            "label": "账号同步",
            "status": "正常" if user.feishu_open_id else "未绑定",
            "detail": "飞书身份" if user.feishu_open_id else "需绑定飞书账号",
        }
    )
    return todos


def list_departments_flat(db: Session) -> list[Department]:
    depts = db.query(Department).order_by(Department.id.asc()).all()
    counts = {
        d.id: db.query(User).filter(User.department_id == d.id).count() for d in depts
    }
    for d in depts:
        d.user_count = counts.get(d.id, 0)  # type: ignore[attr-defined]
    return depts


def build_department_tree(db: Session) -> list[Department]:
    depts = list_departments_flat(db)
    by_id = {d.id: d for d in depts}
    for d in depts:
        d.children = []  # type: ignore[attr-defined]
    roots: list[Department] = []
    for d in depts:
        if d.parent_id and d.parent_id in by_id:
            parent = by_id[d.parent_id]
            parent.children.append(d)  # type: ignore[attr-defined]
        else:
            roots.append(d)
    return roots


def create_department(db: Session, payload: DepartmentCreate) -> Department:
    if payload.parent_id:
        parent = db.query(Department).filter(Department.id == payload.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="上级部门不存在")
    if payload.code:
        exists = db.query(Department).filter(Department.code == payload.code).first()
        if exists:
            raise HTTPException(status_code=400, detail="部门编码已存在")

    dept = Department(
        name=payload.name.strip(),
        code=payload.code.strip() if payload.code else None,
        parent_id=payload.parent_id,
        description=payload.description,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    dept.user_count = 0  # type: ignore[attr-defined]
    dept.children = []  # type: ignore[attr-defined]
    return dept


def update_department(db: Session, dept_id: int, payload: DepartmentUpdate) -> Department:
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")

    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        parent_id = data["parent_id"]
        if parent_id == dept_id:
            raise HTTPException(status_code=400, detail="不能将部门设为自己的上级")
        if parent_id:
            parent = db.query(Department).filter(Department.id == parent_id).first()
            if not parent:
                raise HTTPException(status_code=400, detail="上级部门不存在")
            cursor = parent
            while cursor.parent_id:
                if cursor.parent_id == dept_id:
                    raise HTTPException(status_code=400, detail="不能形成部门环")
                cursor = (
                    db.query(Department).filter(Department.id == cursor.parent_id).first()
                )
                if not cursor:
                    break
    if "code" in data and data["code"]:
        exists = (
            db.query(Department)
            .filter(Department.code == data["code"], Department.id != dept_id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="部门编码已存在")
    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()
    if "code" in data and data["code"]:
        data["code"] = data["code"].strip()

    for k, v in data.items():
        setattr(dept, k, v)
    db.commit()
    db.refresh(dept)
    dept.user_count = db.query(User).filter(User.department_id == dept.id).count()  # type: ignore[attr-defined]
    dept.children = []  # type: ignore[attr-defined]
    return dept


def delete_department(db: Session, dept_id: int) -> None:
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")
    if dept.code == "ROOT":
        raise HTTPException(status_code=400, detail="根部门不可删除")
    child = db.query(Department).filter(Department.parent_id == dept_id).first()
    if child:
        raise HTTPException(status_code=400, detail="请先删除或移出子部门")
    user = db.query(User).filter(User.department_id == dept_id).first()
    if user:
        raise HTTPException(status_code=400, detail="部门下仍有员工，无法删除")
    db.delete(dept)
    db.commit()


def _load_roles(db: Session, role_ids: list[int]) -> list[Role]:
    if not role_ids:
        return []
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status_code=400, detail="存在无效角色")
    return roles


def list_employees(
    db: Session,
    *,
    keyword: Optional[str] = None,
    department_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    employment_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[User]]:
    q = db.query(User).options(
        joinedload(User.roles),
        joinedload(User.department),
        joinedload(User.manager),
    )
    if department_id:
        q = q.filter(User.department_id == department_id)
    if is_active is not None:
        q = q.filter(User.is_active.is_(is_active))
    if employment_status:
        q = q.filter(User.employment_status == employment_status)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(
            (User.username.like(like))
            | (User.real_name.like(like))
            | (User.phone.like(like))
            | (User.email.like(like))
            | (User.employee_no.like(like))
            | (User.job_title.like(like))
        )
    total = q.count()
    items = (
        q.order_by(User.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, [enrich_employee(db, u) for u in items]


def get_employee(db: Session, user_id: int, *, with_overview: bool = True) -> User:
    user = (
        db.query(User)
        .options(
            joinedload(User.roles),
            joinedload(User.department),
            joinedload(User.manager),
        )
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="员工不存在")
    return enrich_employee(db, user, with_overview=with_overview)


def create_employee(db: Session, payload: EmployeeCreate) -> User:
    exists = db.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    if payload.department_id:
        dept = db.query(Department).filter(Department.id == payload.department_id).first()
        if not dept:
            raise HTTPException(status_code=400, detail="部门不存在")
    if payload.manager_id:
        mgr = db.query(User).filter(User.id == payload.manager_id).first()
        if not mgr:
            raise HTTPException(status_code=400, detail="直属负责人不存在")

    roles = _load_roles(db, payload.role_ids)
    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        real_name=payload.real_name or payload.username,
        email=payload.email,
        phone=payload.phone,
        department_id=payload.department_id,
        is_active=payload.is_active,
        job_title=payload.job_title,
        employee_no=payload.employee_no,
        hire_date=payload.hire_date,
        employment_status=payload.employment_status or ("正式" if payload.is_active else "离职"),
        manager_id=payload.manager_id,
        contract_type=payload.contract_type,
        contract_start=payload.contract_start,
        contract_end=payload.contract_end,
        contract_status=payload.contract_status,
        archive_status=payload.archive_status or "完整",
    )
    user.roles = roles
    db.add(user)
    db.flush()
    db.add(
        EmployeeHistoryEvent(
            user_id=user.id,
            event_type="hire",
            title=f"入职 · {user.job_title or user.real_name or user.username}",
            detail="本地建档",
            occurred_at=datetime.combine(
                user.hire_date or date.today(),
                datetime.min.time(),
                tzinfo=timezone.utc,
            ),
        )
    )
    db.commit()
    return get_employee(db, user.id)


def update_employee(db: Session, user_id: int, payload: EmployeeUpdate, *, actor: User) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="员工不存在")

    data = payload.model_dump(exclude_unset=True)
    role_ids = data.pop("role_ids", None)
    prev_dept = user.department_id
    prev_title = user.job_title
    prev_status = user.employment_status

    if "department_id" in data and data["department_id"]:
        dept = db.query(Department).filter(Department.id == data["department_id"]).first()
        if not dept:
            raise HTTPException(status_code=400, detail="部门不存在")

    if "manager_id" in data and data["manager_id"]:
        if data["manager_id"] == user_id:
            raise HTTPException(status_code=400, detail="不能将自己设为直属负责人")
        mgr = db.query(User).filter(User.id == data["manager_id"]).first()
        if not mgr:
            raise HTTPException(status_code=400, detail="直属负责人不存在")

    if data.get("is_active") is False and user.id == actor.id:
        raise HTTPException(status_code=400, detail="不能停用当前登录账号")

    if "feishu_open_id" in data:
        oid = data["feishu_open_id"]
        if oid:
            occupied = (
                db.query(User)
                .filter(User.feishu_open_id == oid, User.id != user.id)
                .first()
            )
            if occupied:
                raise HTTPException(status_code=400, detail="该飞书 open_id 已绑定其他账号")
        else:
            data["feishu_open_id"] = None

    for k, v in data.items():
        setattr(user, k, v)

    if role_ids is not None:
        if user.id == actor.id:
            raise HTTPException(status_code=400, detail="不能修改自己的角色")
        user.roles = _load_roles(db, role_ids)

    # 转岗 / 离职简单留痕
    new_status = user.employment_status
    if new_status == "离职" and prev_status != "离职":
        db.add(
            EmployeeHistoryEvent(
                user_id=user.id,
                event_type="resign",
                title="办理离职",
                detail=f"原岗位 {prev_title or '—'}",
                occurred_at=datetime.now(timezone.utc),
            )
        )
        user.is_active = False
    elif (
        ("department_id" in data and data.get("department_id") != prev_dept)
        or ("job_title" in data and data.get("job_title") != prev_title)
    ) and new_status != "离职":
        db.add(
            EmployeeHistoryEvent(
                user_id=user.id,
                event_type="transfer",
                title=f"转岗 · {user.job_title or '岗位调整'}",
                detail=f"原岗位 {prev_title or '—'} → {user.job_title or '—'}",
                occurred_at=datetime.now(timezone.utc),
            )
        )

    db.commit()
    return get_employee(db, user_id)


def reset_employee_password(
    db: Session, user_id: int, payload: EmployeeResetPassword
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="员工不存在")
    user.password_hash = hash_password(payload.password)
    db.commit()
    return get_employee(db, user_id)


def list_employee_history(db: Session, user_id: int) -> list[EmployeeHistoryEvent]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="员工不存在")
    return (
        db.query(EmployeeHistoryEvent)
        .filter(EmployeeHistoryEvent.user_id == user_id)
        .order_by(EmployeeHistoryEvent.occurred_at.desc(), EmployeeHistoryEvent.id.desc())
        .all()
    )


def org_stats(db: Session) -> dict:
    total = db.query(User).count()
    active = db.query(User).filter(User.is_active.is_(True)).count()
    pending = db.query(User).filter(User.employment_status == "待入职").count()
    soon = date.today() + timedelta(days=30)
    contract_expiring = (
        db.query(User)
        .filter(
            User.contract_end.isnot(None),
            User.contract_end >= date.today(),
            User.contract_end <= soon,
            User.is_active.is_(True),
        )
        .count()
    )
    today = date.today()
    today_total = (
        db.query(FeishuAttendanceDaily)
        .filter(
            FeishuAttendanceDaily.work_date == today,
            FeishuAttendanceDaily.status != "休息日",
        )
        .count()
    )
    today_ok = (
        db.query(FeishuAttendanceDaily)
        .filter(
            FeishuAttendanceDaily.work_date == today,
            FeishuAttendanceDaily.status.in_(["正常", "迟到", "早退"]),
        )
        .count()
    )
    return {
        "departments": db.query(Department).count(),
        "employees": total,
        "active_employees": active,
        "inactive_employees": total - active,
        "pending_onboard": pending,
        "contract_expiring_30d": contract_expiring,
        "today_attendance_ok": today_ok,
        "today_attendance_total": today_total,
    }


def list_role_options(db: Session) -> list[Role]:
    return db.query(Role).order_by(Role.id.asc()).all()
