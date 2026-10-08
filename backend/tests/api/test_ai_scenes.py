"""S2–S5 场景 HTTP。"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.approval_flow import INSTANCE_PENDING, TASK_ACTIVE, ApprovalInstance, ApprovalTask
from app.models.customer import Customer, CustomerFollowUp
from app.models.knowledge import KnowledgeArticle, KnowledgeSpace
from app.models.lead import Lead, LeadFollowUp
from app.models.permission import Permission
from app.models.project import Project
from app.models.role import Role
from app.models.ticket import Ticket
from app.models.timesheet import Timesheet
from app.models.user import User


def _user(db: Session, username: str) -> User:
    role = Role(name=f"{username}-role", code=f"{username}_role", data_scope="company")
    for code in (
        "knowledge:view",
        "timesheet:view",
        "project:view",
        "lead:view",
        "customer:view",
        "ticket:view",
        "approval:center",
    ):
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
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_daily_report_draft_and_submit(client: TestClient, db_session: Session) -> None:
    user = _user(db_session, "scene_http_s2")
    customer = Customer(name="日报客户", owner_id=user.id, creator_id=user.id)
    db_session.add(customer)
    db_session.flush()
    project = Project(
        project_no="PJ-HTTP-S2",
        name="日报项目",
        customer_id=customer.id,
        project_type="other",
        status="executing",
        manager_id=user.id,
        creator_id=user.id,
    )
    db_session.add(project)
    db_session.flush()
    db_session.add(
        Timesheet(
            user_id=user.id,
            work_date=date.today(),
            hours=Decimal("2.5"),
            work_type="project",
            project_id=project.id,
            content="联调知识库接口",
            status="submitted",
        )
    )
    db_session.commit()
    headers = _headers(client, user.username)
    created = client.post("/api/v1/agent/scenes/daily-report", json={"date": str(date.today())}, headers=headers)
    assert created.status_code == 200, created.text
    draft = created.json()
    assert draft["status"] == "draft"
    assert draft["hours_total"] == 2.5
    assert any("联调知识库接口" in line for line in draft["today_work"])
    assert "编造" not in "".join(draft["today_work"])
    before = db_session.query(Timesheet).count()
    submitted = client.post(
        f"/api/v1/agent/scenes/daily-report/{draft['id']}/submit",
        json={"body": "今日：联调知识库接口 2.5h"},
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    assert db_session.query(Timesheet).count() == before
    again = client.post(
        f"/api/v1/agent/scenes/daily-report/{draft['id']}/submit",
        json={"body": "再交一次"},
        headers=headers,
    )
    assert again.status_code == 409


def test_followup_summary_does_not_write(client: TestClient, db_session: Session) -> None:
    user = _user(db_session, "scene_http_s3")
    now = datetime.now(timezone.utc)
    lead = Lead(
        name="王经理",
        company_name="跟进公司",
        status="following",
        owner_id=user.id,
        creator_id=user.id,
    )
    db_session.add(lead)
    db_session.flush()
    db_session.add(
        LeadFollowUp(
            lead_id=lead.id,
            user_id=user.id,
            follow_at=now,
            method="phone",
            content="对方关心报价周期",
            result="keep",
            next_follow_at=now,
        )
    )
    db_session.commit()
    headers = _headers(client, user.username)
    resp = client.post(
        "/api/v1/agent/scenes/followup-summary",
        json={"lead_id": lead.id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    card = resp.json()
    assert card["executed"] is False
    assert "对方关心报价周期" in card["summary"]
    assert card["next_actions"][0]["source"] == "lead"
    assert db_session.query(LeadFollowUp).filter(LeadFollowUp.lead_id == lead.id).count() == 1


def test_ticket_recommendations(client: TestClient, db_session: Session) -> None:
    user = _user(db_session, "scene_http_s4")
    space = KnowledgeSpace(code="policy-http", name="制度", icon="制", sort_order=1)
    db_session.add(space)
    db_session.flush()
    db_session.add(
        KnowledgeArticle(
            title="打印机故障处理",
            space_id=space.id,
            content="先重启交换机，再重装驱动。",
            status="published",
        )
    )
    current = Ticket(
        ticket_no="TK-HTTP-NOW",
        title="办公室打印机无法连接网络",
        content="打印队列卡住",
        creator_id=user.id,
        status="processing",
    )
    old = Ticket(
        ticket_no="TK-HTTP-OLD",
        title="打印机连不上网络",
        content="打印队列卡住，重启后好了",
        creator_id=user.id,
        status="closed",
        result="重启交换机后恢复",
    )
    db_session.add_all([current, old])
    db_session.commit()
    headers = _headers(client, user.username)
    resp = client.get(f"/api/v1/tickets/{current.id}/recommendations", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["similar_tickets"][0]["ticket_no"] == "TK-HTTP-OLD"
    assert data["knowledge"]["citations"][0]["title"] == "打印机故障处理"


def test_approval_precheck_audit(client: TestClient, db_session: Session) -> None:
    user = _user(db_session, "scene_http_s5")
    inst = ApprovalInstance(
        code="AF-SCENE-S5",
        rule_code="AP-TEST",
        biz_type="timesheet",
        biz_id=1,
        title="测试预审",
        summary="单元测试",
        status=INSTANCE_PENDING,
        current_seq=1,
        initiator_id=user.id,
        initiator_name=user.real_name,
        version=1,
    )
    db_session.add(inst)
    db_session.flush()
    db_session.add(
        ApprovalTask(
            instance_id=inst.id,
            seq=1,
            name="确认",
            node_type="assignee",
            roles_json="[]",
            assignee_id=user.id,
            status=TASK_ACTIVE,
        )
    )
    db_session.commit()
    headers = _headers(client, user.username)
    missing = client.get("/api/v1/approvals/approval_instance:99999/precheck", headers=headers)
    assert missing.status_code == 404
    resp = client.get(f"/api/v1/approvals/approval_instance:{inst.id}/precheck", headers=headers)
    assert resp.status_code == 200, resp.text
    report = resp.json()
    assert report["model_version"] == "facts-v1"
    assert report["created_at"]
    assert report["approval"]["title"] == "测试预审"
    calls = client.get("/api/v1/ai/calls", headers=headers)
    assert calls.status_code == 200
    assert any(item["scene"] == "approval_precheck" and item["id"] == report["id"] for item in calls.json()["items"])
