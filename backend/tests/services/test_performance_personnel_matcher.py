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
        ("matched", {"employment_status": "正式"}, "matched", "scope_and_policy_matched"),
        ("wrong_job", {"job_title": "品宣专员"}, None, None),  # 不进候选池
        ("probation", {"employment_status": "试用"}, "excluded", "probation"),
        # 10 月共 31 天：10-22 入职 → 在岗 10 天；10-17 入职 → 在岗 15 天
        ("ten_days", {"hire_date": date(2026, 10, 22)}, "excluded", "insufficient_days"),
        ("boundary_15", {"hire_date": date(2026, 10, 17)}, "matched", "scope_and_policy_matched"),
        ("long_leave", {"employment_status": "长期休假"}, "excluded", "long_leave"),
        ("no_manager", {"manager_id": None}, "blocked", "missing_manager"),
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


def test_empty_job_title_matches_all_jobs_in_dept(db_session: Session) -> None:
    dept, _, mgr, tpl, cycle = _setup(db_session)
    db_session.query(PerformanceTemplateScope).filter(
        PerformanceTemplateScope.template_id == tpl.id
    ).delete()
    db_session.add(PerformanceTemplateScope(template_id=tpl.id, department_id=dept.id, job_title=""))
    db_session.commit()

    a = _person(db_session, username="all_a", dept_id=dept.id, job_title="培训总监", manager_id=mgr.id)
    b = _person(db_session, username="all_b", dept_id=dept.id, job_title="", manager_id=mgr.id)
    c = _person(db_session, username="all_c", dept_id=dept.id, job_title="讲师", manager_id=mgr.id)

    result = matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
    ids = {p["user_id"] for p in result["people"]}
    assert {a.id, b.id, c.id} <= ids
    assert all(p["match_status"] == "matched" for p in result["people"] if p["user_id"] in {a.id, b.id, c.id})


def test_scope_includes_child_department(db_session: Session) -> None:
    dept, _, mgr, tpl, cycle = _setup(db_session)
    child = Department(name="讲师交付组", code="MATCH_LEC_SUB", parent_id=dept.id)
    db_session.add(child)
    db_session.flush()
    db_session.query(PerformanceTemplateScope).filter(
        PerformanceTemplateScope.template_id == tpl.id
    ).delete()
    db_session.add(PerformanceTemplateScope(template_id=tpl.id, department_id=dept.id, job_title=""))
    db_session.commit()

    child_user = _person(
        db_session, username="child_u", dept_id=child.id, job_title="讲师", manager_id=mgr.id
    )
    result = matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
    assert any(p["user_id"] == child_user.id and p["match_status"] == "matched" for p in result["people"])

