"""飞书通讯录 → 本地部门 / 员工同步。"""
from __future__ import annotations

import asyncio
import re
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.security import hash_password
from app.models.department import Department
from app.models.employee_hr import EmployeeHistoryEvent
from app.models.role import Role
from app.models.user import User
from app.services.feishu_auth import FeishuAuthError
from app.services.feishu_client import FeishuClient, get_feishu_client
from app.services.sync_state import SYNC_KEY_CONTACT, upsert_sync_state


def feishu_dept_code(open_department_id: str) -> str:
    raw = f"FS_{open_department_id}"
    return raw[:50]


def _fmt_dept_error(prefix: str, department_id: str, exc: FeishuAuthError) -> str:
    msg = str(exc)
    tip = ""
    if "no dept authority" in msg.lower() or "40004" in msg:
        tip = (
            "；无根部门权限时将自动改走「通讯录授权范围」。"
            "请确认应用可用范围已包含要同步的部门/成员，并已发布版本"
        )
    return f"{prefix} department_id={department_id}: {msg}{tip}"


def _is_no_dept_authority(exc: FeishuAuthError) -> bool:
    msg = str(exc).lower()
    detail = getattr(exc, "detail", None)
    blob = f"{msg} {detail}".lower()
    return "no dept authority" in blob or "40004" in blob


def _sanitize_username(raw: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "", raw).strip("._-")
    return (cleaned or "fs_user")[:50]


def map_employment_status(item: dict[str, Any], *, is_active: bool) -> str:
    if not is_active:
        return "离职"
    emp_type = item.get("employee_type")
    # 飞书 employee_type: 1 正式 2 实习 3 外包 4 劳务 5 顾问
    if emp_type in (2, "2"):
        return "试用"
    status = item.get("status") or {}
    if status.get("is_frozen"):
        return "待入职"
    return "正式"


def parse_hire_date(item: dict[str, Any]) -> date | None:
    join_time = item.get("join_time")
    if join_time is None or join_time == "" or join_time == 0:
        return None
    try:
        ts = int(join_time)
        if ts > 10_000_000_000:
            ts = ts // 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


@dataclass
class FeishuSyncResult:
    departments_created: int = 0
    departments_updated: int = 0
    employees_created: int = 0
    employees_updated: int = 0
    employees_bound: int = 0
    employees_matched: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "departments_created": self.departments_created,
            "departments_updated": self.departments_updated,
            "employees_created": self.employees_created,
            "employees_updated": self.employees_updated,
            "employees_bound": self.employees_bound,
            "employees_matched": self.employees_matched,
            "skipped": self.skipped,
            "warnings": self.warnings,
        }


async def sync_feishu_contacts(
    db: Session,
    *,
    settings: Settings | None = None,
    client: FeishuClient | None = None,
) -> FeishuSyncResult:
    cfg = settings or get_settings()
    own_client = client is None
    api = client or get_feishu_client(cfg)
    result = FeishuSyncResult()

    if own_client:
        await api.__aenter__()
    try:
        upsert_sync_state(db, SYNC_KEY_CONTACT, status="pending")
        db.commit()
        out = await _sync_feishu_contacts_inner(db, api=api, cfg=cfg, result=result)
        upsert_sync_state(
            db,
            SYNC_KEY_CONTACT,
            status="ok",
            last_error=None,
            meta=out.as_dict(),
            success=True,
        )
        db.commit()
        return out
    except Exception as exc:
        db.rollback()
        upsert_sync_state(db, SYNC_KEY_CONTACT, status="error", last_error=str(exc))
        db.commit()
        raise
    finally:
        if own_client:
            await api.__aexit__(None, None, None)


