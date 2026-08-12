"""
系统管理：角色权限、审计日志。
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import normalize_module_scopes
from app.models.associations import user_roles
from app.models.audit_log import AuditLog
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.schemas.system import RoleCreate, RoleUpdate

PROTECTED_ROLE_CODES = {"admin"}


def _known_modules(db: Session) -> set[str]:
    rows = db.query(Permission.module).distinct().all()
    return {m for (m,) in rows if m}


def enrich_role(db: Session, role: Role) -> Role:
    role.permission_ids = [p.id for p in role.permissions]  # type: ignore[attr-defined]
    role.permission_codes = [p.code for p in role.permissions]  # type: ignore[attr-defined]
    if not isinstance(getattr(role, "module_scopes", None), dict):
        role.module_scopes = {}
    role.user_count = (
        db.query(user_roles).filter(user_roles.c.role_id == role.id).count()
    )  # type: ignore[attr-defined]
    return role

def list_permissions(db: Session) -> list[Permission]:
    return db.query(Permission).order_by(Permission.module.asc(), Permission.id.asc()).all()


def list_roles(db: Session) -> list[Role]:
    roles = (
        db.query(Role)
        .options(joinedload(Role.permissions))
        .order_by(Role.id.asc())
        .all()
    )
    return [enrich_role(db, r) for r in roles]


def get_role(db: Session, role_id: int) -> Role:
    role = (
        db.query(Role)
        .options(joinedload(Role.permissions))
        .filter(Role.id == role_id)
        .first()
    )
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return enrich_role(db, role)


def _load_permissions(db: Session, permission_ids: list[int]) -> list[Permission]:
    if not permission_ids:
        return []
    perms = db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
    if len(perms) != len(set(permission_ids)):
        raise HTTPException(status_code=400, detail="存在无效权限")
    return perms


def create_role(db: Session, payload: RoleCreate) -> Role:
    code = payload.code.strip()
    if db.query(Role).filter(Role.code == code).first():
        raise HTTPException(status_code=400, detail="角色编码已存在")
    if db.query(Role).filter(Role.name == payload.name.strip()).first():
        raise HTTPException(status_code=400, detail="角色名称已存在")

    module_scopes = normalize_module_scopes(
        payload.module_scopes, known_modules=_known_modules(db)
    )
    role = Role(
        name=payload.name.strip(),
        code=code,
        description=payload.description,
        data_scope=payload.data_scope,
        module_scopes=module_scopes,
    )
    role.permissions = _load_permissions(db, payload.permission_ids)
    db.add(role)
    db.commit()
    return get_role(db, role.id)


def update_role(db: Session, role_id: int, payload: RoleUpdate) -> Role:
    role = db.query(Role).options(joinedload(Role.permissions)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    data = payload.model_dump(exclude_unset=True)
    permission_ids = data.pop("permission_ids", None)
    if "module_scopes" in data:
        data["module_scopes"] = normalize_module_scopes(
            data["module_scopes"], known_modules=_known_modules(db)
        )

    if role.code in PROTECTED_ROLE_CODES:
        # admin 角色只允许改描述；权限始终保持全部
        if "name" in data or "data_scope" in data or "module_scopes" in data:
            raise HTTPException(status_code=400, detail="系统管理员角色名称与数据范围不可修改")
        if permission_ids is not None:
            raise HTTPException(status_code=400, detail="系统管理员角色权限不可修改")
        if "description" in data:
            role.description = data["description"]
        db.commit()
        return get_role(db, role_id)

    if "name" in data and data["name"]:
        exists = (
            db.query(Role)
            .filter(Role.name == data["name"].strip(), Role.id != role_id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="角色名称已存在")
        data["name"] = data["name"].strip()

    for k, v in data.items():
        setattr(role, k, v)

    if permission_ids is not None:
        role.permissions = _load_permissions(db, permission_ids)

    db.commit()
    return get_role(db, role_id)

def delete_role(db: Session, role_id: int) -> None:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.code in PROTECTED_ROLE_CODES:
        raise HTTPException(status_code=400, detail="系统管理员角色不可删除")
    user_count = db.query(user_roles).filter(user_roles.c.role_id == role.id).count()
    if user_count:
        raise HTTPException(status_code=400, detail="仍有用户绑定该角色，无法删除")
    db.delete(role)
    db.commit()


def list_audit_logs(
    db: Session,
    *,
    module: Optional[str] = None,
    action: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[AuditLog]]:
    q = db.query(AuditLog)
    if module:
        q = q.filter(AuditLog.module == module)
    if action:
        q = q.filter(AuditLog.action == action)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(
            (AuditLog.username.like(like))
            | (AuditLog.detail.like(like))
            | (AuditLog.target_id.like(like))
        )
    total = q.count()
    items = (
        q.order_by(AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, items


def system_stats(db: Session) -> dict:
    return {
        "roles": db.query(Role).count(),
        "permissions": db.query(Permission).count(),
        "audit_logs": db.query(AuditLog).count(),
        "users": db.query(User).count(),
    }
