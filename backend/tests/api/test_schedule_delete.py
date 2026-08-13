"""排期删除：仅系统管理员，已完成也可删。"""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.schedule import SCHEDULE_STATUS_COMPLETED, Schedule
from app.models.user import User


def _user(db: Session, username: str, *, role_code: str, perm_codes: list[str]) -> User:
    role = Role(name=f"{username}-role", code=role_code, data_scope="company")
    for code in perm_codes:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if not perm:
            perm = Permission(name=code, code=code, module=code.split(":")[0])
            db.add(perm)
            db.flush()
        role.permissions.append(perm)
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


def _auth(client: TestClient, username: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_schedule(client: TestClient, headers: dict[str, str], employee_id: int) -> int:
    start = datetime.now(timezone.utc).replace(microsecond=0)
    resp = client.post(
        "/api/v1/schedules",
        headers=headers,
        json={
            "title": "口播拍摄",
            "employee_id": employee_id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=1)).isoformat(),
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_admin_can_delete_completed_schedule(client: TestClient, db_session: Session) -> None:
    admin = _user(db_session, "sch_admin", role_code="admin", perm_codes=["schedule:view"])
    staff = _user(db_session, "sch_staff", role_code="employee", perm_codes=["schedule:view"])
    admin_headers = _auth(client, admin.username)
    staff_headers = _auth(client, staff.username)

    sid = _create_schedule(client, staff_headers, staff.id)
    row = db_session.query(Schedule).filter(Schedule.id == sid).first()
    assert row is not None
    row.status = SCHEDULE_STATUS_COMPLETED
    db_session.commit()

    forbidden = client.delete(f"/api/v1/schedules/{sid}", headers=staff_headers)
    assert forbidden.status_code == 403

    ok = client.delete(f"/api/v1/schedules/{sid}", headers=admin_headers)
    assert ok.status_code == 200, ok.text
    assert ok.json()["ok"] is True

    gone = client.get(f"/api/v1/schedules/{sid}", headers=admin_headers)
    assert gone.status_code == 404


def test_non_admin_cannot_delete_pending_schedule(
    client: TestClient, db_session: Session
) -> None:
    staff = _user(db_session, "sch_staff2", role_code="employee", perm_codes=["schedule:view"])
    headers = _auth(client, staff.username)
    sid = _create_schedule(client, headers, staff.id)
    resp = client.delete(f"/api/v1/schedules/{sid}", headers=headers)
    assert resp.status_code == 403
    still = client.get(f"/api/v1/schedules/{sid}", headers=headers)
    assert still.status_code == 200