async def _sync_feishu_contacts_inner(
    db: Session,
    *,
    api: FeishuClient,
    cfg: Settings,
    result: FeishuSyncResult,
) -> FeishuSyncResult:
    root = db.query(Department).filter(Department.code == "ROOT").first()
    if not root:
        root = Department(name="总公司", code="ROOT", description="根部门")
        db.add(root)
        db.flush()
        result.departments_created += 1

    dept_map: dict[str, Department] = {}
    scope_user_ids: list[str] = []
    start_dept_id = (cfg.feishu_contact_root_department_id or "0").strip() or "0"
    leader_links: dict[str, str] = {}

    seed_ids = await _resolve_seed_department_ids(
        api,
        start_dept_id=start_dept_id,
        result=result,
    )
    if seed_ids.get("use_scopes_users"):
        scope_user_ids = list(seed_ids.get("user_ids") or [])

    use_deep_fetch = bool(seed_ids.get("use_scopes_users")) or start_dept_id != "0"

    queue: list[tuple[str, Department | None]] = []
    for feishu_id in seed_ids.get("department_ids") or []:
        if feishu_id == "0":
            dept_map["0"] = root
            queue.append(("0", root))
            continue
        name = await _department_display_name(api, feishu_id, result)
        local = _upsert_department(db, feishu_id, root, result, name=name)
        dept_map[feishu_id] = local
        queue.append((feishu_id, local))

    visited: set[str] = set()
    while queue:
        feishu_id, parent = queue.pop(0)
        if feishu_id in visited:
            continue
        visited.add(feishu_id)

        if feishu_id == "0":
            dept_map["0"] = root
        elif feishu_id not in dept_map:
            local = _upsert_department(db, feishu_id, parent, result)
            dept_map[feishu_id] = local

        try:
            children = await api.iter_department_children(
                feishu_id,
                fetch_child=use_deep_fetch and feishu_id != "0",
            )
        except FeishuAuthError as exc:
            if feishu_id == "0" and _is_no_dept_authority(exc):
                continue
            result.warnings.append(_fmt_dept_error("拉取子部门失败", feishu_id, exc))
            continue

        for child in children:
            child_id = str(child.get("open_department_id") or child.get("department_id") or "")
            if not child_id:
                result.skipped += 1
                continue
            name = str(child.get("name") or child_id)
            parent_feishu = str(child.get("parent_department_id") or "") or feishu_id
            parent_local = dept_map.get(parent_feishu) or dept_map.get(feishu_id) or parent
            local_child = _upsert_department(db, child_id, parent_local, result, name=name)
            dept_map[child_id] = local_child
            if not (use_deep_fetch and feishu_id != "0"):
                queue.append((child_id, local_child))

    db.flush()

    employee_role = db.query(Role).filter(Role.code == "employee").first()
    # 先按 open_id 去重收集，再按用户自身的 department_ids 解析归属，
    # 避免「先扫到根部门 0 → 全员挂到总公司 → 后续真实部门被跳过」。
    pending_users: dict[str, dict[str, Any]] = {}
    pending_depts: dict[str, Department | None] = {}

    for i, feishu_dept_id in enumerate(list(dept_map.keys())):
        if i and i % 5 == 0:
            await asyncio.sleep(0)
        try:
            users = await api.iter_users_by_department(feishu_dept_id)
        except FeishuAuthError as exc:
            if feishu_dept_id == "0" and _is_no_dept_authority(exc):
                continue
            result.warnings.append(_fmt_dept_error("拉取部门成员失败", feishu_dept_id, exc))
            continue

        fallback = root if feishu_dept_id == "0" else dept_map.get(feishu_dept_id)
        for item in users:
            open_id = str(item.get("open_id") or "")
            if not open_id:
                result.skipped += 1
                continue
            resolved = _pick_department_for_user(item, dept_map, root, fallback)
            if open_id in pending_users:
                pending_users[open_id] = item
                pending_depts[open_id] = _prefer_department(
                    pending_depts.get(open_id), resolved, root
                )
            else:
                pending_users[open_id] = item
                pending_depts[open_id] = resolved
            leader = str(item.get("leader_user_id") or "").strip()
            if leader:
                leader_links[open_id] = leader

    for open_id in scope_user_ids:
        if open_id in pending_users:
            continue
        try:
            item = await api.get_user(open_id)
        except FeishuAuthError as exc:
            result.warnings.append(f"拉取用户失败 open_id={open_id}: {exc}")
            continue
        if not item:
            result.skipped += 1
            continue
        for did in [str(x) for x in (item.get("department_ids") or [])]:
            if did and did != "0" and did not in dept_map:
                name = await _department_display_name(api, did, result)
                dept_map[did] = _upsert_department(db, did, root, result, name=name)
        pending_users[open_id] = item
        pending_depts[open_id] = _pick_department_for_user(item, dept_map, root, root)
        leader = str(item.get("leader_user_id") or "").strip()
        if leader:
            leader_links[open_id] = leader

    for open_id, item in pending_users.items():
        _upsert_employee(
            db,
            item=item,
            department=pending_depts.get(open_id) or root,
            employee_role=employee_role,
            result=result,
        )

    _resolve_managers(db, leader_links, result)

    if not dept_map and not scope_user_ids and not result.warnings:
        result.warnings.append(
            "通讯录授权范围内没有部门或成员：请到飞书开放平台 → 版本管理与发布 / 应用可用范围，"
            "加入要同步的部门或成员并发布版本"
        )

    db.flush()
    return result


