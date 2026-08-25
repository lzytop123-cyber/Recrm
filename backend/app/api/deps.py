"""API 依赖：当前用户、权限校验。"""
from typing import Annotated, Callable, Iterable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import require_permissions
from app.core.security import TokenError, get_subject_from_token
from app.database import get_db
from app.models.department import Department
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
    user.dept_scope_ids = _compute_dept_scope_ids(db, user.department_id)  # type: ignore[attr-defined]
    return user


def _compute_dept_scope_ids(db: Session, root_id: Optional[int]) -> set[int]:
    """本部门 + 全部子孙部门 id；用于 data_scope=department 的可见范围过滤。

    在请求入口一次算好挂到 user 上，避免各 service 层重复查询。
    """
    if not root_id:
        return set()
    rows = db.query(Department.id, Department.parent_id).all()
    children_map: dict[Optional[int], list[int]] = {}
    for dept_id, parent_id in rows:
        children_map.setdefault(parent_id, []).append(dept_id)
    result: set[int] = set()
    stack = [root_id]
    while stack:
        cur = stack.pop()
        if cur in result:
            continue
        result.add(cur)
        stack.extend(children_map.get(cur, []))
    return result


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
