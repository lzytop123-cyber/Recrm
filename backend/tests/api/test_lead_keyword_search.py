"""线索列表关键字：客户主体之外，也能搜录入人 / 负责人姓名。"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.schemas.lead import LeadAssignRequest, LeadCreate
from app.services import lead as lead_service


def _user(db: Session, username: str, real_name: str, *, admin: bool = False) -> User:
    role = Role(
        name=f"{username}-role",
        code="admin" if admin else f"{username}_role",
        data_scope="company",
    )
    if not admin:
        perm = db.query(Permission).filter(Permission.code == "lead:view").first()
        if not perm:
            perm = Permission(name="线索查看", code="lead:view", module="lead")
            db.add(perm)
            db.flush()
        role.permissions.append(perm)
    user = User(
        username=username,
        password_hash=hash_password("secret123"),
        real_name=real_name,
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


def test_keyword_matches_creator_and_owner_names(
    client: TestClient, db_session: Session
) -> None:
    admin = _user(db_session, "kw_admin", "管理员", admin=True)
    creator = _user(db_session, "kw_creator", "张录入")
    owner = _user(db_session, "kw_owner", "李负责")
    lead = lead_service.create_lead(
        db_session,
        creator,
        LeadCreate(company_name="星河科技", phone="13900001111", self_follow=False),
    )
    lead_service.assign_lead(
        db_session, admin, lead.id, LeadAssignRequest(owner_id=owner.id)
    )
    headers = _auth(client, admin.username)

    by_creator = client.get(
        "/api/v1/leads", headers=headers, params={"pool": "all", "keyword": "张录入"}
    )
    assert by_creator.status_code == 200, by_creator.text
    assert {x["id"] for x in by_creator.json()["items"]} == {lead.id}

    by_owner = client.get(
        "/api/v1/leads", headers=headers, params={"pool": "all", "keyword": "李负责"}
    )
    assert by_owner.status_code == 200, by_owner.text
    assert {x["id"] for x in by_owner.json()["items"]} == {lead.id}

    by_company = client.get(
        "/api/v1/leads", headers=headers, params={"pool": "all", "keyword": "星河"}
    )
    assert {x["id"] for x in by_company.json()["items"]} == {lead.id}

    miss = client.get(
        "/api/v1/leads", headers=headers, params={"pool": "all", "keyword": "不存在的人"}
    )
    assert miss.json()["items"] == []