def _resolve_managers(
    db: Session,
    leader_links: dict[str, str],
    result: FeishuSyncResult,
) -> None:
    if not leader_links:
        return
    open_ids = set(leader_links.keys()) | set(leader_links.values())
    users = db.query(User).filter(User.feishu_open_id.in_(list(open_ids))).all()
    by_open = {u.feishu_open_id: u for u in users if u.feishu_open_id}
    for open_id, leader_open_id in leader_links.items():
        user = by_open.get(open_id)
        manager = by_open.get(leader_open_id)
        if not user or not manager or user.id == manager.id:
            continue
        if user.manager_id != manager.id:
            user.manager_id = manager.id


async def _resolve_seed_department_ids(
    api: FeishuClient,
    *,
    start_dept_id: str,
    result: FeishuSyncResult,
) -> dict:
    if start_dept_id != "0":
        return {"department_ids": [start_dept_id], "user_ids": [], "use_scopes_users": False}

    try:
        await api.iter_department_children("0")
        return {"department_ids": ["0"], "user_ids": [], "use_scopes_users": False}
    except FeishuAuthError as exc:
        if not _is_no_dept_authority(exc):
            result.warnings.append(_fmt_dept_error("拉取子部门失败", "0", exc))
            return {"department_ids": [], "user_ids": [], "use_scopes_users": False}
        result.warnings.append(
            "根部门 0 无权限（通讯录范围=与应用可用范围一致），已改走「获取通讯录授权范围」同步"
        )

    try:
        scopes = await api.list_contact_scopes()
    except FeishuAuthError as exc:
        result.warnings.append(f"获取通讯录授权范围失败: {exc}")
        return {"department_ids": [], "user_ids": [], "use_scopes_users": False}

    dept_ids = [d for d in scopes.get("department_ids") or [] if d]
    user_ids = [u for u in scopes.get("user_ids") or [] if u]
    if not dept_ids and not user_ids:
        result.warnings.append(
            "授权范围为空：请在飞书开放平台把「应用可用范围」设为要同步的部门/成员（或全部），"
            "创建版本并发布后再同步"
        )
    else:
        result.warnings.append(
            f"当前通讯录授权范围：部门 {len(dept_ids)} 个、成员 {len(user_ids)} 人"
            "（与应用可用范围一致；要同步全公司请扩大可用范围或改为全部成员后发布）"
        )
    return {
        "department_ids": dept_ids,
        "user_ids": user_ids,
        "use_scopes_users": True,
    }