def test_other_template_assessment_warns_not_blocks(db_session: Session) -> None:
    dept, _, mgr, tpl, cycle = _setup(db_session)
    other_tpl = PerformanceTemplate(
        name="讲师月度积分",
        code="MATCH-TPL-LEC",
        status="published",
        family_code="LECTURER_MONTHLY",
        version=1,
        engine_version="kpi-v2",
        scoring_mode="points_sum",
        assessment_kind="monthly",
        published_at=datetime.now(timezone.utc),
        published_by=mgr.id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )
    db_session.add(other_tpl)
    db_session.flush()

    user = _person(db_session, username="warn_u", dept_id=dept.id, job_title="市场业务", manager_id=mgr.id)
    db_session.add(
        PerformanceAssessment(
            cycle_id=cycle.id,
            user_id=user.id,
            department_id=dept.id,
            template_id=other_tpl.id,
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
    assert person["match_status"] == "matched"
    assert person["allowed_action"] == "include_or_exclude"
    assert person["has_other_template_assessment"] is True
    assert person["warnings"]
    assert person["warnings"][0]["code"] == "other_template_assessment"
    assert "讲师月度积分" in person["warnings"][0]["message"]
    assert result["summary"]["warned"] >= 1



def _closed_cycle(db: Session) -> PerformanceCycle:
    cycle = PerformanceCycle(period_label="2026-09", status="assessing", cycle_type="monthly")
    db.add(cycle)
    db.commit()
    return cycle


def _seed_september(db: Session, user_id: int, *, last_day: int = 30, absent: dict[int, str] | None = None) -> None:
    absent = absent or {}
    for day in range(1, last_day + 1):
        matcher.seed_attendance_days(
            db, user_id, date(2026, 9, day), 1, status=absent.get(day, "正常")
        )
    db.commit()


def test_closed_period_deducts_absence_and_leave(db_session: Session) -> None:
    from app.models.hr import HrLeaveRequest

    dept, _, mgr, tpl, _ = _setup(db_session)
    cycle = _closed_cycle(db_session)
    user = _person(
        db_session, username="closed_u", dept_id=dept.id, job_title="市场业务",
        manager_id=mgr.id, attendance_days=None,
    )
    _seed_september(db_session, user.id, absent={3: "请假", 4: "旷工", 5: "休息日", 6: "缺卡"})
    db_session.add(
        HrLeaveRequest(
            employee_id=user.id, leave_type="annual", start_date=date(2026, 9, 3),
            end_date=date(2026, 9, 9), days=Decimal("7"), status="approved",
        )
    )
    db_session.commit()
    result = matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
    person = next(p for p in result["people"] if p["user_id"] == user.id)
    # 9/3-9/9 请假单 7 天 + 9/4 旷工（已在请假区间内，不重复扣）= 30 - 7
    assert person["days_in_period"] == 23


def test_closed_period_without_full_attendance_falls_back_to_hire_estimate(db_session: Session) -> None:
    dept, _, mgr, tpl, _ = _setup(db_session)
    cycle = _closed_cycle(db_session)
    user = _person(
        db_session, username="partial_u", dept_id=dept.id, job_title="市场业务",
        manager_id=mgr.id, attendance_days=None, hire_date=date(2026, 9, 11),
    )
    _seed_september(db_session, user.id, last_day=20, absent={12: "旷工"})
    result = matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
    person = next(p for p in result["people"] if p["user_id"] == user.id)
    assert person["days_in_period"] == 20


def test_open_period_ignores_attendance(db_session: Session) -> None:
    dept, _, mgr, tpl, cycle = _setup(db_session)
    user = _person(
        db_session, username="open_u", dept_id=dept.id, job_title="市场业务",
        manager_id=mgr.id, attendance_days=None,
    )
    matcher.seed_attendance_days(db_session, user.id, date(2026, 10, 1), 7, status="旷工")
    db_session.commit()
    result = matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
    person = next(p for p in result["people"] if p["user_id"] == user.id)
    assert person["days_in_period"] == 31


@pytest.mark.parametrize(
    "status,is_active,expected",
    [
        ("正式", True, "regular"),
        (None, True, "regular"),
        ("Regular", True, "regular"),
        ("试用", True, "probation"),
        ("试用期", True, "probation"),
        ("待入职", True, "pending"),
        ("长期休假", True, "long_leave"),
        ("离职", True, "resigned"),
        ("已离职", True, "resigned"),
        ("Resigned", True, "resigned"),
        ("正式", False, "resigned"),
    ],
)
def test_employment_state_normalization(status, is_active, expected) -> None:
    from app.services.employment_status import employment_state

    assert employment_state(status, is_active=is_active).value == expected


def test_resigned_but_active_account_excluded(db_session: Session) -> None:
    dept, _, mgr, tpl, cycle = _setup(db_session)
    user = _person(
        db_session, username="left_u", dept_id=dept.id, job_title="市场业务",
        manager_id=mgr.id, employment_status="已离职",
    )
    result = matcher.match_personnel(db_session, cycle_id=cycle.id, template_id=tpl.id)
    person = next(p for p in result["people"] if p["user_id"] == user.id)
    assert person["match_status"] == "excluded"
    assert person["allowed_action"] == "none"
