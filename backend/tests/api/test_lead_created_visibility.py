"""线索录入岗：只能回看自己提交的线索（含待分配）。"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.schemas.lead import LeadCreate
from app.services import lead as lead_service


def _user(db: Session, username: str, *, role_code: str) -> User:
    role = Role(name=f"{username}-role", code=role_code, data_scope="department")
    perm = db.query(Permission).filter(Permission.code == "lead:view").first()
    if not perm:
        perm = Permission(name="线索查看", code="lead:view", module="lead")
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


def test_entry_role_lists_only_own_created_leads(
    client: TestClient, db_session: Session
) -> None:
    ops = _user(db_session, "ops_creator", role_code="operations")
    other = _user(db_session, "ops_other", role_code="employee")
    mine = lead_service.create_lead(
        db_session,
        ops,
        LeadCreate(company_name="运营自己的客户", phone="13800001111", self_follow=False),
    )
    others = lead_service.create_lead(
        db_session,
        other,
        LeadCreate(company_name="别人的客户", phone="13800002222", self_follow=False),
    )
    headers = _auth(client, ops.username)

    listed = client.get("/api/v1/leads", headers=headers, params={"pool": "created"})
    assert listed.status_code == 200, listed.text
    ids = {x["id"] for x in listed.json()["items"]}
    assert mine.id in ids
    assert others.id not in ids

    own = client.get(f"/api/v1/leads/{mine.id}", headers=headers)
    assert own.status_code == 200
    assert own.json()["company_name"] == "运营自己的客户"

    hidden = client.get(f"/api/v1/leads/{others.id}", headers=headers)
    assert hidden.status_code == 403
