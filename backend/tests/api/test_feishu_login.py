"""飞书登录相关 API 与用户绑定逻辑测试（mock 开放平台）。"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User
from app.services.feishu_auth import FeishuIdentity, create_feishu_oauth_state


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _enable_feishu(monkeypatch: pytest.MonkeyPatch, *, auto_provision: bool = False) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test_app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret_test")
    monkeypatch.setenv("FEISHU_REDIRECT_URI", "http://127.0.0.1:5173/login/feishu/callback")
    monkeypatch.setenv("FEISHU_AUTO_PROVISION", "true" if auto_provision else "false")
    get_settings.cache_clear()


def test_feishu_config_disabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "")
    monkeypatch.setenv("FEISHU_APP_SECRET", "")
    get_settings.cache_clear()
    resp = client.get("/api/v1/auth/feishu/config")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_feishu_authorize_requires_config(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "")
    monkeypatch.setenv("FEISHU_APP_SECRET", "")
    get_settings.cache_clear()
    resp = client.get("/api/v1/auth/feishu/authorize")
    assert resp.status_code == 503


def test_feishu_authorize_returns_url(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_feishu(monkeypatch)
    resp = client.get("/api/v1/auth/feishu/authorize", params={"redirect": "/leads"})
    assert resp.status_code == 200
    body = resp.json()
    assert "accounts.feishu.cn" in body["authorize_url"]
    assert "client_id=cli_test_app" in body["authorize_url"]
    assert body["state"]


def test_feishu_callback_binds_existing_open_id(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_feishu(monkeypatch)
    role = Role(name="普通员工", code="employee", data_scope="personal")
    db_session.add(role)
    user = User(
        username="feishu_user",
        password_hash=hash_password("x"),
        real_name="飞书用户",
        feishu_open_id="ou_abc123",
        is_active=True,
    )
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    identity = FeishuIdentity(open_id="ou_abc123", name="飞书用户", email="a@example.com")
    state = create_feishu_oauth_state("/dashboard")

    with patch(
        "app.api.v1.auth.resolve_feishu_identity",
        new=AsyncMock(return_value=identity),
    ):
        resp = client.post(
            "/api/v1/auth/feishu/callback",
            json={"code": "mock_code", "state": state},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["username"] == "feishu_user"


def test_feishu_callback_rejects_unbound_without_auto_provision(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_feishu(monkeypatch, auto_provision=False)
    identity = FeishuIdentity(open_id="ou_new", name="新人")
    state = create_feishu_oauth_state("/dashboard")

    with patch(
        "app.api.v1.auth.resolve_feishu_identity",
        new=AsyncMock(return_value=identity),
    ):
        resp = client.post(
            "/api/v1/auth/feishu/callback",
            json={"code": "mock_code", "state": state},
        )

    assert resp.status_code == 403
    assert "未绑定" in resp.json()["detail"]


def test_feishu_callback_auto_provisions(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_feishu(monkeypatch, auto_provision=True)
    db_session.add(Role(name="普通员工", code="employee", data_scope="personal"))
    db_session.commit()

    identity = FeishuIdentity(open_id="ou_auto_1", name="自动建号", email="auto@ztxd.com")
    state = create_feishu_oauth_state("/dashboard")

    with patch(
        "app.api.v1.auth.resolve_feishu_identity",
        new=AsyncMock(return_value=identity),
    ):
        resp = client.post(
            "/api/v1/auth/feishu/callback",
            json={"code": "mock_code", "state": state},
        )

    assert resp.status_code == 200
    created = db_session.query(User).filter(User.feishu_open_id == "ou_auto_1").first()
    assert created is not None
    assert created.email == "auto@ztxd.com"
