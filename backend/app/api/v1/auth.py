"""认证接口：密码登录 / 飞书登录 / 当前用户 / 退出。

对齐 PRD：
- 账号有效才可进入；禁用账号拒绝新会话
- 飞书身份进入后系统内再次签发 JWT 并按权限鉴权
- 登录成功返回功能权限与数据范围
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_active_user
from app.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    FeishuAuthorizeResponse,
    FeishuCallbackRequest,
    FeishuLoginConfig,
    FeishuLoginResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    TokenResponse,
    UserInfoResponse,
)
from app.services.feishu_auth import (
    FeishuAuthError,
    build_authorize_url,
    resolve_feishu_identity,
    safe_parse_state,
)
from app.services.feishu_users import find_or_provision_feishu_user
from app.services.menu import build_user_info

router = APIRouter(prefix="/auth", tags=["认证"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _load_user_with_rbac(db: Session, username: str) -> User | None:
    return (
        db.query(User)
        .options(joinedload(User.roles).joinedload(Role.permissions))
        .filter(User.username == username)
        .first()
    )


def _write_audit(
    db: Session,
    *,
    user: User | None,
    action: str,
    ip: str | None,
    detail: str | None = None,
    username_hint: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            username=(user.username if user else None) or username_hint,
            action=action,
            module="auth",
            ip=ip,
            detail=detail,
        )
    )


def _authenticate(db: Session, username: str, password: str) -> User:
    """校验用户名密码；失败抛出 HTTPException。"""
    user = _load_user_with_rbac(db, username)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    return user


@router.post("/register", response_model=UserInfoResponse, summary="用户注册（仅调试）")
def register(
    payload: RegisterRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> UserInfoResponse:
    """仅 DEBUG 开放。正式环境账号由组织员工模块创建。"""
    if not get_settings().debug:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="正式环境禁止自助注册")

    exists = db.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        real_name=payload.real_name or payload.username,
        email=payload.email,
        is_active=True,
    )
    employee_role = db.query(Role).filter(Role.code == "employee").first()
    if employee_role:
        user.roles.append(employee_role)

    db.add(user)
    db.flush()
    _write_audit(db, user=user, action="register", ip=_client_ip(request))
    db.commit()

    user = _load_user_with_rbac(db, user.username)
    assert user is not None
    return build_user_info(user)


@router.post("/login", response_model=LoginResponse, summary="用户登录（JSON）")
def login_json(
    payload: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    """账号密码登录，返回 JWT + 用户信息。"""
    ip = _client_ip(request)
    try:
        user = _authenticate(db, payload.username, payload.password)
    except HTTPException as exc:
        action = "login_disabled" if exc.status_code == status.HTTP_403_FORBIDDEN else "login_failed"
        _write_audit(
            db,
            user=None,
            action=action,
            ip=ip,
            detail=f"username={payload.username}",
            username_hint=payload.username,
        )
        db.commit()
        raise

    token = create_access_token(subject=user.id)
    _write_audit(db, user=user, action="login", ip=ip)
    db.commit()
    return LoginResponse(access_token=token, user=build_user_info(user))


@router.post("/token", response_model=TokenResponse, summary="OAuth2 表单登录（Swagger 用）")
def login_form(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """兼容 /docs Authorize。"""
    user = _authenticate(db, form_data.username, form_data.password)
    return TokenResponse(access_token=create_access_token(subject=user.id))


@router.get("/feishu/config", response_model=FeishuLoginConfig, summary="飞书登录是否已配置")
def feishu_config() -> FeishuLoginConfig:
    settings = get_settings()
    return FeishuLoginConfig(
        enabled=settings.feishu_enabled,
        redirect_uri=settings.feishu_redirect_uri if settings.feishu_enabled else None,
    )


@router.get("/feishu/authorize", response_model=FeishuAuthorizeResponse, summary="获取飞书授权跳转地址")
def feishu_authorize(
    redirect: Annotated[str, Query(description="登录成功后前端跳转路径")] = "/dashboard",
) -> FeishuAuthorizeResponse:
    url, state = build_authorize_url(redirect=redirect)
    return FeishuAuthorizeResponse(authorize_url=url, state=state)


@router.post("/feishu/callback", response_model=FeishuLoginResponse, summary="飞书授权码换本系统登录态")
async def feishu_callback(
    payload: FeishuCallbackRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> FeishuLoginResponse:
    """前端回调页拿到 code 后调用；服务端换票、解析 open_id、签发 JWT。"""
    ip = _client_ip(request)
    redirect = safe_parse_state(payload.state)

    try:
        identity = await resolve_feishu_identity(payload.code)
        user = find_or_provision_feishu_user(db, identity)
    except FeishuAuthError as exc:
        _write_audit(
            db,
            user=None,
            action="feishu_login_failed",
            ip=ip,
            detail=str(exc),
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except HTTPException as exc:
        _write_audit(
            db,
            user=None,
            action="feishu_login_rejected",
            ip=ip,
            detail=f"{exc.detail}; redirect={redirect}",
        )
        db.commit()
        raise

    token = create_access_token(subject=user.id)
    _write_audit(
        db,
        user=user,
        action="feishu_login",
        ip=ip,
        detail=f"open_id={identity.open_id}",
    )
    db.commit()
    return FeishuLoginResponse(
        access_token=token,
        user=build_user_info(user),
        redirect=build_user_info(user).home_path if redirect in {"/dashboard", "/"} else redirect,
    )

@router.get("/me", response_model=UserInfoResponse, summary="当前登录用户信息与菜单")
def read_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserInfoResponse:
    """携带 Bearer Token 再次鉴权。"""
    return build_user_info(current_user)


@router.post("/logout", summary="退出登录")
def logout(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """JWT 无服务端会话；退出以客户端丢弃 Token 为准，此处写审计。"""
    _write_audit(db, user=current_user, action="logout", ip=_client_ip(request))
    db.commit()
    return {"message": "已退出登录"}
