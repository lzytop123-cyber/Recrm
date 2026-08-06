"""我的待办聚合接口。"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


def _headers(client: TestClient, db: Session) -> dict[str, str]:
    role = Role(name="系统管理员", code="admin", data_scope="company")
    user = User(
        username="todo_admin",
        password_hash=hash_password("secret123"),
        real_name="待办管理员",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "todo_admin", "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_list_my_todos_shape(client: TestClient, db_session: Session) -> None:
    headers = _headers(client, db_session)
    resp = client.get("/api/v1/todos", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body
    assert "counts" in body
    assert "items" in body
    assert "partial_errors" in body
    assert isinstance(body["items"], list)
    assert isinstance(body["partial_errors"], list)
    for key in ("approval", "ticket", "lead", "task", "schedule", "resource"):
        assert key in body["counts"]
        assert body["counts"][key] >= 0


def test_me_includes_todos_menu(client: TestClient, db_session: Session) -> None:
    headers = _headers(client, db_session)
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    menus = resp.json().get("menus") or []
    paths = [m.get("path") for m in menus]
    assert "/todos" in paths


def test_approval_rules_mounted(client: TestClient, db_session: Session) -> None:
    headers = _headers(client, db_session)
    resp = client.get("/api/v1/approval-rules", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body
    assert "items" in body


def test_published_rule_attaches_to_pending_meta(
    client: TestClient, db_session: Session
) -> None:
    from decimal import Decimal

    from app.core.security import hash_password
    from app.models.contract import CONTRACT_STATUS_PENDING_APPROVAL, Contract
    from app.models.customer import Customer
    from app.models.role import Role
    from app.models.user import User
    from app.services import approval as approval_service

    role = Role(name="系统管理员", code="admin", data_scope="company")
    user = User(
        username="rule_attach_admin",
        password_hash=hash_password("secret123"),
        real_name="规则挂载管理员",
        is_active=True,
    )
    user.roles.append(role)
    customer = Customer(name="规则挂接客户", owner_id=user.id, creator_id=user.id)
    db_session.add_all([role, user, customer])
    db_session.commit()
    db_session.refresh(user)

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "rule_attach_admin", "password": "secret123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post(
        "/api/v1/approval-rules",
        headers=headers,
        json={
            "code": "contract_todo_rule",
            "name": "合同待办规则",
            "biz_type": "contract",
            "nodes_json": '[{"name":"财务审批"}]',
            "timeout_hours": 24,
        },
    )
    assert created.status_code == 200
    rule_id = created.json()["id"]
    published = client.post(f"/api/v1/approval-rules/{rule_id}/publish", headers=headers)
    assert published.status_code == 200

    contract = Contract(
        contract_no="HT-RULE-ATTACH-001",
        title="规则挂接合同",
        customer_id=customer.id,
        contract_type="other",
        status=CONTRACT_STATUS_PENDING_APPROVAL,
        amount=Decimal("1000"),
        currency="CNY",
        creator_id=user.id,
        owner_id=user.id,
    )
    db_session.add(contract)
    db_session.commit()

    items = approval_service.list_pending_approvals(db_session, user)
    matched = [x for x in items if x.id == f"contract:{contract.id}"]
    assert matched
    assert matched[0].meta.get("rule_code") == "contract_todo_rule"
    assert matched[0].meta.get("rule_version") == 1
    assert matched[0].meta.get("rule_timeout_hours") == 24
