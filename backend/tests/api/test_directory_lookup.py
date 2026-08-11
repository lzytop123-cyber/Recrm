"""公共通讯录：登录可读，不要求 org:view；员工管理仍需 org:view。"""

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
        module=permission_code.split(":")[0],
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


def test_schedule_user_can_use_directory_without_org_view(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_permission(
        db_session,
        username="sched_picker",
        permission_code="schedule:view",
    )
    headers = _auth_headers(client, "sched_picker")

    assert client.get("/api/v1/directory/departments", headers=headers).status_code == 200
    people = client.get("/api/v1/directory/people", headers=headers)
    assert people.status_code == 200
    body = people.json()
    assert "items" in body
    assert "total" in body

    projects = client.get("/api/v1/directory/projects", headers=headers)
    assert projects.status_code == 200
    assert "items" in projects.json()

    # 员工管理 / 项目管理仍需对应入口权限
    assert client.get("/api/v1/org/departments", headers=headers).status_code == 403
    assert client.get("/api/v1/org/employees", headers=headers).status_code == 403
    assert client.get("/api/v1/projects", headers=headers).status_code == 403


def test_ticket_user_can_pick_projects_without_project_view(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_permission(
        db_session,
        username="ticket_picker",
        permission_code="ticket:view",
    )
    headers = _auth_headers(client, "ticket_picker")
    assert client.get("/api/v1/directory/projects", headers=headers).status_code == 200
    assert client.get("/api/v1/projects", headers=headers).status_code == 403


def test_directory_people_returns_brief_fields_only(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_permission(
        db_session,
        username="lead_picker",
        permission_code="lead:view",
    )
    headers = _auth_headers(client, "lead_picker")
    response = client.get("/api/v1/directory/people?page_size=5", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    if items:
        row = items[0]
        assert "id" in row
        assert "username" in row
        assert "phone" not in row
        assert "email" not in row
        assert "roles" not in row