async def _department_display_name(
    api: FeishuClient,
    department_id: str,
    result: FeishuSyncResult,
) -> str:
    try:
        info = await api.get_department(department_id)
        name = (info.get("name") or "").strip()
        if name:
            return name
    except FeishuAuthError as exc:
        result.warnings.append(f"获取部门名称失败 department_id={department_id}: {exc}")
    return f"飞书部门 {department_id}"


def _pick_department_for_user(
    item: dict[str, Any],
    dept_map: dict[str, Department],
    root: Department,
    fallback: Department | None,
) -> Department | None:
    """按飞书用户 department_ids 解析本地部门；主部门优先，跳过根部门 0。"""
    dept_ids = [str(x) for x in (item.get("department_ids") or []) if x is not None and str(x)]
    for did in dept_ids:
        if did == "0":
            continue
        if did in dept_map:
            return dept_map[did]
    if "0" in dept_ids:
        return root
    return fallback


def _prefer_department(
    current: Department | None,
    candidate: Department | None,
    root: Department,
) -> Department | None:
    """多人多部门命中时，优先保留非总公司的具体部门。"""
    if candidate is None:
        return current
    if current is None:
        return candidate
    if current.id == root.id and candidate.id != root.id:
        return candidate
    if current.id != root.id and candidate.id == root.id:
        return current
    return current


def _upsert_department(
    db: Session,
    open_department_id: str,
    parent: Department | None,
    result: FeishuSyncResult,
    *,
    name: str | None = None,
) -> Department:
    code = feishu_dept_code(open_department_id)
    dept = db.query(Department).filter(Department.code == code).first()
    display = (name or open_department_id)[:100]
    if dept:
        changed = False
        if name and dept.name != display:
            dept.name = display
            changed = True
        if parent and dept.parent_id != parent.id and dept.id != parent.id:
            dept.parent_id = parent.id
            changed = True
        if changed:
            result.departments_updated += 1
        return dept

    dept = Department(
        name=display,
        code=code,
        parent_id=parent.id if parent else None,
        description=f"飞书部门 {open_department_id}",
    )
    db.add(dept)
    db.flush()
    result.departments_created += 1
    return dept


