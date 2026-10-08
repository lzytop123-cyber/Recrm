"""模板修订、分配、试算、确认归档、阶段与观察期。"""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.data.performance_templates import load_drafts
from app.models.performance import (
    PerformanceAssessment,
    PerformanceCycle,
    PerformanceFeedbackRecord,
    PerformanceTemplate,
)
from app.models.user import User
from app.services import performance_kpi


def _user(db: Session, username: str) -> User:
    row = User(username=username, password_hash=hash_password("secret123"), real_name=username, is_active=True)
    db.add(row)
    db.commit()
    return row


def _cycle(db: Session) -> PerformanceCycle:
    row = PerformanceCycle(period_label="2026-09-kpi-flow")
    db.add(row)
    db.commit()
    return row


def _assessment(db: Session, **kwargs) -> PerformanceAssessment:
    row = PerformanceAssessment(
        cycle_id=kwargs.pop("cycle_id"),
        user_id=kwargs.pop("user_id"),
        template_id=kwargs.get("template_id"),
        instance_key=kwargs.get("instance_key", "monthly_primary"),
        assessment_kind=kwargs.get("assessment_kind", "monthly"),
        engine_version="kpi-v2",
        total_points=kwargs.get("total_points"),
        performance_base_snapshot=kwargs.get("base"),
        payroll_eligible=kwargs.get("payroll_eligible", True),
        revision=1,
        confirmed_revision=kwargs.get("confirmed_revision", 1),
        status="pending_self",
    )
    db.add(row)
    db.commit()
    return row


def test_revise_keeps_draft_and_preview_marks_missing(db_session: Session) -> None:
    load_drafts(db_session)
    market = db_session.query(PerformanceTemplate).filter(PerformanceTemplate.family_code == "MARKET_MONTHLY").one()
    nxt = performance_kpi.revise_template(db_session, market.id)
    assert nxt["code"] == "MARKET_MONTHLY_V2"
    assert nxt["status"] == "draft"
    assert db_session.get(PerformanceTemplate, market.id).status == "draft"
    preview = performance_kpi.preview_template(db_session, nxt["id"], {"market.signed_clients": "3"})
    signed = next(line for line in preview["lines"] if line["metric_key"] == "market.signed_clients")
    assert signed["awarded_points"] == "15.00"
    assert preview["formal"] is False
    assert preview["total_points"] is None


def test_same_priority_assignment_conflicts(db_session: Session) -> None:
    load_drafts(db_session)
    market = db_session.query(PerformanceTemplate).filter(PerformanceTemplate.family_code == "MARKET_MONTHLY").one()
    performance_kpi.create_assignment(db_session, {"template_id": market.id, "assessment_kind": "monthly"})
    with pytest.raises(HTTPException) as exc:
        performance_kpi.create_assignment(db_session, {"template_id": market.id, "assessment_kind": "monthly"})
    assert exc.value.status_code == 409


def test_refresh_invalidates_confirmation_and_archive_needs_base(db_session: Session) -> None:
    owner = _user(db_session, "owner_kpi")
    other = _user(db_session, "other_kpi")
    cycle = _cycle(db_session)
    brand = PerformanceTemplate(
        name="品牌",
        code="BRAND_MONTHLY_V9",
        family_code="BRAND_MONTHLY",
        scoring_mode="points_sum",
        engine_version="kpi-v2",
        definition_json="{}",
    )
    db_session.add(brand)
    db_session.commit()
    row = _assessment(
        db_session,
        cycle_id=cycle.id,
        user_id=owner.id,
        template_id=brand.id,
        total_points=Decimal("65"),
        base=None,
        confirmed_revision=None,
    )
    with pytest.raises(HTTPException) as denied:
        performance_kpi.confirm_assessment(db_session, other, row.id, manage=False)
    assert denied.value.status_code == 403
    performance_kpi.confirm_assessment(db_session, owner, row.id, manage=False)
    refreshed = performance_kpi.refresh_assessment(db_session, row.id)
    assert refreshed["needs_confirm"] is True
    with pytest.raises(HTTPException) as stale:
        performance_kpi.archive_assessment(db_session, row.id)
    assert stale.value.status_code == 400
    row.confirmed_revision = row.revision
    db_session.commit()
    with pytest.raises(HTTPException) as missing_base:
        performance_kpi.archive_assessment(db_session, row.id)
    assert "基数" in missing_base.value.detail
    row.performance_base_snapshot = Decimal("2000")
    db_session.commit()
    archived = performance_kpi.archive_assessment(db_session, row.id)
    assert archived["bonus_amount"] == "1600.00"
    assert db_session.get(PerformanceAssessment, row.id).total_points == Decimal("65")


