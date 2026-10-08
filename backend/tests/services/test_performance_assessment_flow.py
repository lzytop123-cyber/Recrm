"""简化考核状态机。"""
import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.permission import Permission
from app.models.performance import (
    ASSESS_EMPLOYEE_CONFIRM_PENDING,
    ASSESS_EMPLOYEE_PENDING,
    ASSESS_MANAGER_PENDING,
    PerformanceAssessment,
    PerformanceAssessmentItem,
    PerformanceCycle,
    PerformanceMaterialTask,
    PerformanceTemplate,
)
from app.models.role import Role
from app.models.user import User
from app.services import performance_assessment_flow as flow
from app.services import performance_materials as mats


def _user(db, username, *, dept_id=None, manager_id=None, perms=()):
    role = Role(name=f"{username}-r", code=f"{username}_r", data_scope="company")
    for code in perms:
        p = db.query(Permission).filter_by(code=code).first()
        if not p:
            p = Permission(name=code, code=code, module="kpi")
            db.add(p)
            db.flush()
        role.permissions.append(p)
    u = User(
        username=username,
        password_hash=hash_password("x"),
        real_name=username,
        is_active=True,
        department_id=dept_id,
        manager_id=manager_id,
    )
    u.roles.append(role)
    db.add(u)
    db.flush()
    return u


def _setup(db: Session, *, hr_review: bool = False):
    dept = Department(name="市场部", code="FLOW_MKT")
    db.add(dept)
    db.flush()
    mgr = _user(db, "flow_mgr", dept_id=dept.id)
    emp = _user(db, "flow_emp", dept_id=dept.id, manager_id=mgr.id)
    hr = _user(db, "flow_hr", dept_id=dept.id, perms=("kpi:assessment:manage",))
    tpl = PerformanceTemplate(name="流", code="FLOW-TPL", status="published", engine_version="kpi-v2")
    cycle = PerformanceCycle(period_label="2026-10-flow", status="assessing")
    db.add_all([tpl, cycle])
    db.flush()
    assessment = PerformanceAssessment(
        cycle_id=cycle.id,
        user_id=emp.id,
        department_id=dept.id,
        template_id=tpl.id,
        manager_id=mgr.id,
        status=ASSESS_EMPLOYEE_PENDING,
        instance_key="flow_1",
        engine_version="v2",
        revision=1,
        current_handler_type="employee",
        current_handler_id=emp.id,
        workflow_config_json=json.dumps({"hr_review_required": hr_review}),
    )
    db.add(assessment)
    db.flush()
    item = PerformanceAssessmentItem(
        assessment_id=assessment.id,
        order_no=1,
        name="签约",
        weight=Decimal("100"),
        data_source="manual",
    )
    db.add(item)
    db.commit()
    return emp, mgr, hr, assessment, item


def test_employee_cannot_manager_submit(db_session: Session) -> None:
    emp, mgr, _, assessment, item = _setup(db_session)
    assessment.status = ASSESS_MANAGER_PENDING
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        flow.manager_submit(
            db_session,
            assessment.id,
            emp,
            revision=1,
            scores=[{"item_id": item.id, "score": "80"}],
        )
    assert exc.value.status_code == 403


def test_manager_submit_skips_hr_when_disabled(db_session: Session) -> None:
    emp, mgr, _, assessment, item = _setup(db_session, hr_review=False)
    assessment.status = ASSESS_MANAGER_PENDING
    db_session.commit()
    out = flow.manager_submit(
        db_session,
        assessment.id,
        mgr,
        revision=1,
        scores=[{"item_id": item.id, "score": "88"}],
    )
    assert out["status"] == ASSESS_EMPLOYEE_CONFIRM_PENDING
    assert out["current_handler_type"] == "employee"
    assert out["hr_review_required"] is False


