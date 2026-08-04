"""合同签署不再自动生成应收；应收计划由财务/合同侧手动创建以便分期。"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.finance import ReceivablePlan
from app.models.role import Role
from app.models.user import User


def _admin_headers(client: TestClient, db: Session) -> dict[str, str]:
    role = Role(name="测试管理员", code="admin", data_scope="company")
    user = User(
        username="sign_recv_admin",
        password_hash=hash_password("secret123"),
        real_name="签署应收管理员",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "sign_recv_admin", "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _approved_contract(db: Session, owner: User, *, amount: Decimal) -> Contract:
    customer = Customer(
        name="签署应收测试客户",
        owner_id=owner.id,
        creator_id=owner.id,
    )
    db.add(customer)
    db.flush()
    contract = Contract(
        contract_no=f"HT-SIGN-RECV-{amount}",
        title="签署应收测试合同",
        customer_id=customer.id,
        contract_type="ai_product",
        amount=amount,
        currency="CNY",
        status="approved",
        owner_id=owner.id,
        creator_id=owner.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def test_sign_does_not_auto_create_receivable(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    owner = db_session.query(User).filter(User.username == "sign_recv_admin").one()
    contract = _approved_contract(db_session, owner, amount=Decimal("1000.00"))

    sign_response = client.post(
        f"/api/v1/contracts/{contract.id}/sign",
        headers=headers,
        json={},
    )
    assert sign_response.status_code == 200
    assert sign_response.json()["status"] == "signed"

    receivables = client.get(
        f"/api/v1/contracts/{contract.id}/receivables",
        headers=headers,
    )
    assert receivables.status_code == 200
    assert receivables.json() == []


def test_sign_keeps_manual_receivables(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    owner = db_session.query(User).filter(User.username == "sign_recv_admin").one()
    contract = _approved_contract(db_session, owner, amount=Decimal("800.00"))
    db_session.add(
        ReceivablePlan(
            contract_id=contract.id,
            sequence_no=1,
            title="首付款",
            amount=Decimal("300.00"),
            due_date=date.today(),
            currency="CNY",
            created_by=owner.id,
            remark="手动预置",
        )
    )
    db_session.add(
        ReceivablePlan(
            contract_id=contract.id,
            sequence_no=2,
            title="尾款",
            amount=Decimal("500.00"),
            due_date=date.today(),
            currency="CNY",
            created_by=owner.id,
            remark="手动预置",
        )
    )
    db_session.commit()

    sign_response = client.post(
        f"/api/v1/contracts/{contract.id}/sign",
        headers=headers,
        json={},
    )
    assert sign_response.status_code == 200

    receivables = client.get(
        f"/api/v1/contracts/{contract.id}/receivables",
        headers=headers,
    )
    assert receivables.status_code == 200
    items = receivables.json()
    assert len(items) == 2
    assert {x["title"] for x in items} == {"首付款", "尾款"}
