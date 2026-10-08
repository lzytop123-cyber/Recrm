"""G2-003 人事闭环：合同、转岗、离职交接、假勤、工资条。"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.hr import HrPayslip
from app.models.lead import Lead
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


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


def test_labor_contract_ledger(client: TestClient, db_session: Session) -> None:
    hr = _user(db_session, "hr_mgr", "org:view", "org:manage")
    emp = _user(db_session, "staff_a")
    headers = _headers(client, "hr_mgr")
    end = date.today() + timedelta(days=20)
    created = client.post(
        "/api/v1/hr/contracts",
        headers=headers,
        json={
            "employee_id": emp.id,
            "contract_type": "fixed",
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(end),
            "status": "signed",
            "attachment": "劳动合同扫描件.pdf",
            "attachment_path": "labor_contract/demo_scan.pdf",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["file_path"] == "labor_contract/demo_scan.pdf"
    assert body["attachment_path"] == "labor_contract/demo_scan.pdf"
    assert body["attachment"] == "劳动合同扫描件.pdf"
    listed = client.get("/api/v1/hr/contracts", headers=headers, params={"page": 1, "page_size": 10})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    hit = next(x for x in listed.json()["items"] if x["id"] == body["id"])
    assert hit["attachment_path"] == "labor_contract/demo_scan.pdf"
    assert hit["attachment"]  # 列表从路径回填文件名
    assert "attachment" in hit and "attachment_path" in hit
    # 仅传 path 时，attachment 从文件名回填
    only_path = client.post(
        "/api/v1/hr/contracts",
        headers=headers,
        json={
            "employee_id": emp.id,
            "contract_type": "fixed",
            "signed_on": str(date.today()),
            "start_date": str(date.today()),
            "end_date": str(end),
            "status": "signed",
            "file_path": "labor_contract/uuid_合同.pdf",
        },
    )
    assert only_path.status_code == 200, only_path.text
    assert only_path.json()["attachment"] == "uuid_合同.pdf"
    assert only_path.json()["attachment_path"] == "labor_contract/uuid_合同.pdf"
    expiring = client.get("/api/v1/hr/contracts/expiring", headers=headers, params={"days": 30})
    assert expiring.status_code == 200
    assert expiring.json()["total"] >= 1


def test_transfer_applies_without_rule(client: TestClient, db_session: Session) -> None:
    src = Department(name="销售", code="sales_hr")
    dst = Department(name="交付", code="delivery_hr")
    db_session.add_all([src, dst])
    db_session.commit()
    hr = _user(db_session, "hr_xfer", "org:view", "org:manage")
    emp = _user(db_session, "staff_xfer")
    emp.department_id = src.id
    db_session.commit()
    headers = _headers(client, "hr_xfer")
    resp = client.post(
        "/api/v1/hr/transfers",
        headers=headers,
        json={
            "employee_id": emp.id,
            "to_department_id": dst.id,
            "effective_on": str(date.today()),
            "reason": "业务需要",
            "job_title": "交付专员",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "applied"
    db_session.refresh(emp)
    assert emp.department_id == dst.id


def test_resignation_handover_blocks_then_completes(client: TestClient, db_session: Session) -> None:
    hr = _user(db_session, "hr_leave", "org:view", "org:manage")
    emp = _user(db_session, "staff_leave")
    recv = _user(db_session, "staff_recv")
    db_session.add(Lead(name="待交接线索", owner_id=emp.id, status="following"))
    db_session.commit()
    headers = _headers(client, "hr_leave")
    created = client.post(
        "/api/v1/hr/resignations",
        headers=headers,
        json={
            "employee_id": emp.id,
            "last_working_day": str(date.today() + timedelta(days=7)),
            "reason": "个人原因",
        },
    )
    assert created.status_code == 200, created.text
    handover_id = created.json()["handover_id"]
    assert handover_id
    ho = client.get(f"/api/v1/hr/handovers/{handover_id}", headers=headers).json()
    assert ho["can_complete"] is False
    item_id = ho["items"][0]["id"]
    assigned = client.post(
        f"/api/v1/hr/handovers/{handover_id}/items/{item_id}/assign",
        headers=headers,
        json={"assignee_id": recv.id},
    )
    assert assigned.status_code == 200
    confirmed = client.post(
        f"/api/v1/hr/handovers/{handover_id}/items/{item_id}/confirm",
        headers=headers,
    )
    assert confirmed.status_code == 200
    done = client.post(f"/api/v1/hr/handovers/{handover_id}/complete", headers=headers)
    assert done.status_code == 200, done.text
    db_session.refresh(emp)
    assert emp.is_active is False


def test_leave_and_payslip(client: TestClient, db_session: Session) -> None:
    hr = _user(db_session, "hr_pay", "org:view", "org:manage", "payment:view")
    emp = _user(db_session, "staff_pay")
    headers = _headers(client, "hr_pay")
    bal = client.post(
        "/api/v1/hr/leave-balances",
        headers=headers,
        params={"employee_id": emp.id, "leave_type": "annual", "quota": 5},
    )
    assert bal.status_code == 200, bal.text
    emp_headers = _headers(client, "staff_pay")
    leave = client.post(
        "/api/v1/hr/leave-requests",
        headers=emp_headers,
        json={
            "leave_type": "annual",
            "start_date": str(date.today()),
            "end_date": str(date.today()),
            "days": 1,
            "reason": "事假",
        },
    )
    assert leave.status_code == 200, leave.text
    assert leave.json()["status"] == "approved"

    db_session.add(
        HrPayslip(
            employee_id=emp.id,
            period_label="2026-08",
            version=1,
            status="published",
            base_amount=Decimal("8000"),
            performance_amount=Decimal("1200"),
            adjustment_amount=Decimal("0"),
            total_amount=Decimal("9200"),
            items_json='[{"name":"绩效工资","amount":"1200"}]',
        )
    )
    db_session.commit()
    mine = client.get("/api/v1/payslips/me", headers=emp_headers)
    assert mine.status_code == 200
    assert mine.json()["total"] == 1
    pid = mine.json()["items"][0]["id"]
    detail = client.get(f"/api/v1/payslips/{pid}", headers=emp_headers)
    assert detail.status_code == 200
    board = client.get("/api/v1/hr/dashboard", headers=headers)
    assert board.status_code == 200
    assert board.json()["headcount"] >= 1
