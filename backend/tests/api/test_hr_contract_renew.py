"""劳动合同续签：无规则直通、有审批、驳回、重复续签。"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.approval_rule import RULE_STATUS_PUBLISHED, ApprovalRule
from app.models.hr import LaborContract
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services import hr as hr_service


def _user(db: Session, username: str, *codes: str) -> User:
    role = Role(name=f"{username}-role", code=f"{username}_role", data_scope="company")
    for code in codes:
        role.permissions.append(Permission(name=code, code=code, module=code.split(":")[0]))
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


def _headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "secret123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_signed(client: TestClient, headers: dict, employee_id: int) -> dict:
    end = date.today() + timedelta(days=40)
    resp = client.post(
        "/api/v1/hr/contracts",
        headers=headers,
        json={
            "employee_id": employee_id,
            "contract_type": "fixed",
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(end),
            "status": "signed",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_renew_without_rule_applies_immediately(client: TestClient, db_session: Session) -> None:
    hr = _user(db_session, "hr_rn1", "org:view", "org:manage")
    emp = _user(db_session, "staff_rn1")
    headers = _headers(client, "hr_rn1")
    old = _create_signed(client, headers, emp.id)
    renew = client.post(
        f"/api/v1/hr/contracts/{old['id']}/renew",
        headers=headers,
        json={
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=365)),
        },
    )
    assert renew.status_code == 200, renew.text
    body = renew.json()
    assert body["status"] == "signed"
    assert body["version"] == old["version"] + 1
    assert body["supersedes_id"] == old["id"]
    old_detail = client.get(f"/api/v1/hr/contracts/{old['id']}", headers=headers).json()
    assert old_detail["status"] == "renewed"
    assert old_detail["renew_pending"] is False
    db_session.refresh(emp)
    assert emp.contract_end == date.today() + timedelta(days=365)


def test_renew_with_rule_pending_and_duplicate_blocked(client: TestClient, db_session: Session) -> None:
    hr = _user(db_session, "hr_rn2", "org:view", "org:manage")
    emp = _user(db_session, "staff_rn2")
    db_session.add(
        ApprovalRule(
            code="AP-HR-01-TEST",
            name="劳动合同续签测试",
            biz_type="labor_contract_renew",
            nodes_json='{"nodes":[{"name":"人事审批","type":"approve","roles":["hr"]}],"cc":[]}',
            status=RULE_STATUS_PUBLISHED,
        )
    )
    db_session.commit()
    headers = _headers(client, "hr_rn2")
    old = _create_signed(client, headers, emp.id)
    renew = client.post(
        f"/api/v1/hr/contracts/{old['id']}/renew",
        headers=headers,
        json={
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=400)),
        },
    )
    assert renew.status_code == 200, renew.text
    new = renew.json()
    assert new["status"] == "pending_sign"
    assert new["supersedes_id"] == old["id"]
    old_detail = client.get(f"/api/v1/hr/contracts/{old['id']}", headers=headers).json()
    assert old_detail["status"] == "signed"
    assert old_detail["renew_pending"] is True
    dup = client.post(
        f"/api/v1/hr/contracts/{old['id']}/renew",
        headers=headers,
        json={
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=401)),
        },
    )
    assert dup.status_code == 409
    assert "续签审批进行中" in dup.json()["detail"]


def test_renew_reject_cancels_new_keeps_old(client: TestClient, db_session: Session) -> None:
    hr = _user(db_session, "hr_rn3", "org:view", "org:manage")
    emp = _user(db_session, "staff_rn3")
    db_session.add(
        ApprovalRule(
            code="AP-HR-01-REJ",
            name="劳动合同续签驳回测试",
            biz_type="labor_contract_renew",
            nodes_json='{"nodes":[{"name":"人事审批","type":"approve","roles":["hr"]}],"cc":[]}',
            status=RULE_STATUS_PUBLISHED,
        )
    )
    db_session.commit()
    headers = _headers(client, "hr_rn3")
    old = _create_signed(client, headers, emp.id)
    renew = client.post(
        f"/api/v1/hr/contracts/{old['id']}/renew",
        headers=headers,
        json={
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=500)),
            "remark": "续签草案",
        },
    )
    assert renew.status_code == 200, renew.text
    new_id = renew.json()["id"]
    hr_service.on_contract_renew_result(
        db_session, SimpleNamespace(biz_id=new_id), approved=False, withdrawn=False
    )
    db_session.commit()
    new_row = db_session.query(LaborContract).filter(LaborContract.id == new_id).first()
    old_row = db_session.query(LaborContract).filter(LaborContract.id == old["id"]).first()
    assert new_row is not None and new_row.status == "cancelled"
    assert "续签驳回" in (new_row.remark or "")
    assert old_row is not None and old_row.status == "signed"
    old_detail = client.get(f"/api/v1/hr/contracts/{old['id']}", headers=headers).json()
    assert old_detail["renew_pending"] is False
    # 驳回后可再次续签
    again = client.post(
        f"/api/v1/hr/contracts/{old['id']}/renew",
        headers=headers,
        json={
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=501)),
        },
    )
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "pending_sign"


def test_renew_approve_marks_old_renewed(client: TestClient, db_session: Session) -> None:
    hr = _user(db_session, "hr_rn4", "org:view", "org:manage")
    emp = _user(db_session, "staff_rn4")
    db_session.add(
        ApprovalRule(
            code="AP-HR-01-OK",
            name="劳动合同续签通过测试",
            biz_type="labor_contract_renew",
            nodes_json='{"nodes":[{"name":"人事审批","type":"approve","roles":["hr"]}],"cc":[]}',
            status=RULE_STATUS_PUBLISHED,
        )
    )
    db_session.commit()
    headers = _headers(client, "hr_rn4")
    old = _create_signed(client, headers, emp.id)
    renew = client.post(
        f"/api/v1/hr/contracts/{old['id']}/renew",
        headers=headers,
        json={
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=600)),
        },
    )
    assert renew.status_code == 200, renew.text
    new_id = renew.json()["id"]
    hr_service.on_contract_renew_result(
        db_session, SimpleNamespace(biz_id=new_id), approved=True
    )
    db_session.commit()
    new_row = db_session.query(LaborContract).filter(LaborContract.id == new_id).first()
    old_row = db_session.query(LaborContract).filter(LaborContract.id == old["id"]).first()
    assert new_row is not None and new_row.status == "signed"
    assert old_row is not None and old_row.status == "renewed"
    db_session.refresh(emp)
    assert emp.contract_end == date.today() + timedelta(days=600)


def test_renew_rejects_non_signed(client: TestClient, db_session: Session) -> None:
    hr = _user(db_session, "hr_rn5", "org:view", "org:manage")
    emp = _user(db_session, "staff_rn5")
    headers = _headers(client, "hr_rn5")
    created = client.post(
        "/api/v1/hr/contracts",
        headers=headers,
        json={
            "employee_id": emp.id,
            "contract_type": "fixed",
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=30)),
            "status": "pending_sign",
        },
    )
    assert created.status_code == 200, created.text
    resp = client.post(
        f"/api/v1/hr/contracts/{created.json()['id']}/renew",
        headers=headers,
        json={
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=365)),
        },
    )
    assert resp.status_code == 409
    assert "仅已签合同可续签" in resp.json()["detail"]