def test_manager_submit_goes_hr_when_flag_set(db_session: Session) -> None:
    _, mgr, _, assessment, item = _setup(db_session, hr_review=True)
    assessment.status = ASSESS_MANAGER_PENDING
    db_session.commit()
    out = flow.manager_submit(
        db_session,
        assessment.id,
        mgr,
        revision=1,
        scores=[{"item_id": item.id, "score": "90"}],
    )
    assert out["status"] == "hr_review"
    assert out["current_handler_type"] == "hr"
    assert out["hr_review_required"] is True


def test_appeal_blocks_confirm(db_session: Session) -> None:
    emp, _, hr, assessment, _ = _setup(db_session)
    assessment.status = ASSESS_EMPLOYEE_CONFIRM_PENDING
    db_session.commit()
    flow.create_appeal(db_session, assessment.id, emp, revision=1, reason="分数偏低", request_score=95)
    with pytest.raises(HTTPException) as exc:
        flow.result_confirm(db_session, assessment.id, emp, revision=2)
    assert exc.value.status_code == 409
    flow.resolve_appeal(db_session, assessment.id, hr, revision=2, approve=True, resolution="同意调整", final_score=95)
    db_session.refresh(assessment)
    out = flow.result_confirm(db_session, assessment.id, emp, revision=assessment.revision)
    assert out["status"] == "completed"


def test_resolve_appeal_updates_item_scores(db_session: Session) -> None:
    emp, _, hr, assessment, item = _setup(db_session)
    assessment.status = ASSESS_EMPLOYEE_CONFIRM_PENDING
    item.awarded_points = Decimal("11")
    item.final_score = Decimal("11")
    assessment.total_points = Decimal("11")
    db_session.commit()
    flow.create_appeal(db_session, assessment.id, emp, revision=1, reason="分数偏低", request_score=80)
    out = flow.resolve_appeal(
        db_session,
        assessment.id,
        hr,
        revision=2,
        approve=True,
        resolution="同意改分",
        scores=[{"item_id": item.id, "score": "80"}],
    )
    assert out["status"] == ASSESS_EMPLOYEE_CONFIRM_PENDING
    assert out["total_points"] == "80.00"
    assert out["appeal"]["status"] == "approved"
    db_session.refresh(item)
    assert item.final_score == Decimal("80")


def test_resolve_appeal_returns_to_manager(db_session: Session) -> None:
    emp, mgr, hr, assessment, _ = _setup(db_session)
    assessment.status = ASSESS_EMPLOYEE_CONFIRM_PENDING
    db_session.commit()
    flow.create_appeal(db_session, assessment.id, emp, revision=1, reason="请主管重评", request_score=80)
    out = flow.resolve_appeal(
        db_session,
        assessment.id,
        hr,
        revision=2,
        approve=True,
        resolution="退回主管重评",
        return_to_manager=True,
    )
    assert out["status"] == ASSESS_MANAGER_PENDING
    assert out["current_handler_type"] == "manager"
    assert out["current_handler_id"] == mgr.id


def test_revision_conflict(db_session: Session) -> None:
    emp, mgr, _, assessment, item = _setup(db_session)
    assessment.status = ASSESS_MANAGER_PENDING
    assessment.revision = 3
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        flow.manager_submit(db_session, assessment.id, mgr, revision=1, scores=[{"item_id": item.id, "score": "1"}])
    assert exc.value.status_code == 409
    assert "KPI_REVISION_CONFLICT" in str(exc.value.detail)


def test_completed_locks_writes(db_session: Session) -> None:
    emp, _, _, assessment, item = _setup(db_session)
    assessment.status = "completed"
    assessment.completed_at = datetime.now(timezone.utc)
    task = PerformanceMaterialTask(
        assessment_id=assessment.id,
        assessment_item_id=item.id,
        source_record_type="x",
        source_record_id="y",
        title="t",
        status="pending",
        revision=1,
    )
    db_session.add(task)
    db_session.commit()
    with pytest.raises(HTTPException):
        mats.save_draft(db_session, task.id, emp, "nope")
