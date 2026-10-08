"""S2–S5 Agent 取数工具。"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.agent.runtime import agent_runtime
from app.core.security import hash_password
from app.models.customer import Customer, CustomerFollowUp
from app.models.knowledge import KnowledgeArticle, KnowledgeSpace
from app.models.lead import Lead, LeadFollowUp
from app.models.permission import Permission
from app.models.project import Project, ProjectMilestone, ProjectTask
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


def test_get_work_report_facts(db_session: Session) -> None:
    from app.agent.tools.work_report import get_work_report_facts

    user = _user(db_session, "scene_s2")
    customer = Customer(name="日报客户", owner_id=user.id, creator_id=user.id)
    db_session.add(customer)
    db_session.flush()
    project = Project(
        project_no="PJ-S2-001",
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
    db_session.add(
        ProjectTask(
            task_no="T-S2-1",
            project_id=project.id,
            title="待办任务",
            assignee_id=user.id,
            status="doing",
            due_date=date.today(),
        )
    )
    db_session.add(
        ProjectMilestone(
            project_id=project.id,
            name="接口联调",
            status="doing",
            deadline=date.today(),
        )
    )
    db_session.commit()
    with agent_runtime(db_session, user):
        facts = get_work_report_facts.invoke({"period": "today"})
    assert facts["hours_total"] == 2.5
    assert facts["timesheets"][0]["content"] == "联调知识库接口"
    assert any(t["title"] == "待办任务" for t in facts["tasks_open"])
    assert any(m["name"] == "接口联调" for m in facts["milestones"])


def test_get_followup_records(db_session: Session) -> None:
    from app.agent.tools.followup import get_followup_records

    user = _user(db_session, "scene_s3")
    now = datetime.now(timezone.utc)
    lead = Lead(
        name="王经理",
        company_name="跟进公司",
        status="following",
        owner_id=user.id,
        creator_id=user.id,
        need_desc="要一套 CRM",
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
        )
    )
    customer = Customer(name="跟进客户", owner_id=user.id, creator_id=user.id)
    db_session.add(customer)
    db_session.flush()
    db_session.add(
        CustomerFollowUp(
            customer_id=customer.id,
            user_id=user.id,
            follow_at=now,
            method="wechat",
            content="约下周演示",
        )
    )
    db_session.commit()
    with agent_runtime(db_session, user):
        empty = get_followup_records.invoke({})
        data = get_followup_records.invoke({"lead_id": lead.id, "customer_id": customer.id})
    assert "error" in empty
    assert data["lead"]["name"] == "王经理"
    texts = [r["content"] for r in data["records"]]
    assert "对方关心报价周期" in texts
    assert "约下周演示" in texts


def test_recommend_ticket_solutions(db_session: Session) -> None:
    from app.agent.tools.ticket import recommend_ticket_solutions

    user = _user(db_session, "scene_s4")
    space = KnowledgeSpace(code="policy", name="制度", icon="制", sort_order=1)
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
        ticket_no="TK-S4-NOW",
        title="办公室打印机无法连接网络",
        content="打印队列卡住",
        creator_id=user.id,
        status="processing",
    )
    old = Ticket(
        ticket_no="TK-S4-OLD",
        title="打印机连不上网络",
        content="打印队列卡住，重启后好了",
        creator_id=user.id,
        status="closed",
        result="重启交换机后恢复",
    )
    db_session.add_all([current, old])
    db_session.commit()
    with agent_runtime(db_session, user):
        data = recommend_ticket_solutions.invoke({"ticket_id": current.id})
    assert data["similar_tickets"][0]["ticket_no"] == "TK-S4-OLD"
    assert data["knowledge"]["found"] is True
    assert data["knowledge"]["citations"][0]["title"] == "打印机故障处理"


def test_precheck_approval_missing(db_session: Session) -> None:
    from app.agent.tools.approval import precheck_approval

    user = _user(db_session, "scene_s5")
    with agent_runtime(db_session, user):
        data = precheck_approval.invoke({"approval_id": "flow:99999"})
    assert data.get("status_code") == 404
