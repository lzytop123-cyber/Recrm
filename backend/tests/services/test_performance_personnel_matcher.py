"""人员匹配表驱动测试。"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.performance import (
    PerformanceAssessment,
    PerformanceCycle,
    PerformanceTemplate,
    PerformanceTemplateItem,
    PerformanceTemplateScope,
)
from app.models.user import User
from app.services import performance_personnel_matcher as matcher


def _setup(db: Session):
    dept = Department(name="市场部", code="MATCH_MKT")
    other = Department(name="讲师部", code="MATCH_LEC")
    db.add_all([dept, other])
    db.flush()
    mgr = User(
        username="match_mgr",
        password_hash=hash_password("x"),
        real_name="李岚",
        is_active=True,
        department_id=dept.id,
        job_title="市场主管",
    )
    db.add(mgr)
    db.flush()
    tpl = PerformanceTemplate(
        name="市场月度",
        code="MATCH-TPL-1",
        status="published",
        family_code="MARKET_MONTHLY",
        version=2,
        engine_version="kpi-v2",
        scoring_mode="points_sum",
        assessment_kind="monthly",
        published_at=datetime.now(timezone.utc),
        published_by=mgr.id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        eligibility_policy_json='{"min_days_in_period":15,"include_probation":false}',
    )
    cycle = PerformanceCycle(period_label="2026-10", status="assessing", cycle_type="monthly")
    db.add_all([tpl, cycle])
    db.flush()
    db.add(
        PerformanceTemplateItem(
            template_id=tpl.id,
            order_no=1,
            name="签约",
            weight=Decimal("100"),
            data_source="system",
            scoring_type="quantity",
            handling_mode="system_auto",
        )
    )
    db.add(PerformanceTemplateScope(template_id=tpl.id, department_id=dept.id, job_title="市场业务"))
    db.commit()
    return dept, other, mgr, tpl, cycle


def _person(
    db: Session,
    *,
    username: str,
    dept_id: int,
    job_title: str,
    manager_id: int | None,
    employment_status: str = "正式",
    hire_date: date | None = date(2025, 1, 1),
    attendance_days: int | None = 30,
    period_start: date = date(2026, 10, 1),
) -> User:
    u = User(
        username=username,
        password_hash=hash_password("x"),
        real_name=username,
        is_active=True,
        department_id=dept_id,
        job_title=job_title,
        manager_id=manager_id,
        employment_status=employment_status,
        hire_date=hire_date,
    )
    db.add(u)
    db.flush()
    if attendance_days is not None:
        matcher.seed_attendance_days(db, u.id, period_start, attendance_days)
    db.commit()
    return u


@pytest.mark.parametrize(
    "case,kwargs,expect_status,expect_code",
    [
        ("matched", {"employment_status": "正式", "attendance_days": 30}, "matched", "scope_and_policy_matched"),
        ("wrong_job", {"job_title": "品宣专员", "attendance_days": 30}, None, None),  # 不进候选池
        ("probation", {"employment_status": "试用", "attendance_days": 25}, "excluded", "probation"),
        ("ten_days", {"attendance_days": 10}, "excluded", "insufficient_days"),
        ("boundary_15", {"attendance_days": 15}, "matched", "scope_and_policy_matched"),
        ("long_leave", {"employment_status": "长期休假", "attendance_days": 30}, "excluded", "long_leave"),
        ("no_manager", {"manager_id": None, "attendance_days": 30}, "blocked", "missing_manager"),
    ],
)
def test_match_personnel_cases(db_session: Session, case, kwargs, expect_status, expect_code) -> None:
    dept, other, mgr, tpl, cycle = _setup(db_session)
    base = {
        "username": f"p_{case}",
        "dept_id": dept.id,
        "job_title": "市场业务",
        "manager_id": mgr.id,
    }
    base.update(kwargs)
    if case == "wrong_job":
        # 岗位不符：创建后不应出现在结果
        _person(db_session, **base)
        result = matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
        assert all(p["user_id"] for p in result["people"]) or result["people"] == []
        assert not any(p["name"] == f"p_{case}" for p in result["people"])
        return

    user = _person(db_session, **base)
    result = matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
    person = next(p for p in result["people"] if p["user_id"] == user.id)
    assert person["match_status"] == expect_status
    assert person["reason_code"] == expect_code
    assert person["reason"]


def test_duplicate_assessment_blocked(db_session: Session) -> None:
    dept, _, mgr, tpl, cycle = _setup(db_session)
    user = _person(db_session, username="dup_u", dept_id=dept.id, job_title="市场业务", manager_id=mgr.id)
    db_session.add(
        PerformanceAssessment(
            cycle_id=cycle.id,
            user_id=user.id,
            department_id=dept.id,
            template_id=tpl.id,
            status="employee_pending",
            assessment_kind="monthly",
            instance_key="monthly_primary",
            engine_version="v2",
            revision=1,
        )
    )
    db_session.commit()
    result = matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
    person = next(p for p in result["people"] if p["user_id"] == user.id)
    assert person["match_status"] == "blocked"
    assert person["reason_code"] == "duplicate_assessment"
    assert person["allowed_action"] == "none"


def test_out_of_department_not_in_pool(db_session: Session) -> None:
    dept, other, mgr, tpl, cycle = _setup(db_session)
    _person(
        db_session,
        username="other_dept",
        dept_id=other.id,
        job_title="市场业务",
        manager_id=mgr.id,
    )
    result = matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
    assert not any(p["name"] == "other_dept" for p in result["people"])


def test_template_all_blocked_flag(db_session: Session) -> None:
    dept, _, mgr, tpl, cycle = _setup(db_session)
    assert matcher.template_all_blocked(db_session, cycle_id=cycle.id, template_id=tpl.id) is False
    user = _person(db_session, username="occ_u", dept_id=dept.id, job_title="市场业务", manager_id=mgr.id)
    assert matcher.template_all_blocked(db_session, cycle_id=cycle.id, template_id=tpl.id) is False
    db_session.add(
        PerformanceAssessment(
            cycle_id=cycle.id,
            user_id=user.id,
            department_id=dept.id,
            template_id=tpl.id,
            status="employee_pending",
            assessment_kind="monthly",
            instance_key="monthly_primary",
            engine_version="v2",
            revision=1,
        )
    )
    db_session.commit()
    assert matcher.template_all_blocked(db_session, cycle_id=cycle.id, template_id=tpl.id) is True
    extra = _person(db_session, username="occ_free", dept_id=dept.id, job_title="市场业务", manager_id=mgr.id)
    assert extra.id
    assert matcher.template_all_blocked(db_session, cycle_id=cycle.id, template_id=tpl.id) is False


def test_unpublished_template_rejected(db_session: Session) -> None:
    dept, _, mgr, tpl, cycle = _setup(db_session)
    tpl.status = "approved"
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
    assert exc.value.status_code == 409
