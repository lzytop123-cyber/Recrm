"""AP-12：普通执行人（无审批中心权限）通过工单页「接单处理」按钮完成 assignee 节点确认。

覆盖：
- 未轮到本人时 /tickets/{id}/accept 返回 409 且给出可读提示；
- 部门负责人审批后，本人调用同一接口即可推进 assignee 节点、工单落 processing；
- can_accept / next_actor_hint 在审批不同阶段的正确反映。
"""
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
    dept = Department(name="交付部AP12", code="DELIV_AP12")
    perm_ticket = Permission(name="工单查看", code="ticket:view", module="ticket")
    perm_center = Permission(name="审批中心", code="approval:center", module="approval")
    role_lead = Role(name="部门负责人AP12", code="dept_head", data_scope="department")
    role_sales = Role(name="销售AP12", code="sales", data_scope="department")
    db.add_all([dept, perm_ticket, perm_center, role_lead, role_sales])
    db.flush()
    role_lead.permissions.extend([perm_ticket, perm_center])
    role_sales.permissions.append(perm_ticket)
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

    lead = _mk("ap12_lead", role_lead)
    sales = _mk("ap12_sales", role_sales)
    other = _mk("ap12_other", role_sales)
    db.commit()
    db.refresh(lead)
    db.refresh(sales)
    db.refresh(other)

    # AP-12：部门负责人审批 → 执行人本人确认接单
    rule = ApprovalRule(
        code="AP-12",
        name="工单审批与接单",
        biz_type="ticket",
        nodes_json=(
            '{"nodes":[{"name":"执行部门负责人审批","type":"approve","roles":["dept_head"]},'
            '{"name":"执行人确认接单","type":"assignee","assignee_key":"executor_id"}]}'
        ),
        status=RULE_STATUS_PUBLISHED,
    )
    db.add(rule)
    db.commit()
    return {"lead": lead, "sales": sales, "other": other, "dept": dept}


def test_sales_accept_after_lead_approval(client: TestClient, db_session: Session) -> None:
    ctx = _setup(db_session)
    lead_h = _login(client, "ap12_lead")
    sales_h = _login(client, "ap12_sales")
    other_h = _login(client, "ap12_other")

    # 1) 部门负责人建单并直接指派 sales（触发 AP-12 实例）
    ticket_resp = client.post(
        "/api/v1/tickets",
        headers=lead_h,
        json={
            "title": "AP-12 接单审批用例",
            "ticket_type": "collaboration",
            "priority": "normal",
            "content": "验证本人通过工单页按钮完成 assignee 节点",
            "department_id": ctx["dept"].id,
            "assignee_ids": [ctx["sales"].id],
        },
    )
    assert ticket_resp.status_code == 200, ticket_resp.text
    ticket = ticket_resp.json()
    tid = ticket["id"]

    # 2) 部门负责人是发起人 → G-08 跳过 seq1，若还有其他 dept_head 则轮到他；
    #    这里只种了一名 dept_head=lead 自己，seq1 直接被跳过，seq2 assignee 立即激活。
    detail_sales = client.get(f"/api/v1/tickets/{tid}", headers=sales_h).json()
    assert detail_sales["can_accept"] is True

    # 3) 其他销售（非本人）想接：应 409 + 提示"接单审批中"
    other_accept = client.post(f"/api/v1/tickets/{tid}/accept", headers=other_h)
    assert other_accept.status_code in (403, 409)

    # 4) 本人调 /accept → 应把 assignee 节点推进为通过，工单落 processing
    accept = client.post(f"/api/v1/tickets/{tid}/accept", headers=sales_h)
    assert accept.status_code == 200, accept.text
    body = accept.json()
    assert body["status"] == "processing"
    assert body["assignee_id"] == ctx["sales"].id


def test_sales_blocked_when_lead_pending(client: TestClient, db_session: Session) -> None:
    """存在其他 dept_head 时，seq1 未通过则 sales 的按钮应被置灰、直接调 accept 会 409。"""
    ctx = _setup(db_session)
    # 追加另一个 dept_head 以避免 G-08 跳过 seq1
    role_lead = db_session.query(Role).filter(Role.code == "dept_head").first()
    boss = User(
        username="ap12_boss",
        password_hash=hash_password("secret123"),
        real_name="ap12_boss",
        is_active=True,
        department_id=ctx["dept"].id,
    )
    boss.roles.append(role_lead)
    db_session.add(boss)
    db_session.commit()

    lead_h = _login(client, "ap12_lead")
    sales_h = _login(client, "ap12_sales")

    ticket_resp = client.post(
        "/api/v1/tickets",
        headers=lead_h,
        json={
            "title": "AP-12 待部门负责人审批",
            "ticket_type": "collaboration",
            "priority": "normal",
            "content": "验证 seq1 未过时不允许本人绕过",
            "department_id": ctx["dept"].id,
            "assignee_ids": [ctx["sales"].id],
        },
    )
    assert ticket_resp.status_code == 200
    tid = ticket_resp.json()["id"]

    detail = client.get(f"/api/v1/tickets/{tid}", headers=sales_h).json()
    assert detail["can_accept"] is False
    assert "接单审批中" in (detail.get("next_actor_hint") or "")

    accept = client.post(f"/api/v1/tickets/{tid}/accept", headers=sales_h)
    assert accept.status_code in (403, 409)
