"""API 依赖：当前用户、权限校验。"""
from typing import Annotated, Callable, Iterable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import require_permissions
from app.core.security import TokenError, get_subject_from_token
from app.database import get_db
from app.models.role import Role
from app.models.user import User

# Swagger /docs 里 Authorize 会走此端点拿 token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """从 Authorization: Bearer <token> 解析当前用户（含角色与权限）。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或登录已失效",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = int(get_subject_from_token(token))
    except (TokenError, ValueError) as exc:
        raise credentials_exception from exc

    user = (
        db.query(User)
        .options(joinedload(User.roles).joinedload(Role.permissions))
        .filter(User.id == user_id)
        .first()
    )
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    return current_user


def PermissionChecker(required: Iterable[str], *, any_of: bool = False) -> Callable:
    """
    路由级 RBAC 依赖工厂。
    用法：Depends(PermissionChecker(["lead:view"]))
    """

    def _checker(current_user: Annotated[User, Depends(get_current_active_user)]) -> User:
        require_permissions(current_user, required, any_of=any_of)
        return current_user

    return _checker
