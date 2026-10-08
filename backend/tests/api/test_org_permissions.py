"""组织模块权限边界集成测试。"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def _create_user_with_permission(
    db: Session,
    *,
    username: str,
    permission_code: str,
) -> User:
    permission = Permission(
        name=permission_code,
        code=permission_code,
        module="org",
    )
    role = Role(
        name=f"{username}-role",
        code=f"{username}_role",
        data_scope="company",
    )
    role.permissions.append(permission)
    user = User(
        username=username,
        password_hash=hash_password("secret123"),
        real_name=username,
        is_active=True,
    )
    user.roles.append(role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_org_view_can_read_but_cannot_create_department(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_permission(
        db_session,
        username="org_reader",
        permission_code="org:view",
    )
    headers = _auth_headers(client, "org_reader")

    assert client.get("/api/v1/org/departments", headers=headers).status_code == 200

    response = client.post(
        "/api/v1/org/departments",
        headers=headers,
        json={"name": "越权部门", "code": "NOPE"},
    )
    assert response.status_code == 403


def test_org_view_cannot_reset_another_users_password(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_permission(
        db_session,
        username="org_reader",
        permission_code="org:view",
    )
    target = User(
        username="target_user",
        password_hash=hash_password("original123"),
        real_name="目标员工",
        is_active=True,
    )
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)
    headers = _auth_headers(client, "org_reader")

    response = client.post(
        f"/api/v1/org/employees/{target.id}/reset-password",
        headers=headers,
        json={"password": "changed123"},
    )
    assert response.status_code == 403


def test_org_manage_can_create_department_but_cannot_sync_feishu(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_permission(
        db_session,
        username="org_manager",
        permission_code="org:manage",
    )
    headers = _auth_headers(client, "org_manager")

    create_response = client.post(
        "/api/v1/org/departments",
        headers=headers,
        json={"name": "授权部门", "code": "ALLOWED"},
    )
    assert create_response.status_code == 200

    sync_response = client.post("/api/v1/org/feishu/sync", headers=headers)
    assert sync_response.status_code == 403


def test_org_manager_can_edit_own_profile_with_unchanged_roles(client: TestClient, db_session: Session) -> None:
    user = _create_user_with_permission(db_session, username="self_editor", permission_code="org:manage")
    headers = _auth_headers(client, user.username)
    response = client.patch(
        f"/api/v1/org/employees/{user.id}", headers=headers,
        json={"real_name": "更新姓名", "role_ids": [role.id for role in user.roles]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["real_name"] == "更新姓名"


def test_org_manager_cannot_change_own_roles(client: TestClient, db_session: Session) -> None:
    user = _create_user_with_permission(db_session, username="self_role_blocked", permission_code="org:manage")
    extra = Role(name="额外角色", code="extra_role_blocked", data_scope="self")
    db_session.add(extra)
    db_session.commit()
    db_session.refresh(extra)
    headers = _auth_headers(client, user.username)
    response = client.patch(
        f"/api/v1/org/employees/{user.id}",
        headers=headers,
        json={"role_ids": [role.id for role in user.roles] + [extra.id]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "不能修改自己的角色"


def test_admin_can_change_own_roles(client: TestClient, db_session: Session) -> None:
    admin_role = Role(name="系统管理员", code="admin", data_scope="company")
    extra = Role(name="额外角色", code="extra_for_admin", data_scope="self")
    db_session.add_all([admin_role, extra])
    user = User(
        username="sys_admin_self",
        password_hash=hash_password("secret123"),
        real_name="系统管理员",
        is_active=True,
    )
    user.roles.append(admin_role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(extra)
    headers = _auth_headers(client, user.username)
    response = client.patch(
        f"/api/v1/org/employees/{user.id}",
        headers=headers,
        json={"role_ids": [admin_role.id, extra.id]},
    )
    assert response.status_code == 200, response.text
    codes = {r["code"] for r in response.json()["roles"]}
    assert codes == {"admin", "extra_for_admin"}


def test_org_manager_cannot_disable_self_through_employment_status(client: TestClient, db_session: Session) -> None:
    user = _create_user_with_permission(db_session, username="self_resign", permission_code="org:manage")
    headers = _auth_headers(client, user.username)
    response = client.patch(
        f"/api/v1/org/employees/{user.id}", headers=headers,
        json={"employment_status": "离职"},
    )
    assert response.status_code == 400
    db_session.refresh(user)
    assert user.is_active is True

