"""Project initiation reads only contract gate facts, with project and ownership permissions."""
from datetime import date
from decimal import Decimal

import pytest

from app.core.security import create_access_token
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.finance import Receipt
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def _case(db, *, relation="owner", permission=True):
    role = Role(name="gate-role", code="admin" if relation == "admin" else "gate-role", data_scope="company")
    if permission:
        role.permissions.append(Permission(name="project gate", code="project:view", module="project"))
    actor = User(username="gate-user", password_hash="unused", is_active=True, roles=[role])
    other = User(username="other-user", password_hash="unused", is_active=True)
    db.add_all([actor, other])
    db.flush()
    customer = Customer(name="gate customer", owner_id=other.id, creator_id=other.id)
    db.add(customer)
    db.flush()
    contract = Contract(contract_no="GATE-001", title="private contract", customer_id=customer.id,
                        status="signed", contract_type="ai_custom", amount=Decimal("5000"),
                        owner_id=actor.id if relation == "owner" else other.id,
                        creator_id=actor.id if relation == "creator" else other.id)
    db.add(contract)
    db.commit()
    token = create_access_token(subject=str(actor.id))
    return contract, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("relation", ["owner", "creator", "admin"])
def test_project_gate_allows_own_contract_without_contract_view(client, db_session, relation):
    contract, headers = _case(db_session, relation=relation)
    if relation != "admin":
        assert client.get(f"/api/v1/contracts/{contract.id}", headers=headers).status_code == 403
    response = client.get(f"/api/v1/projects/contract-gate/{contract.id}", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"id": contract.id, "contract_type": "ai_custom", "status": "signed", "payment_ok": False}


def test_project_gate_rejects_unrelated_contract_even_with_company_scope(client, db_session):
    contract, headers = _case(db_session, relation="other")
    assert client.get(f"/api/v1/projects/contract-gate/{contract.id}", headers=headers).status_code == 403


def test_project_gate_requires_project_view(client, db_session):
    contract, headers = _case(db_session, permission=False)
    assert client.get(f"/api/v1/projects/contract-gate/{contract.id}", headers=headers).status_code == 403


@pytest.mark.parametrize("receipt_status, amount, payment_ok", [
    ("pending_review", "100", False), ("confirmed", "100", True), ("confirmed", "0", False),
])
def test_project_gate_uses_only_positive_confirmed_receipts(client, db_session, receipt_status, amount, payment_ok):
    contract, headers = _case(db_session)
    db_session.add(Receipt(receipt_no="GATE-RECEIPT", contract_id=contract.id, amount=Decimal(amount),
                           paid_date=date.today(), payer_name="payer", status=receipt_status))
    db_session.commit()
    response = client.get(f"/api/v1/projects/contract-gate/{contract.id}", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["payment_ok"] is payment_ok
    assert set(response.json()) == {"id", "contract_type", "status", "payment_ok"}


def test_project_gate_missing_contract_is_404(client, db_session):
    _, headers = _case(db_session)
    assert client.get("/api/v1/projects/contract-gate/99999", headers=headers).status_code == 404
