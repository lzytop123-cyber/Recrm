"""合同完成：回款收齐才能完成，允许特批。"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.finance import (
    ALLOCATION_STATUS_ACTIVE,
    RECEIPT_STATUS_CONFIRMED,
    RECEIVABLE_STATUS_UNPAID,
    Receipt,
    ReceiptAllocation,
    ReceivablePlan,
)
from app.models.role import Role
from app.models.user import User


def _admin_headers(client: TestClient, db: Session) -> dict[str, str]:
    role = Role(name="测试管理员", code="admin", data_scope="company")
    user = User(
        username="complete_admin",
        password_hash=hash_password("secret123"),
        real_name="完成合同管理员",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "complete_admin", "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _active_contract(db: Session, owner: User, *, amount: Decimal) -> Contract:
    customer = Customer(
        name="完成合同客户",
        owner_id=owner.id,
        creator_id=owner.id,
    )
    db.add(customer)
    db.flush()
    contract = Contract(
        contract_no=f"HT-COMPLETE-{amount}",
        title="完成规则测试合同",
        customer_id=customer.id,
        contract_type="ai_product",
        amount=amount,
        currency="CNY",
        status="active",
        owner_id=owner.id,
        creator_id=owner.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def test_complete_blocked_when_receivable_outstanding(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    owner = db_session.query(User).filter(User.username == "complete_admin").one()
    contract = _active_contract(db_session, owner, amount=Decimal("100.00"))
    db_session.add(
        ReceivablePlan(
            contract_id=contract.id,
            sequence_no=1,
            title="合同款",
            amount=Decimal("100.00"),
            due_date=date.today(),
            currency="CNY",
            status=RECEIVABLE_STATUS_UNPAID,
            created_by=owner.id,
        )
    )
    db_session.commit()

    response = client.post(f"/api/v1/contracts/{contract.id}/complete", headers=headers, json={})
    assert response.status_code == 409
    assert "回款尚未收齐" in response.json()["detail"]


def test_complete_ok_when_fully_allocated(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    owner = db_session.query(User).filter(User.username == "complete_admin").one()
    contract = _active_contract(db_session, owner, amount=Decimal("200.00"))
    receivable = ReceivablePlan(
        contract_id=contract.id,
        sequence_no=1,
        title="合同款",
        amount=Decimal("200.00"),
        due_date=date.today(),
        currency="CNY",
        status=RECEIVABLE_STATUS_UNPAID,
        created_by=owner.id,
    )
    db_session.add(receivable)
    db_session.flush()
    receipt = Receipt(
        receipt_no="SK-COMPLETE-001",
        contract_id=contract.id,
        amount=Decimal("200.00"),
        paid_date=date.today(),
        payer_name="完成合同客户",
        status=RECEIPT_STATUS_CONFIRMED,
        submitted_by=owner.id,
        confirmed_by=owner.id,
    )
    db_session.add(receipt)
    db_session.flush()
    db_session.add(
        ReceiptAllocation(
            receipt_id=receipt.id,
            receivable_plan_id=receivable.id,
            amount=Decimal("200.00"),
            status=ALLOCATION_STATUS_ACTIVE,
            allocated_by=owner.id,
        )
    )
    db_session.commit()

    response = client.post(f"/api/v1/contracts/{contract.id}/complete", headers=headers, json={})
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_force_complete_with_reason(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    owner = db_session.query(User).filter(User.username == "complete_admin").one()
    contract = _active_contract(db_session, owner, amount=Decimal("300.00"))
    db_session.add(
        ReceivablePlan(
            contract_id=contract.id,
            sequence_no=1,
            title="合同款",
            amount=Decimal("300.00"),
            due_date=date.today(),
            currency="CNY",
            status=RECEIVABLE_STATUS_UNPAID,
            created_by=owner.id,
        )
    )
    db_session.commit()

    blocked = client.post(
        f"/api/v1/contracts/{contract.id}/complete",
        headers=headers,
        json={"force": True},
    )
    assert blocked.status_code == 400

    ok = client.post(
        f"/api/v1/contracts/{contract.id}/complete",
        headers=headers,
        json={"force": True, "force_reason": "客户分期尾款延后，管理层特批结案"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "completed"
    assert "特批完成" in (ok.json().get("remark") or "")


def test_sales_cannot_force_complete_without_perm(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.models.permission import Permission

    role = Role(name="销售", code="sales", data_scope="department")
    role.permissions.append(
        Permission(name="完成合同", code="contract:complete", module="contract")
    )
    user = User(
        username="sales_force",
        password_hash=hash_password("secret123"),
        real_name="销售甲",
        is_active=True,
    )
    user.roles.append(role)
    db_session.add_all([role, user])
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "sales_force", "password": "secret123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    contract = _active_contract(db_session, user, amount=Decimal("300.00"))
    db_session.add(
        ReceivablePlan(
            contract_id=contract.id,
            sequence_no=1,
            title="合同款",
            amount=Decimal("300.00"),
            due_date=date.today(),
            currency="CNY",
            status=RECEIVABLE_STATUS_UNPAID,
            created_by=user.id,
        )
    )
    db_session.commit()

    denied = client.post(
        f"/api/v1/contracts/{contract.id}/complete",
        headers=headers,
        json={"force": True, "force_reason": "销售自行特批"},
    )
    assert denied.status_code == 403
