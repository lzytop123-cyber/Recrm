"""飞书用户与本地账号绑定 / 自动建号。"""
from __future__ import annotations

import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import Settings, get_settings
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User
from app.services.feishu_auth import FeishuIdentity


def _load_user_by_id(db: Session, user_id: int) -> User:
    user = (
        db.query(User)
        .options(joinedload(User.roles).joinedload(Role.permissions))
        .filter(User.id == user_id)
        .first()
    )
    assert user is not None
    return user


def _username_from_identity(identity: FeishuIdentity) -> str:
    if identity.email and "@" in identity.email:
        local = identity.email.split("@", 1)[0]
        candidate = "".join(ch for ch in local if ch.isalnum() or ch in "._-")[:40]
        if candidate:
            return candidate
    suffix = identity.open_id.replace("ou_", "")[-24:]
    return f"fs_{suffix}"[:50]


def find_or_provision_feishu_user(
    db: Session,
    identity: FeishuIdentity,
    *,
    settings: Settings | None = None,
) -> User:
    """
    解析本地用户：
    1) 已绑定 feishu_open_id
    2) 邮箱匹配未绑定账号 → 自动绑定
    3) 开启 auto_provision → 创建员工账号并绑定
    4) 否则拒绝（需管理员在组织模块预建并绑定）
    """
    cfg = settings or get_settings()

    by_open_id = (
        db.query(User)
        .options(joinedload(User.roles).joinedload(Role.permissions))
        .filter(User.feishu_open_id == identity.open_id)
        .first()
    )
    if by_open_id:
        if not by_open_id.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
        return by_open_id

    if identity.email:
        by_email = (
            db.query(User)
            .options(joinedload(User.roles).joinedload(Role.permissions))
            .filter(User.email == identity.email)
            .first()
        )
        if by_email:
            if not by_email.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
            if by_email.feishu_open_id and by_email.feishu_open_id != identity.open_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="该邮箱已绑定其他飞书账号，请联系管理员",
                )
            by_email.feishu_open_id = identity.open_id
            if identity.name and not by_email.real_name:
                by_email.real_name = identity.name
            if identity.mobile and not by_email.phone:
                by_email.phone = identity.mobile
            db.flush()
            return _load_user_by_id(db, by_email.id)

    if not cfg.feishu_auto_provision:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "飞书账号未绑定系统用户，请联系管理员在「组织员工」中绑定后再登录"
                f"（open_id={identity.open_id}）"
            ),
        )

    base = _username_from_identity(identity)
    username = base
    n = 1
    while db.query(User).filter(User.username == username).first() is not None:
        n += 1
        username = f"{base[:40]}_{n}"[:50]

    user = User(
        username=username,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        real_name=identity.name or username,
        email=identity.email,
        phone=identity.mobile,
        feishu_open_id=identity.open_id,
        is_active=True,
    )
    employee_role = db.query(Role).filter(Role.code == "employee").first()
    if employee_role:
        user.roles.append(employee_role)
    db.add(user)
    db.flush()
    return _load_user_by_id(db, user.id)
