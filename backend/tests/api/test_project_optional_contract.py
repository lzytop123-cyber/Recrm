"""无合同可立项但须审批；有合同未到款须无到款例外。"""
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.permission import Permission
from app.models.project import RESOURCE_NEED_ACCEPTED, ProjectResourceNeed
from app.models.role import Role
from app.models.user import User
from app.schemas.project import ProjectPaymentDeferReviewRequest
from app.services import project as project_service


def _user_with_project(db: Session, username: str, *, admin: bool = False) -> User:
    codes = ("project:view", "project:manage")
    perms: list[Permission] = []
    for code in codes:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if not perm:
            perm = Permission(name=code, code=code, module="project")
            db.add(perm)
            db.flush()
        perms.append(perm)
    role = Role(
        name=f"{username}-role",
        code="admin" if admin else f"{username}_role",
        data_scope="company",
    )
    role.permissions.extend(perms)
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


def _signed_unpaid_contract(db: Session, owner: User, *, no: str) -> Contract:
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


def _accept_all_resources(db: Session, project_id: int) -> None:
    needs = (
        db.query(ProjectResourceNeed)
        .filter(ProjectResourceNeed.project_id == project_id)
        .all()
    )
    for need in needs:
        need.status = RESOURCE_NEED_ACCEPTED
    db.commit()


def test_no_contract_requires_reason_and_approval(
    client: TestClient,
    db_session: Session,
) -> None:
    me = _user_with_project(db_session, "noc_appr", admin=True)
    headers = _auth_headers(client, me.username)

    missing_reason = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "无合同无原因",
            "project_type": "ai_custom",
            "scope_desc": "内部预研",
        },
    )
    assert missing_reason.status_code == 400
    assert "原因" in missing_reason.json()["detail"]

    create = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "无合同交付",
            "project_type": "ai_custom",
            "scope_desc": "内部预研",
            "payment_deferred_reason": "客户口头确认，合同后补",
        },
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["contract_id"] is None
    assert body["payment_deferred"] is True
    assert body["payment_defer_status"] == "pending"
    pid = body["id"]

    _accept_all_resources(db_session, pid)
    blocked = client.post(f"/api/v1/projects/{pid}/plan", headers=headers)
    assert blocked.status_code == 400
    assert "无合同立项" in blocked.json()["detail"]

    project_service.review_payment_defer(
        db_session,
        me,
        pid,
        ProjectPaymentDeferReviewRequest(remark="同意先启动"),
        approve=True,
    )
    planned = client.post(f"/api/v1/projects/{pid}/plan", headers=headers)
    assert planned.status_code == 200, planned.text
    assert planned.json()["status"] == "planning"


def test_initiate_with_unpaid_contract_requires_defer(
    client: TestClient,
    db_session: Session,
) -> None:
    me = _user_with_project(db_session, "defer_req2")
    contract = _signed_unpaid_contract(db_session, me, no="HT-DEFER-REQ2")
    headers = _auth_headers(client, me.username)

    blocked = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "未到款未勾例外",
            "contract_id": contract.id,
            "project_type": "ai_product",
        },
    )
    assert blocked.status_code == 400
    assert "确认到账" in blocked.json()["detail"]

    ok = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "未到款勾例外",
            "contract_id": contract.id,
            "project_type": "ai_product",
            "payment_deferred": True,
            "payment_deferred_reason": "客户约定先干活后付款",
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["payment_deferred"] is True
    assert body["payment_defer_status"] == "pending"
    pid = body["id"]

    _accept_all_resources(db_session, pid)
    plan = client.post(f"/api/v1/projects/{pid}/plan", headers=headers)
    assert plan.status_code == 400
    assert "无到款" in plan.json()["detail"]
