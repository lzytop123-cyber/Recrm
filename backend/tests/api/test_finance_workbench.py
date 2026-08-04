"""财务工作台必须区分到账确认和应收核销。"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.role import Role
from app.models.user import User


def _admin_headers(client: TestClient, db: Session) -> dict[str, str]:
    role = Role(name="测试管理员", code="admin", data_scope="company")
    user = User(
        username="finance_admin",
        password_hash=hash_password("secret123"),
        real_name="财务管理员",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "finance_admin", "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _contract(db: Session, owner: User) -> Contract:
    customer = Customer(
        name="核销测试客户",
        owner_id=owner.id,
        creator_id=owner.id,
    )
    db.add(customer)
    db.flush()
    contract = Contract(
        contract_no="HT-FINANCE-001",
        title="财务闭环测试合同",
        customer_id=customer.id,
        contract_type="ai_product",
        amount=Decimal("500.00"),
        currency="CNY",
        status="active",
        owner_id=owner.id,
        creator_id=owner.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def test_workbench_lists_confirmation_separately_from_allocation(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    owner = db_session.query(User).filter(User.username == "finance_admin").one()
    contract = _contract(db_session, owner)

    receivable_response = client.post(
        f"/api/v1/contracts/{contract.id}/receivables",
        headers=headers,
        json={
            "title": "首付款",
            "amount": 500,
            "due_date": date.today().isoformat(),
        },
    )
    assert receivable_response.status_code == 200
    receivable_id = receivable_response.json()["id"]

    receipt_response = client.post(
        "/api/v1/receipts",
        headers=headers,
        json={
            "contract_id": contract.id,
            "amount": 500,
            "paid_date": date.today().isoformat(),
            "payer_name": "核销测试客户",
            "idempotency_key": "receipt-finance-001",
        },
    )
    assert receipt_response.status_code == 200
    receipt = receipt_response.json()

    confirm_response = client.post(
        f"/api/v1/receipts/{receipt['id']}/confirm",
        headers=headers,
        json={"version": receipt["version"]},
    )
    assert confirm_response.status_code == 200

    before_allocation = client.get(
        "/api/v1/receipts",
        headers=headers,
        params={"page": 1, "page_size": 20},
    )
    assert before_allocation.status_code == 200
    before_item = before_allocation.json()["items"][0]
    assert before_item["status"] == "confirmed"
    assert Decimal(before_item["allocated_amount"]) == Decimal("0")
    assert Decimal(before_item["available_amount"]) == Decimal("500")

    allocation_response = client.post(
        f"/api/v1/receipts/{receipt['id']}/allocations",
        headers=headers,
        json={
            "receivable_plan_id": receivable_id,
            "amount": 300,
            "idempotency_key": "allocation-finance-001",
        },
    )
    assert allocation_response.status_code == 200
    allocation = allocation_response.json()
    assert allocation["status"] == "pending"

    # 待审阶段：占用可用余额，但不计入已核销
    pending_receipts = client.get(
        "/api/v1/receipts",
        headers=headers,
        params={"page": 1, "page_size": 20},
    )
    pending_item = pending_receipts.json()["items"][0]
    assert Decimal(pending_item["allocated_amount"]) == Decimal("0")
    assert Decimal(pending_item["pending_allocation_amount"]) == Decimal("300")
    assert Decimal(pending_item["available_amount"]) == Decimal("200")

    pending_receivables = client.get(
        "/api/v1/receivables",
        headers=headers,
        params={"page": 1, "page_size": 20},
    )
    pending_receivable = pending_receivables.json()["items"][0]
    assert Decimal(pending_receivable["allocated_amount"]) == Decimal("0")
    assert Decimal(pending_receivable["outstanding_amount"]) == Decimal("200")

    approve_response = client.post(
        f"/api/v1/allocations/{allocation['id']}/confirm",
        headers=headers,
        json={"version": allocation["version"]},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "active"

    receivables = client.get(
        "/api/v1/receivables",
        headers=headers,
        params={"page": 1, "page_size": 20},
    )
    assert receivables.status_code == 200
    receivable = receivables.json()["items"][0]
    assert receivable["contract_no"] == "HT-FINANCE-001"
    assert receivable["customer_name"] == "核销测试客户"
    assert Decimal(receivable["allocated_amount"]) == Decimal("300")
    assert Decimal(receivable["outstanding_amount"]) == Decimal("200")
    assert receivable["effective_status"] == "partially_paid"

    receipts = client.get(
        "/api/v1/receipts",
        headers=headers,
        params={"page": 1, "page_size": 20},
    )
    receipt_item = receipts.json()["items"][0]
    assert Decimal(receipt_item["allocated_amount"]) == Decimal("300")
    assert Decimal(receipt_item["pending_allocation_amount"]) == Decimal("0")
    assert Decimal(receipt_item["available_amount"]) == Decimal("200")

    stats = client.get("/api/v1/finance/stats", headers=headers)
    assert stats.status_code == 200
    assert Decimal(stats.json()["confirmed_receipt_amount"]) == Decimal("500")
    assert Decimal(stats.json()["allocated_amount"]) == Decimal("300")
    assert Decimal(stats.json()["unallocated_receipt_amount"]) == Decimal("200")
    assert Decimal(stats.json()["outstanding_receivable_amount"]) == Decimal("200")

    approvals = client.get(
        "/api/v1/approvals",
        headers=headers,
        params={"tab": "processed", "page": 1, "page_size": 50},
    )
    assert approvals.status_code == 200
    assert any(item["type"] == "allocation" for item in approvals.json()["items"])
