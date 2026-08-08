"""资源承诺工时与任务计划工时打通。"""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.customer import Customer
from app.models.project import (
    RESOURCE_NEED_ACCEPTED,
    RESOURCE_NEED_PENDING,
    Project,
    ProjectResourceNeed,
    ProjectTask,
)
from app.models.role import Role
from app.models.user import User
from app.schemas.project import ProjectTaskCreate
from app.services import project as project_service
from app.services import project_resource as resource_service


def _setup(db: Session) -> tuple[User, Project]:
    role = Role(name="交付", code="hours_budget_role", data_scope="department")
    user = User(
        username="hours_budget_user",
        password_hash=hash_password("x"),
        real_name="预算测试",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.flush()
    customer = Customer(name="预算客户", owner_id=user.id, creator_id=user.id)
    db.add(customer)
    db.flush()
    project = Project(
        project_no="XM-HOURS-BUDGET",
        name="工时预算项目",
        customer_id=customer.id,
        project_type="ai_custom",
        status="executing",
        manager_id=user.id,
        creator_id=user.id,
    )
    db.add(project)
    db.flush()
    db.add(
        ProjectResourceNeed(
            project_id=project.id,
            role_name="交付部",
            department_name="交付部",
            suggested_user_id=user.id,
            planned_hours=Decimal("40"),
            status=RESOURCE_NEED_ACCEPTED,
            schedule_status="clear",
        )
    )
    db.commit()
    return user, project


def test_hours_budget_summary(db_session: Session):
    user, project = _setup(db_session)
    db_session.add(
        ProjectTask(
            task_no="RW-HB-1",
            project_id=project.id,
            title="已拆任务",
            assignee_id=user.id,
            planned_hours=Decimal("18"),
            actual_hours=Decimal("0"),
            status="doing",
            creator_id=user.id,
        )
    )
    db_session.commit()

    budget = resource_service.get_hours_budget(db_session, project.id)
    assert budget["resource_budget_hours"] == Decimal("40")
    assert budget["task_planned_hours"] == Decimal("18")
    assert budget["remaining_hours"] == Decimal("22")
    assert budget["over_budget"] is False


def test_create_task_over_budget_rejected(db_session: Session):
    user, project = _setup(db_session)
    db_session.add(
        ProjectTask(
            task_no="RW-HB-2",
            project_id=project.id,
            title="占位",
            assignee_id=user.id,
            planned_hours=Decimal("30"),
            actual_hours=Decimal("0"),
            status="doing",
            creator_id=user.id,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        project_service.create_task(
            db_session,
            user,
            ProjectTaskCreate(
                project_id=project.id,
                title="超预算任务",
                assignee_id=user.id,
                planned_hours=Decimal("15"),
            ),
        )
    assert exc.value.status_code == 400
    assert "超出资源承诺" in str(exc.value.detail)


def test_reject_resource_blocked_when_tasks_exceed(db_session: Session):
    user, project = _setup(db_session)
    need = (
        db_session.query(ProjectResourceNeed)
        .filter(ProjectResourceNeed.project_id == project.id)
        .first()
    )
    assert need is not None
    need.status = RESOURCE_NEED_PENDING
    db_session.add(
        ProjectTask(
            task_no="RW-HB-3",
            project_id=project.id,
            title="已拆",
            assignee_id=user.id,
            planned_hours=Decimal("20"),
            actual_hours=Decimal("0"),
            status="doing",
            creator_id=user.id,
        )
    )
    db_session.commit()

    from app.schemas.project_resource import ResourceConfirmRequest

    with pytest.raises(HTTPException) as exc:
        resource_service.confirm_resource(
            db_session,
            user,
            need.id,
            ResourceConfirmRequest(action="reject", note="人手不足无法承接"),
        )
    assert exc.value.status_code == 400
    assert "低于已拆任务" in str(exc.value.detail)
