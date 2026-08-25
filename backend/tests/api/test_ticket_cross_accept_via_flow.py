"""AP-13：跨部门工单发起人（可能是销售，无审批中心权限）通过「验收并关闭」按钮完成 assignee 节点。"""
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
    # 两个部门：sales 发起工单，交付部承接
    sales_dept = Department(name="销售部AP13", code="SALES_AP13")
    deliv_dept = Department(name="交付部AP13", code="DELIV_AP13")
    perm_ticket = Permission(name="工单查看", code="ticket:view", module="ticket")
    perm_center = Permission(name="审批中心", code="approval:center", module="approval")
    role_sales = Role(name="销售AP13", code="sales", data_scope="department")
    role_lead = Role(name="部门负责人AP13", code="dept_head", data_scope="department")
    db.add_all([sales_dept, deliv_dept, perm_ticket, perm_center, role_sales, role_lead])
    db.flush()
    role_sales.permissions.append(perm_ticket)
    role_lead.permissions.extend([perm_ticket, perm_center])
    db.flush()

    def _mk(name: str, dept: Department, role: Role) -> User:
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

    creator = _mk("ap13_sales", sales_dept, role_sales)  # 发起人（销售）
    lead = _mk("ap13_lead", deliv_dept, role_lead)  # 交付部负责人（分派+处理）
    db.commit()
    db.refresh(creator)
    db.refresh(lead)

    # AP-12（工单接单）；此测试里创建者不是被指派人，故 seq2 assignee=lead
    ap12 = ApprovalRule(
        code="AP-12",
        name="工单审批与接单",
        biz_type="ticket",
        nodes_json=(
            '{"nodes":[{"name":"执行部门负责人审批","type":"approve","roles":["dept_head"]},'
            '{"name":"执行人确认接单","type":"assignee","assignee_key":"executor_id"}]}'
        ),
        status=RULE_STATUS_PUBLISHED,
    )
    ap13 = ApprovalRule(
        code="AP-13",
        name="跨部门工单验收",
        biz_type="ticket_cross_accept",
        nodes_json=(
            '{"nodes":[{"name":"发起人验收","type":"assignee","assignee_key":"creator_id"}]}'
        ),
        status=RULE_STATUS_PUBLISHED,
    )
    db.add_all([ap12, ap13])
    db.commit()
    return {"creator": creator, "lead": lead, "sales_dept": sales_dept, "deliv_dept": deliv_dept}


def test_cross_dept_creator_confirms_via_flow(client: TestClient, db_session: Session) -> None:
    ctx = _setup(db_session)
    sales_h = _login(client, "ap13_sales")
    lead_h = _login(client, "ap13_lead")

    # 1) 销售建跨部门工单，承接部门=交付部，指派 lead
    create = client.post(
        "/api/v1/tickets",
        headers=sales_h,
        json={
            "title": "AP-13 跨部门验收用例",
            "ticket_type": "collaboration",
            "priority": "normal",
            "content": "验证发起人本人通过按钮完成 AP-13 assignee",
            "department_id": ctx["deliv_dept"].id,
            "assignee_ids": [ctx["lead"].id],
        },
    )
    assert create.status_code == 200, create.text
    tid = create.json()["id"]

    # 2) lead 是被指派人；AP-12 seq1（dept_head）里只有 lead，seq1 命中 seq1 待 lead 审批
    #    直接让 lead 走审批中心通过 seq1 + seq2
    lst = client.get("/api/v1/approvals", headers=lead_h, params={"status": "pending"}).json()
    inst_id = next(x["meta"]["instance_id"] for x in lst["items"] if x["source"] == "AP-12")
    approve1 = client.post(
        f"/api/v1/approvals/approval_instance:{inst_id}/approve",
        headers=lead_h,
        json={"comment": "同意"},
    )
    assert approve1.status_code == 200, approve1.text
    # seq2 assignee=lead 本人 —— lead 通过工单页按钮接单
    accept = client.post(f"/api/v1/tickets/{tid}/accept", headers=lead_h)
    assert accept.status_code == 200, accept.text
    assert accept.json()["status"] == "processing"

    # 3) lead 提交处理结果 → 触发 AP-13 起单（跨部门），assignee=creator
    complete = client.post(
        f"/api/v1/tickets/{tid}/complete",
        headers=lead_h,
        json={"result": "已完成"},
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] == "pending_confirm"

    # 4) 销售详情页应看到 next_actor_hint = 等你验收，can_confirm=true
    detail = client.get(f"/api/v1/tickets/{tid}", headers=sales_h).json()
    assert detail["can_confirm"] is True
    assert "验收" in (detail.get("next_actor_hint") or "")

    # 5) 销售调 /confirm 带满意度关闭 → 推进 AP-13 assignee + 走关闭逻辑
    confirm = client.post(
        f"/api/v1/tickets/{tid}/confirm",
        headers=sales_h,
        json={"satisfaction": 5, "comment": "赞", "close": True},
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["status"] == "closed"
    assert body["satisfaction"] == 5
