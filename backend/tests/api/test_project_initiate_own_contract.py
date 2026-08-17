"""立项只能关联自己负责或创建的合同。"""
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def _user_with_project_view(db: Session, username: str) -> User:
    perm = db.query(Permission).filter(Permission.code == "project:view").first()
    if not perm:
        perm = Permission(name="查看项目", code="project:view", module="project")
        db.add(perm)
        db.flush()
    role = Role(name=f"{username}-role", code=f"{username}_role", data_scope="company")
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


def _auth_headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _signed_contract(db: Session, owner: User, *, no: str) -> Contract:
    customer = Customer(name=f"客户-{no}", owner_id=owner.id, creator_id=owner.id)
    db.add(customer)
    db.flush()
    contract = Contract(
        contract_no=no,
        title=f"合同-{no}",
        customer_id=customer.id,
        contract_type="ai_product",
        amount=Decimal("1000.00"),
        currency="CNY",
        status="signed",
        owner_id=owner.id,
        creator_id=owner.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def test_initiate_rejects_other_users_contract(
    client: TestClient,
    db_session: Session,
) -> None:
    me = _user_with_project_view(db_session, "init_owner")
    other = _user_with_project_view(db_session, "init_other")
    others_contract = _signed_contract(db_session, other, no="HT-INIT-OTHER")
    headers = _auth_headers(client, me.username)

    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "别人合同立项",
            "contract_id": others_contract.id,
            "project_type": "ai_product",
            "payment_deferred": True,
            "payment_deferred_reason": "测试越权",
        },
    )
    assert response.status_code == 403
    assert "自己" in response.json()["detail"]


def test_initiate_allows_own_contract(
    client: TestClient,
    db_session: Session,
) -> None:
    me = _user_with_project_view(db_session, "init_self")
    mine = _signed_contract(db_session, me, no="HT-INIT-MINE")
    headers = _auth_headers(client, me.username)

    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "自己合同立项",
            "contract_id": mine.id,
            "project_type": "ai_product",
            "payment_deferred": True,
            "payment_deferred_reason": "客户约定先干活后付款",
        },
    )
    assert response.status_code == 200
    assert response.json()["contract_id"] == mine.id