def _upsert_employee(
    db: Session,
    *,
    item: dict,
    department: Department | None,
    employee_role: Role | None,
    result: FeishuSyncResult,
) -> None:
    open_id = str(item.get("open_id"))
    name = (item.get("name") or item.get("en_name") or "").strip() or None
    email = (item.get("email") or item.get("enterprise_email") or "").strip() or None
    mobile = (item.get("mobile") or "").strip() or None
    job_title = (item.get("job_title") or "").strip() or None
    employee_no = (item.get("employee_no") or "").strip() or None
    feishu_user_id = (item.get("user_id") or "").strip() or None
    status = item.get("status") or {}
    is_resigned = bool(status.get("is_resigned"))
    is_activated = status.get("is_activated")
    is_active = (not is_resigned) and (True if is_activated is None else bool(is_activated))
    employment_status = map_employment_status(item, is_active=is_active)
    hire_date = parse_hire_date(item)

    user = db.query(User).filter(User.feishu_open_id == open_id).first()
    bound = False
    if user is None and email:
        user = db.query(User).filter(User.email == email).first()
        if user and not user.feishu_open_id:
            user.feishu_open_id = open_id
            bound = True
        elif user and user.feishu_open_id and user.feishu_open_id != open_id:
            result.warnings.append(f"邮箱 {email} 已绑定其他飞书账号，跳过 open_id={open_id}")
            result.skipped += 1
            return

    if user is None and mobile:
        normalized = mobile.replace(" ", "")
        candidates = [normalized, normalized.lstrip("+86"), normalized.removeprefix("86")]
        user = db.query(User).filter(User.phone.in_(candidates)).first()
        if user and not user.feishu_open_id:
            user.feishu_open_id = open_id
            bound = True

    if user is None:
        username = _username_from_feishu(item, open_id)
        base = username
        n = 1
        while db.query(User).filter(User.username == username).first() is not None:
            n += 1
            username = f"{base[:40]}_{n}"[:50]
        user = User(
            username=username,
            password_hash=hash_password(secrets.token_urlsafe(24)),
            real_name=name or username,
            email=email,
            phone=mobile,
            job_title=job_title,
            employee_no=employee_no,
            feishu_open_id=open_id,
            feishu_user_id=feishu_user_id,
            hire_date=hire_date,
            employment_status=employment_status,
            department_id=department.id if department else None,
            is_active=is_active,
            archive_status="完整",
        )
        if employee_role:
            user.roles.append(employee_role)
        db.add(user)
        db.flush()
        _ensure_hire_event(db, user)
        result.employees_created += 1
        return

    if bound:
        result.employees_bound += 1

    changed = bound
    if name and user.real_name != name:
        user.real_name = name
        changed = True
    if email and user.email != email:
        user.email = email
        changed = True
    if mobile and user.phone != mobile:
        user.phone = mobile
        changed = True
    if user.job_title != job_title:
        user.job_title = job_title
        changed = True
    if employee_no and user.employee_no != employee_no:
        user.employee_no = employee_no
        changed = True
    if feishu_user_id and user.feishu_user_id != feishu_user_id:
        occupied = (
            db.query(User)
            .filter(User.feishu_user_id == feishu_user_id, User.id != user.id)
            .first()
        )
        if occupied:
            result.warnings.append(f"飞书 user_id={feishu_user_id} 已被占用，跳过绑定")
        else:
            user.feishu_user_id = feishu_user_id
            changed = True
    if hire_date and user.hire_date != hire_date:
        user.hire_date = hire_date
        changed = True
    if user.employment_status != employment_status:
        user.employment_status = employment_status
        changed = True
    if department and user.department_id != department.id:
        user.department_id = department.id
        changed = True
    if user.is_active != is_active:
        user.is_active = is_active
        changed = True
    if not user.feishu_open_id:
        user.feishu_open_id = open_id
        changed = True
    if not user.archive_status:
        user.archive_status = "完整"
        changed = True
    if changed:
        result.employees_updated += 1
        if hire_date and not _has_hire_event(db, user.id):
            _ensure_hire_event(db, user)
    else:
        result.employees_matched += 1


def _has_hire_event(db: Session, user_id: int) -> bool:
    return (
        db.query(EmployeeHistoryEvent)
        .filter(
            EmployeeHistoryEvent.user_id == user_id,
            EmployeeHistoryEvent.event_type == "hire",
        )
        .first()
        is not None
    )


def _ensure_hire_event(db: Session, user: User) -> None:
    if _has_hire_event(db, user.id):
        return
    occurred = (
        datetime.combine(user.hire_date, datetime.min.time(), tzinfo=timezone.utc)
        if user.hire_date
        else datetime.now(timezone.utc)
    )
    title = "完成入职并建立员工档案"
    detail = "组织身份与飞书账号同步"
    if user.job_title:
        title = f"入职 · {user.job_title}"
    db.add(
        EmployeeHistoryEvent(
            user_id=user.id,
            event_type="hire",
            title=title,
            detail=detail,
            occurred_at=occurred,
        )
    )


def _username_from_feishu(item: dict, open_id: str) -> str:
    email = (item.get("email") or item.get("enterprise_email") or "").strip()
    if email and "@" in email:
        return _sanitize_username(email.split("@", 1)[0])
    mobile = re.sub(r"\D", "", item.get("mobile") or "")
    if mobile:
        return _sanitize_username(f"m{mobile[-11:]}")
    suffix = open_id.replace("ou_", "")[-20:]
    return _sanitize_username(f"fs_{suffix}")
