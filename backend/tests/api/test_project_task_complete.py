"""完成任务须手填实际工时。"""
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.customer import Customer
from app.models.project import Project, ProjectTask
from app.models.role import Role
from app.models.user import User
from app.schemas.project import ProjectTaskUpdate
from app.services import project as project_service
from fastapi import HTTPException


def _user_and_project(db: Session) -> tuple[User, Project]:
    role = Role(name="交付", code="delivery_lead", data_scope="department")
    user = User(
        username="task_hours_user",
        password_hash=hash_password("x"),
        real_name="工时测试",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.flush()
    customer = Customer(name="工时客户", owner_id=user.id, creator_id=user.id)
    db.add(customer)
    db.flush()
    project = Project(
        project_no="XM-TASK-HOURS",
        name="工时测试项目",
        customer_id=customer.id,
        project_type="ai_custom",
        status="executing",
        manager_id=user.id,
        creator_id=user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(user)
    db.refresh(project)
    return user, project


def test_complete_task_requires_actual_hours(db_session: Session) -> None:
    user, project = _user_and_project(db_session)
    task = ProjectTask(
        task_no="RW-HOURS-001",
        project_id=project.id,
        title="开发任务",
        assignee_id=user.id,
        planned_hours=Decimal("8"),
        actual_hours=Decimal("0"),
        status="doing",
        due_date=date.today(),
        creator_id=user.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    try:
        project_service.update_task(
            db_session,
            user,
            task.id,
            ProjectTaskUpdate(status="done"),
        )
        assert False, "should require actual_hours"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "实际工时" in str(exc.detail)

    updated = project_service.update_task(
        db_session,
        user,
        task.id,
        ProjectTaskUpdate(status="done", actual_hours=Decimal("6.5")),
    )
    assert updated.status == "done"
    assert Decimal(str(updated.actual_hours)) == Decimal("6.5")
