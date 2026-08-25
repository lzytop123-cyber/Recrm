"""业务实体维度的审批操作日志：/api/v1/approvals/flow/activity。"""
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


def test_flow_activity_returns_audit_events_for_ticket(
    client: TestClient, db_session: Session
) -> None:
    dept = Department(name="交付部FA", code="DELIV_FA")
    perm_ticket = Permission(name="工单查看", code="ticket:view", module="ticket")
    perm_center = Permission(name="审批中心", code="approval:center", module="approval")
    role_lead = Role(name="部门负责人FA", code="dept_head", data_scope="department")
    role_sales = Role(name="销售FA", code="sales", data_scope="department")
    db_session.add_all([dept, perm_ticket, perm_center, role_lead, role_sales])
    db_session.flush()
    role_lead.permissions.extend([perm_ticket, perm_center])
    role_sales.permissions.append(perm_ticket)
    db_session.flush()

    def _mk(name: str, role: Role) -> User:
        u = User(
            username=name,
            password_hash=hash_password("secret123"),
            real_name=name,
            is_active=True,
            department_id=dept.id,
        )
        u.roles.append(role)
        db_session.add(u)
        return u

    lead = _mk("fa_lead", role_lead)
    sales = _mk("fa_sales", role_sales)
    db_session.commit()

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
    db_session.add(rule)
    db_session.commit()

    lead_h = _login(client, "fa_lead")
    sales_h = _login(client, "fa_sales")

    # lead 建单指派 sales（G-08 跳过 seq1 → 直接 seq2）→ sales 接单
    create = client.post(
        "/api/v1/tickets",
        headers=lead_h,
        json={
            "title": "flow_activity 用例",
            "ticket_type": "collaboration",
            "priority": "normal",
            "content": "验证审批日志接口",
            "department_id": dept.id,
            "assignee_ids": [sales.id],
        },
    )
    assert create.status_code == 200, create.text
    tid = create.json()["id"]

    accept = client.post(f"/api/v1/tickets/{tid}/accept", headers=sales_h)
    assert accept.status_code == 200, accept.text

    # 销售视角调"审批操作日志"：应能看到 submit + approve 至少 2 条
    #   —— 用逗号分隔的单值字符串（前端 axios 生产环境走的正是这条链路）
    resp = client.get(
        "/api/v1/approvals/flow/activity",
        headers=sales_h,
        params={"biz_type": "ticket,ticket_cross_accept", "biz_id": tid},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["biz_type"] == "ticket,ticket_cross_accept"
    assert body["biz_id"] == tid
    actions = [it["action"] for it in body["items"]]
    assert any(a.endswith("submit") for a in actions), actions
    assert any(a.endswith("approve") for a in actions), actions
    # 有 actor_name + action_label（中文标签）
    for it in body["items"]:
        assert it["action_label"]
        # sales 或 lead 参与
        assert it["actor_name"] in {"fa_lead", "fa_sales"}


def test_flow_activity_denied_for_unrelated_user(
    client: TestClient, db_session: Session
) -> None:
    """不能看的实体，接口 403。"""
    dept = Department(name="部门FA2", code="DEPT_FA2")
    perm_ticket = Permission(name="工单查看", code="ticket:view", module="ticket")
    role_sales = Role(name="销售FA2", code="sales", data_scope="personal")
    db_session.add_all([dept, perm_ticket, role_sales])
    db_session.flush()
    role_sales.permissions.append(perm_ticket)
    db_session.flush()

    def _mk(name: str) -> User:
        u = User(
            username=name,
            password_hash=hash_password("secret123"),
            real_name=name,
            is_active=True,
            department_id=dept.id,
        )
        u.roles.append(role_sales)
        db_session.add(u)
        return u

    creator = _mk("fa2_creator")
    outsider = _mk("fa2_outsider")
    db_session.commit()

    creator_h = _login(client, "fa2_creator")
    outsider_h = _login(client, "fa2_outsider")

    # creator 建单（自己是发起人+处理人）
    create = client.post(
        "/api/v1/tickets",
        headers=creator_h,
        json={
            "title": "私有工单",
            "ticket_type": "collaboration",
            "priority": "normal",
            "content": "只有 creator 能看",
            "department_id": dept.id,
        },
    )
    assert create.status_code == 200, create.text
    tid = create.json()["id"]

    # personal scope 下，outsider 看不到不是自己的工单
    resp = client.get(
        "/api/v1/approvals/flow/activity",
        headers=outsider_h,
        params={"biz_type": "ticket", "biz_id": tid},
    )
    assert resp.status_code == 403, resp.text


def test_flow_activity_multi_biz_type_same_entity(
    client: TestClient, db_session: Session
) -> None:
    """一次查一个实体的多个 biz_type（合同：contract + contract_terminate 同 biz_id）。"""
    dept = Department(name="部门FA3", code="DEPT_FA3")
    perm_ticket = Permission(name="工单查看", code="ticket:view", module="ticket")
    role_sales = Role(name="销售FA3", code="sales", data_scope="personal")
    db_session.add_all([dept, perm_ticket, role_sales])
    db_session.flush()
    role_sales.permissions.append(perm_ticket)
    db_session.flush()

    user = User(
        username="fa3_sales",
        password_hash=hash_password("secret123"),
        real_name="fa3_sales",
        is_active=True,
        department_id=dept.id,
    )
    user.roles.append(role_sales)
    db_session.add(user)
    db_session.commit()

    h = _login(client, "fa3_sales")
    # 无实体存在 → 404
    resp = client.get(
        "/api/v1/approvals/flow/activity",
        headers=h,
        params=[("biz_type", "contract"), ("biz_type", "contract_terminate"), ("biz_id", 99999)],
    )
    assert resp.status_code == 404, resp.text

    # 跨实体类型混传应 400
    resp2 = client.get(
        "/api/v1/approvals/flow/activity",
        headers=h,
        params=[("biz_type", "contract"), ("biz_type", "ticket"), ("biz_id", 1)],
    )
    assert resp2.status_code == 400, resp2.text