def test_market_score_is_not_clamped_and_onboarding_skips_pay(db_session: Session) -> None:
    owner = _user(db_session, "pay_kpi")
    cycle = _cycle(db_session)
    market = PerformanceTemplate(
        name="市场",
        code="MARKET_PAY_V1",
        family_code="MARKET_MONTHLY",
        scoring_mode="points_sum",
        engine_version="kpi-v2",
    )
    db_session.add(market)
    db_session.commit()
    high = _assessment(
        db_session,
        cycle_id=cycle.id,
        user_id=owner.id,
        template_id=market.id,
        total_points=Decimal("105"),
        base=Decimal("2000"),
        instance_key="monthly_primary",
    )
    done = performance_kpi.archive_assessment(db_session, high.id)
    assert done["bonus_amount"] == "2000.00"
    assert db_session.get(PerformanceAssessment, high.id).total_points == Decimal("105")
    stage = _assessment(
        db_session,
        cycle_id=cycle.id,
        user_id=owner.id,
        template_id=market.id,
        total_points=Decimal("80"),
        base=Decimal("5000"),
        payroll_eligible=False,
        instance_key="onboarding:9:D5",
        assessment_kind="onboarding",
    )
    skipped = performance_kpi.archive_assessment(db_session, stage.id)
    assert skipped["bonus_amount"] is None
    assert skipped["payroll_eligible"] is False


def test_feedback_stage_observation_and_lecturer(db_session: Session) -> None:
    subject = _user(db_session, "lecturer_kpi")
    reviewer = _user(db_session, "reviewer_kpi")
    cycle = _cycle(db_session)
    created = performance_kpi.create_feedback(db_session, {
        "form_type": "complaint",
        "subject_user_id": subject.id,
        "reviewer_user_id": reviewer.id,
        "anonymous": True,
        "score": "2",
    })
    hidden = performance_kpi.list_feedback(db_session, see_identity=False)[0]
    assert hidden["reviewer_user_id"] is None
    assert created["reviewer_user_id"] == reviewer.id
    for _ in range(3):
        row = PerformanceFeedbackRecord(
            form_type="complaint",
            subject_user_id=subject.id,
            anonymous=False,
            status="confirmed",
        )
        db_session.add(row)
    db_session.commit()
    assert performance_kpi.lecturer_status(db_session, subject.id)["incompetent"] is False
    extra = PerformanceFeedbackRecord(
        form_type="complaint", subject_user_id=subject.id, anonymous=False, status="confirmed"
    )
    db_session.add(extra)
    db_session.commit()
    assert performance_kpi.lecturer_status(db_session, subject.id)["incompetent"] is True
    opened = performance_kpi.open_stage_case(db_session, {
        "user_id": subject.id,
        "hire_event_id": 9,
        "stage": "D5",
        "role_kind": "sales",
        "cycle_id": cycle.id,
    })
    again = performance_kpi.open_stage_case(db_session, {
        "user_id": subject.id,
        "hire_event_id": 9,
        "stage": "D5",
        "role_kind": "sales",
        "cycle_id": cycle.id,
    })
    assert opened["instance_key"] == "onboarding:9:D5"
    assert again["idempotent"] is True
    released = performance_kpi.open_observation(db_session, {"user_id": subject.id, "end_score": "80", "retriggered": False})
    held = performance_kpi.open_observation(db_session, {"user_id": subject.id, "end_score": "80", "retriggered": True})
    assert released["status"] == "released"
    assert held["status"] == "hr_todo"
    assert "工资" in (held["hr_todo"] or "")
