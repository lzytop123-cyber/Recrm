"""工单挂项目完整链路：创建挂接 → 按项目可查 → 任务回写 → 结项后不可再挂。"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.customer import Customer
from app.models.department import Department
from app.models.project import Project, ProjectTask
from app.models.role import Role
from app.models.user import User


def _admin_headers(
    client: TestClient,
    db: Session,
    *,
    username: str = "ticket_link_admin",
) -> tuple[dict[str, str], User, Department]:
    role = Role(name=f"管理员-{username}", code="admin", data_scope="company")
    dept = Department(name=f"交付部-{username}", code=f"DELIVERY_{username.upper()}")
    db.add_all([role, dept])
    db.flush()
    user = User(
        username=username,
        password_hash=hash_password("secret123"),
        real_name="工单挂接管理员",
        is_active=True,
        department_id=dept.id,
    )
    user.roles.append(role)
    db.add(user)
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, user, dept


def _executing_project(db: Session, owner: User, *, project_no: str = "PJ-TICKET-LINK-001") -> Project:
    customer = Customer(name=f"挂接客户-{project_no}", owner_id=owner.id, creator_id=owner.id)
    db.add(customer)
    db.flush()
    project = Project(
        project_no=project_no,
        name="挂接测试项目",
        customer_id=customer.id,
        project_type="ai_custom",
        status="executing",
        manager_id=owner.id,
        creator_id=owner.id,
        progress=40,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def test_ticket_project_link_full_flow(client: TestClient, db_session: Session) -> None:
    headers, owner, dept = _admin_headers(client, db_session)
    project = _executing_project(db_session, owner)

    # 1) 建任务
    task_resp = client.post(
        "/api/v1/projects/tasks",
        headers=headers,
        json={
            "project_id": project.id,
            "title": "联调协助任务",
            "assignee_id": owner.id,
            "planned_hours": 8,
            "due_date": date.today().isoformat(),
        },
    )
    assert task_resp.status_code == 200, task_resp.text
    task = task_resp.json()
    assert task["ticket_id"] is None

    # 2) 发起工单并挂项目+任务
    ticket_resp = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "title": "协助联调工单",
            "ticket_type": "collaboration",
            "priority": "normal",
            "content": "需要跨部门协助完成本项目联调",
            "department_id": dept.id,
            "assignee_ids": [owner.id],
            "project_id": project.id,
            "task_id": task["id"],
        },
    )
    assert ticket_resp.status_code == 200, ticket_resp.text
    ticket = ticket_resp.json()
    assert ticket["project_id"] == project.id
    assert ticket["task_id"] == task["id"]
    assert ticket["project_name"] == project.name
    assert ticket["task_no"] == task["task_no"]

    # 3) 按项目筛选应能查到
    listed = client.get(
        "/api/v1/tickets",
        headers=headers,
        params={"project_id": project.id, "page": 1, "page_size": 50},
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert any(x["id"] == ticket["id"] for x in items)

    # 4) 任务侧应回写 ticket_id / ticket_no
    tasks = client.get(
        "/api/v1/projects/tasks",
        headers=headers,
        params={"project_id": project.id, "page": 1, "page_size": 50},
    )
    assert tasks.status_code == 200, tasks.text
    linked_task = next(x for x in tasks.json()["items"] if x["id"] == task["id"])
    assert linked_task["ticket_id"] == ticket["id"]
    assert linked_task["ticket_no"] == ticket["ticket_no"]

    # 5) 任务统计含关联工单
    stats = client.get("/api/v1/projects/tasks/stats", headers=headers)
    assert stats.status_code == 200, stats.text
    assert stats.json()["linked_tickets"] >= 1

    # 6) 完成/确认工单后，任务仍保持未完成（两套状态独立）
    accept = client.post(f"/api/v1/tickets/{ticket['id']}/accept", headers=headers)
    assert accept.status_code == 200, accept.text
    complete = client.post(
        f"/api/v1/tickets/{ticket['id']}/complete",
        headers=headers,
        json={"result": "联调已协助完成"},
    )
    assert complete.status_code == 200, complete.text
    confirm = client.post(
        f"/api/v1/tickets/{ticket['id']}/confirm",
        headers=headers,
        json={"satisfaction": 5, "comment": "ok", "close": True},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "closed"

    tasks_after = client.get(
        "/api/v1/projects/tasks",
        headers=headers,
        params={"project_id": project.id, "page": 1, "page_size": 50},
    )
    still = next(x for x in tasks_after.json()["items"] if x["id"] == task["id"])
    assert still["status"] != "done"
    assert still["ticket_id"] == ticket["id"]

    # 7) 项目结项后不可再挂工单
    project.status = "completed"
    db_session.commit()
    blocked = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "title": "结项后再挂应失败",
            "content": "不应成功",
            "department_id": dept.id,
            "project_id": project.id,
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "结项" in blocked.json()["detail"] or "终止" in blocked.json()["detail"]


def test_cannot_link_done_task(client: TestClient, db_session: Session) -> None:
    headers, owner, dept = _admin_headers(client, db_session, username="ticket_link_admin2")
    project = _executing_project(db_session, owner, project_no="PJ-TICKET-LINK-002")

    task = ProjectTask(
        task_no="RW-DONE-001",
        project_id=project.id,
        title="已完成任务",
        assignee_id=owner.id,
        planned_hours=Decimal("4"),
        actual_hours=Decimal("4"),
        status="done",
        due_date=date.today(),
        creator_id=owner.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    resp = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "title": "挂已完成任务应失败",
            "content": "不应成功",
            "department_id": dept.id,
            "project_id": project.id,
            "task_id": task.id,
        },
    )
    assert resp.status_code == 400, resp.text
    assert "已完成" in resp.json()["detail"]
