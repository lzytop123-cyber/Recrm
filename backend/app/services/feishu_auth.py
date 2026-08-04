"""飞书 OAuth 网页登录：授权 URL、换票、拉取用户身份。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from jose import JWTError

from app.config import Settings, get_settings
from app.core.security import create_access_token, decode_access_token


class FeishuAuthError(Exception):
    """飞书开放平台调用失败。"""

    def __init__(self, message: str, *, detail: Any = None) -> None:
        super().__init__(message)
        self.detail = detail


@dataclass(frozen=True)
class FeishuIdentity:
    open_id: str
    union_id: str | None = None
    name: str | None = None
    email: str | None = None
    mobile: str | None = None
    avatar_url: str | None = None


def require_feishu_enabled(settings: Settings | None = None) -> Settings:
    cfg = settings or get_settings()
    if not cfg.feishu_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置飞书登录，请在 .env 填写 FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_REDIRECT_URI",
        )
    return cfg


def create_feishu_oauth_state(redirect: str = "/dashboard") -> str:
    """短时 state，防 CSRF，并带回登录后跳转路径。"""
    safe = redirect if redirect.startswith("/") else "/dashboard"
    return create_access_token(
        subject="feishu_oauth",
        extra_claims={"purpose": "feishu_oauth", "redirect": safe},
        expires_minutes=10,
    )


def parse_feishu_oauth_state(state: str) -> str:
    try:
        payload = decode_access_token(state)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="飞书登录 state 已失效") from exc
    if payload.get("purpose") != "feishu_oauth" or payload.get("sub") != "feishu_oauth":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的飞书登录 state")
    redirect = payload.get("redirect") or "/dashboard"
    if not isinstance(redirect, str) or not redirect.startswith("/"):
        return "/dashboard"
    return redirect


def build_authorize_url(*, redirect: str = "/dashboard", settings: Settings | None = None) -> tuple[str, str]:
    cfg = require_feishu_enabled(settings)
    state = create_feishu_oauth_state(redirect)
    query = urlencode(
        {
            "client_id": cfg.feishu_app_id,
            "redirect_uri": cfg.feishu_redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": cfg.feishu_scope,
        }
    )
    return f"{cfg.feishu_authorize_url}?{query}", state


def _raise_feishu(message: str, payload: Any = None) -> None:
    raise FeishuAuthError(message, detail=payload)


async def exchange_code_for_user_access_token(code: str, *, settings: Settings | None = None) -> str:
    cfg = require_feishu_enabled(settings)
    body = {
        "grant_type": "authorization_code",
        "client_id": cfg.feishu_app_id,
        "client_secret": cfg.feishu_app_secret,
        "code": code,
        "redirect_uri": cfg.feishu_redirect_uri,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(cfg.feishu_token_url, json=body)
    try:
        data = resp.json()
    except Exception as exc:
        raise FeishuAuthError(f"飞书换票响应无效: HTTP {resp.status_code}") from exc

    err_code = data.get("code")
    if resp.status_code >= 400 or (err_code not in (None, 0) and not data.get("access_token")):
        _raise_feishu(data.get("error_description") or data.get("msg") or "飞书换票失败", data)

    token = data.get("access_token")
    if not token:
        _raise_feishu("飞书换票未返回 access_token", data)
    return str(token)


async def fetch_feishu_user_info(user_access_token: str, *, settings: Settings | None = None) -> FeishuIdentity:
    cfg = settings or get_settings()
    headers = {"Authorization": f"Bearer {user_access_token}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(cfg.feishu_user_info_url, headers=headers)
    try:
        payload = resp.json()
    except Exception as exc:
        raise FeishuAuthError(f"飞书用户信息响应无效: HTTP {resp.status_code}") from exc

    if resp.status_code >= 400 or payload.get("code", 0) != 0:
        _raise_feishu(payload.get("msg") or "获取飞书用户信息失败", payload)

    data = payload.get("data") or {}
    open_id = data.get("open_id") or data.get("openId")
    if not open_id:
        _raise_feishu("飞书用户信息缺少 open_id", payload)

    return FeishuIdentity(
        open_id=str(open_id),
        union_id=(str(data["union_id"]) if data.get("union_id") else None),
        name=(str(data["name"]) if data.get("name") else None),
        email=(str(data["email"]) if data.get("email") else None),
        mobile=(str(data["mobile"]) if data.get("mobile") else None),
        avatar_url=(str(data["avatar_url"]) if data.get("avatar_url") else None),
    )


async def resolve_feishu_identity(code: str, *, settings: Settings | None = None) -> FeishuIdentity:
    token = await exchange_code_for_user_access_token(code, settings=settings)
    return await fetch_feishu_user_info(token, settings=settings)


def safe_parse_state(state: str | None) -> str:
    if not state:
        return "/dashboard"
    return parse_feishu_oauth_state(state)
