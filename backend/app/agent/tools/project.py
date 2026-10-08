"""项目只读 / 写操作工具。"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from langchain_core.tools import tool
from sqlalchemy import or_

from app.agent.runtime import require_db, require_user
from app.agent.tools.base import write_operation
from app.models.project import PROJECT_STATUS_LABEL
from app.models.user import User
from app.schemas.project import ProjectUpdate
from app.services import project as project_service


def _project_brief(p) -> dict:
    status = getattr(p, "status", None)
    return {
        "id": p.id,
        "name": p.name,
        "project_no": getattr(p, "project_no", None),
        "status": status,
        "status_label": PROJECT_STATUS_LABEL.get(status, status),
        "manager": getattr(p, "manager_name", None),
        "progress": getattr(p, "progress", None),
    }


def _resolve_user_by_name(db, name: str) -> User:
    key = (name or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    user = (
        db.query(User)
        .filter(or_(User.real_name == key, User.username == key))
        .first()
    )
    if not user:
        like = f"%{key}%"
        rows = (
            db.query(User)
            .filter(or_(User.real_name.like(like), User.username.like(like)))
            .limit(5)
            .all()
        )
        if len(rows) == 1:
            return rows[0]
        if not rows:
            raise HTTPException(status_code=404, detail=f"找不到用户：{key}")
        names = [u.real_name or u.username for u in rows]
        raise HTTPException(
            status_code=400,
            detail=f"匹配到多个用户，请用精确姓名或用户名：{', '.join(names)}",
        )
    return user


@tool
def list_my_projects(status: Optional[str] = None) -> list:
    """列出当前用户负责或创建的项目。

    Args:
        status: 可选项目状态码：initiating/planning/executing/accepting/accepted/completed/terminated
    """
    db, user = require_db(), require_user()
    _, items = project_service.list_projects(
        db, user, status=status, scope_filter="mine", page=1, page_size=20
    )
    return [_project_brief(p) for p in items]


@tool
def search_projects(keyword: str) -> list:
    """按关键词搜索项目。当用户说"找一下叫XX的项目"时用此工具。"""
    db, user = require_db(), require_user()
    _, items = project_service.list_projects(
        db, user, keyword=keyword, page=1, page_size=10
    )
    return [{"id": p.id, "name": p.name, "status": p.status} for p in items]


@tool
def get_project_detail(project_id: int) -> dict:
    """查询项目详情，包括基本信息、负责人、进度。"""
    db, user = require_db(), require_user()
    try:
        p = project_service.get_project_detail(db, user, project_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        **_project_brief(p),
        "customer_name": getattr(p, "customer_name", None),
        "contract_no": getattr(p, "contract_no", None),
        "start_date": str(p.start_date) if getattr(p, "start_date", None) else None,
        "end_date": str(p.end_date) if getattr(p, "end_date", None) else None,
        "milestone_count": len(getattr(p, "milestones", None) or []),
    }


@write_operation("修改项目负责人", permission="project:manage")
@tool
def update_project_manager(project_id: int, manager_name: str) -> dict:
    """修改项目负责人（写操作，需要用户确认）。

    Args:
        project_id: 项目ID
        manager_name: 新负责人真实姓名或登录用户名
    """
    db, user = require_db(), require_user()
    try:
        manager = _resolve_user_by_name(db, manager_name)
        p = project_service.update_project(
            db, user, project_id, ProjectUpdate(manager_id=manager.id)
        )
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {
        "status": "ok",
        "project_id": p.id,
        "project_name": p.name,
        "manager_id": manager.id,
        "manager_name": manager.real_name or manager.username,
        "message": f"已将项目负责人更新为 {manager.real_name or manager.username}",
    }
