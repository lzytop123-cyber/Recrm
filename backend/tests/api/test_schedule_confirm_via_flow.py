"""AP-14：排期本人（无审批中心权限）通过「确认本人档期」按钮完成 assignee 节点确认。"""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.approval_rule import RULE_STATUS_PUBLISHED, ApprovalRule
from app.models.department import Department
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def _login(client: TestClient, username: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _setup(db: Session) -> dict:
    dept = Department(name="内容部AP14", code="CONT_AP14")
    perm_sched = Permission(name="排期查看", code="schedule:view", module="schedule")
    perm_mng = Permission(name="排期管理", code="schedule:manage", module="schedule")
    role_lead = Role(name="部门负责人AP14", code="dept_head", data_scope="department")
    role_sales = Role(name="销售AP14", code="sales", data_scope="department")
    db.add_all([dept, perm_sched, perm_mng, role_lead, role_sales])
    db.flush()
    role_lead.permissions.extend([perm_sched, perm_mng])
    role_sales.permissions.append(perm_sched)
    db.flush()

    def _mk(name: str, role: Role) -> User:
        u = User(
            username=name,
            password_hash=hash_password("secret123"),
            real_name=name,
            is_active=True,
            department_id=dept.id,
        )
        u.roles.append(role)
        db.add(u)
        return u

    lead = _mk("ap14_lead", role_lead)
    sales = _mk("ap14_sales", role_sales)
    db.commit()
    db.refresh(lead)
    db.refresh(sales)

    rule = ApprovalRule(
        code="AP-14",
        name="排期确认",
        biz_type="schedule",
        nodes_json=(
            '{"nodes":[{"name":"执行人确认排期","type":"assignee","assignee_key":"owner_id"}]}'
        ),
        status=RULE_STATUS_PUBLISHED,
    )
    db.add(rule)
    db.commit()
    return {"lead": lead, "sales": sales, "dept": dept}


def test_owner_confirms_schedule_via_flow(client: TestClient, db_session: Session) -> None:
    ctx = _setup(db_session)
    lead_h = _login(client, "ap14_lead")
    sales_h = _login(client, "ap14_sales")

    start = (datetime.now() + timedelta(days=2)).replace(microsecond=0)
    end = start + timedelta(hours=2)
    # 部门负责人为销售建档期，AP-14 起单，唯一节点 assignee=销售
    create = client.post(
        "/api/v1/schedules",
        headers=lead_h,
        json={
            "title": "AP-14 档期确认用例",
            "schedule_type": "other",
            "resource_type": "other",
            "employee_id": ctx["sales"].id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    )
    assert create.status_code == 200, create.text
    sid = create.json()["id"]

    # 本人（sales）点确认本人档期：新逻辑应等价于推进 assignee 节点，档期落 confirmed
    confirm = client.post(f"/api/v1/schedules/{sid}/confirm", headers=sales_h)
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["status"] == "confirmed"
    assert body["confirmed_by"] == ctx["sales"].id
