"""登录接口验收：POST /api/v1/auth/login、/me、/logout。"""
from fastapi.testclient import TestClient

from app.models.user import User


def test_login_success_returns_token_and_user(client: TestClient, active_user: User) -> None:
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "alice"
    assert body["user"]["real_name"] == "爱丽丝"
    assert body["user"]["is_active"] is True
    assert body["user"]["data_scope"] == "personal"
    assert any(m["path"] == "/dashboard" for m in body["user"]["menus"])


def test_login_wrong_password(client: TestClient, active_user: User) -> None:
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "用户名或密码错误"


def test_login_unknown_user(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "secret123"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "用户名或密码错误"


def test_login_disabled_account_rejected(client: TestClient, disabled_user: User) -> None:
    resp = client.post("/api/v1/auth/login", json={"username": "bob", "password": "secret123"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "账号已禁用"


def test_me_requires_bearer_and_returns_profile(client: TestClient, active_user: User) -> None:
    login = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret123"})
    token = login.json()["access_token"]

    denied = client.get("/api/v1/auth/me")
    assert denied.status_code == 401

    ok = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["username"] == "alice"


def test_logout_writes_ok(client: TestClient, active_user: User) -> None:
    login = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret123"})
    token = login.json()["access_token"]
    resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["message"] == "已退出登录"
