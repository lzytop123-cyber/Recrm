"""公共通讯录：登录可读，不要求 org:view；员工管理仍需 org:view。"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def _create_user_with_permission(
    db: Session,
    *,
    username: str,
    permission_code: str,
) -> User:
    permission = db.query(Permission).filter(Permission.code == permission_code).first()
    if not permission:
        permission = Permission(
            name=permission_code,
            code=permission_code,
            module=permission_code.split(":")[0],
        )
        db.add(permission)
        db.flush()
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


def test_directory_contracts_mine_hides_others(
    client: TestClient,
    db_session: Session,
) -> None:
    mine_user = _create_user_with_permission(
        db_session,
        username="contract_mine",
        permission_code="project:view",
    )
    other_user = _create_user_with_permission(
        db_session,
        username="contract_other",
        permission_code="project:view",
    )
    customer = Customer(name="目录合同客户", owner_id=mine_user.id, creator_id=mine_user.id)
    db_session.add(customer)
    db_session.flush()
    mine_contract = Contract(
        contract_no="HT-MINE-001",
        title="我的合同",
        customer_id=customer.id,
        contract_type="ai_product",
        amount=Decimal("100.00"),
        currency="CNY",
        status="signed",
        owner_id=mine_user.id,
        creator_id=mine_user.id,
    )
    other_contract = Contract(
        contract_no="HT-OTHER-001",
        title="别人的合同",
        customer_id=customer.id,
        contract_type="ai_product",
        amount=Decimal("200.00"),
        currency="CNY",
        status="signed",
        owner_id=other_user.id,
        creator_id=other_user.id,
    )
    db_session.add_all([mine_contract, other_contract])
    db_session.commit()

    headers = _auth_headers(client, "contract_mine")
    all_rows = client.get("/api/v1/directory/contracts", headers=headers)
    assert all_rows.status_code == 200
    all_ids = {x["id"] for x in all_rows.json()["items"]}
    assert mine_contract.id in all_ids
    assert other_contract.id in all_ids

    mine_rows = client.get("/api/v1/directory/contracts?mine=true", headers=headers)
    assert mine_rows.status_code == 200
    mine_ids = {x["id"] for x in mine_rows.json()["items"]}
    assert mine_contract.id in mine_ids
    assert other_contract.id not in mine_ids
