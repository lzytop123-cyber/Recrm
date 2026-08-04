"""内部验收提交后进入审批，通过后才可结项。"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.project import (
    EVIDENCE_STATUS_CONFIRMED,
    MILESTONE_STATUS_DONE,
    Project,
    ProjectMilestone,
)
from app.models.role import Role
from app.models.user import User


def _admin_headers(client: TestClient, db: Session) -> tuple[dict[str, str], User]:
    role = Role(name="测试管理员", code="admin", data_scope="company")
    user = User(
        username="accept_admin",
        password_hash=hash_password("secret123"),
        real_name="验收管理员",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "accept_admin", "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, user


def _ready_project(db: Session, owner: User) -> Project:
    customer = Customer(name="验收客户", owner_id=owner.id, creator_id=owner.id)
    db.add(customer)
    db.flush()
    contract = Contract(
        contract_no="HT-ACCEPT-001",
        title="验收合同",
        customer_id=customer.id,
        contract_type="ai_product",
        amount=Decimal("1000.00"),
        currency="CNY",
        status="active",
        owner_id=owner.id,
        creator_id=owner.id,
    )
    db.add(contract)
    db.flush()
    project = Project(
        project_no="PJ-ACCEPT-001",
        name="验收测试项目",
        contract_id=contract.id,
        customer_id=customer.id,
        project_type="ai_product",
        status="executing",
        manager_id=owner.id,
        creator_id=owner.id,
        progress=80,
    )
    db.add(project)
    db.flush()
    ms = ProjectMilestone(
        project_id=project.id,
        name="里程碑1",
        status=MILESTONE_STATUS_DONE,
        evidence="交付包 v1",
        evidence_status=EVIDENCE_STATUS_CONFIRMED,
        evidence_confirmed_by=owner.id,
        sort_order=1,
    )
    db.add(ms)
    db.commit()
    db.refresh(project)
    return project


def test_acceptance_requires_approval_before_complete(
    client: TestClient, db_session: Session
) -> None:
    headers, owner = _admin_headers(client, db_session)
    project = _ready_project(db_session, owner)

    submit = client.post(
        f"/api/v1/projects/{project.id}/accept",
        headers=headers,
        json={
            "result": "pass",
            "accepted_at": date.today().isoformat(),
            "method": "内部验收单",
            "conclusion": "范围已交付，遗留无",
            "attachment": "验收单.pdf",
            "attachment_path": "acceptance/demo.pdf",
        },
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["status"] == "accepting"
    assert body["acceptance_approval_status"] == "pending"

    pending = client.get(
        "/api/v1/approvals",
        headers=headers,
        params={"tab": "pending", "page": 1, "page_size": 50},
    )
    assert pending.status_code == 200
    assert any(i["type"] == "project_acceptance" for i in pending.json()["items"])

    complete_too_early = client.post(
        f"/api/v1/projects/{project.id}/complete",
        headers=headers,
    )
    assert complete_too_early.status_code == 400

    approve = client.post(
        f"/api/v1/projects/{project.id}/acceptance/confirm",
        headers=headers,
        json={},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "accepted"
    assert approve.json()["acceptance_approval_status"] == "approved"

    finance = client.post(
        f"/api/v1/projects/{project.id}/finance-check",
        headers=headers,
        json={},
    )
    assert finance.status_code == 200
    assert finance.json()["finance_check_status"] == "pending"
    assert finance.json()["finance_check_passed"] is False

    complete_no_finance = client.post(
        f"/api/v1/projects/{project.id}/complete",
        headers=headers,
    )
    assert complete_no_finance.status_code == 400

    finance_ok = client.post(
        f"/api/v1/projects/{project.id}/finance-check/confirm",
        headers=headers,
        json={},
    )
    assert finance_ok.status_code == 200
    assert finance_ok.json()["finance_check_passed"] is True
    assert finance_ok.json()["finance_check_status"] == "approved"

    complete = client.post(
        f"/api/v1/projects/{project.id}/complete",
        headers=headers,
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"
