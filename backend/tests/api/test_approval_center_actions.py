"""审批中心 P0：stats / detail / 规则 CRUD。"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


def _admin_headers(client: TestClient, db: Session) -> dict[str, str]:
    role = Role(name="系统管理员", code="admin", data_scope="company")
    user = User(
        username="approval_admin",
        password_hash=hash_password("secret123"),
        real_name="审批管理员",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "approval_admin", "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_can_list_approval_stats(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client, db_session)
    resp = client.get("/api/v1/approvals/stats", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "pending" in body
    assert "initiated" in body
    assert "processed" in body
    assert "cc" in body
    assert body["pending"] >= 0


def test_get_detail_404_for_unknown(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client, db_session)
    resp = client.get("/api/v1/approvals/contract:999999", headers=headers)
    assert resp.status_code == 404


def test_create_rule_and_publish(client: TestClient, db_session: Session) -> None:
    headers = _admin_headers(client, db_session)
    create = client.post(
        "/api/v1/approval-rules",
        headers=headers,
        json={
            "code": "contract_default",
            "name": "合同默认审批",
            "biz_type": "contract",
            "nodes_json": '[{"name":"财务审批"}]',
            "timeout_hours": 48,
            "remark": "测试规则",
        },
    )
    assert create.status_code == 200
    rule = create.json()
    assert rule["code"] == "contract_default"
    assert rule["status"] == "draft"
    assert rule["version"] == 1

    publish = client.post(
        f"/api/v1/approval-rules/{rule['id']}/publish",
        headers=headers,
    )
    assert publish.status_code == 200
    published = publish.json()
    assert published["status"] == "published"
    assert published["published_at"] is not None
