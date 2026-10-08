"""模板生命周期：draft/returned → pending_review → approved → published → disabled。"""
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
from app.services import performance_template as tpl


def _hr(db: Session) -> User:
    u = User(username="life_hr", password_hash=hash_password("x"), real_name="HR", is_active=True)
    db.add(u)
    db.flush()
    return u


def _v2_template(db: Session, user: User, *, code: str = "LIFE-V2-1") -> PerformanceTemplate:
    dept = Department(name="市场部", code=f"LIFE_{code}")
    db.add(dept)
    db.flush()
    row = PerformanceTemplate(
        name="市场月度可发布",
        code=code,
        status="draft",
        engine_version="kpi-v2",
        scoring_mode="points_sum",
        assessment_kind="monthly",
        nominal_total=Decimal("100"),
        definition_json='{"items":[{"metric_key":"market.signed_clients","max_points":"100"}],"open_issues":[]}',
        blocking_issues_json="[]",
        created_by=user.id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )
    db.add(row)
    db.flush()
    db.add(
        PerformanceTemplateItem(
            template_id=row.id,
            order_no=1,
            name="签约数",
            weight=Decimal("100"),
            data_source="system",
            metric_key="market.signed_clients",
            max_points=Decimal("100"),
            scoring_type="quantity",
            handling_mode="system_supplement",
            unit="个",
        )
    )
    db.add(
        PerformanceTemplateScope(template_id=row.id, department_id=dept.id, job_title="市场业务")
    )
    db.commit()
    return row


def test_reject_sets_returned_for_v2(db_session: Session) -> None:
    user = _hr(db_session)
    row = _v2_template(db_session, user)
    row.status = "pending_review"
    db_session.commit()
    tpl.apply_review_result(db_session, row.id, approved=False)
    db_session.refresh(row)
    assert row.status == "returned"


def test_publish_requires_approved_and_valid(db_session: Session) -> None:
    user = _hr(db_session)
    row = _v2_template(db_session, user)
    with pytest.raises(HTTPException) as exc:
        tpl.publish_template(db_session, row.id, user)
    assert exc.value.status_code == 409

    row.status = "approved"
    db_session.commit()
    published = tpl.publish_template(db_session, row.id, user)
    assert published.status == "published"
    assert published.published_by == user.id
    assert published.published_at is not None


def test_publish_blocks_when_blocking_issues(db_session: Session) -> None:
    user = _hr(db_session)
    row = _v2_template(db_session, user, code="LIFE-BLOCK")
    row.status = "approved"
    row.blocking_issues_json = '[{"code":"C09","blocking":true}]'
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        tpl.publish_template(db_session, row.id, user)
    assert exc.value.status_code == 409


def test_disable_only_affects_new_launches(db_session: Session) -> None:
    user = _hr(db_session)
    row = _v2_template(db_session, user, code="LIFE-DIS")
    row.status = "published"
    row.published_at = datetime.now(timezone.utc)
    row.published_by = user.id
    db_session.commit()
    cycle = PerformanceCycle(period_label="2026-10-life", status="assessing")
    db_session.add(cycle)
    db_session.flush()
    assessment = PerformanceAssessment(
        cycle_id=cycle.id,
        user_id=user.id,
        template_id=row.id,
        status="employee_pending",
        instance_key="life_primary",
        engine_version="v2",
        template_snapshot_json='{"code":"LIFE-DIS","version":1}',
        revision=1,
    )
    db_session.add(assessment)
    db_session.commit()

    disabled = tpl.disable_template(db_session, row.id, user)
    assert disabled.status == "disabled"
    with pytest.raises(HTTPException) as exc:
        tpl.require_published_for_launch(db_session, row.id)
    assert exc.value.status_code == 409
    assert "KPI_TEMPLATE_NOT_PUBLISHED" in str(exc.value.detail)

    # 历史考核仍可读快照
    loaded = db_session.query(PerformanceAssessment).filter_by(id=assessment.id).one()
    assert loaded.template_snapshot_json is not None
    assert "LIFE-DIS" in loaded.template_snapshot_json


def test_approved_not_published_cannot_launch(db_session: Session) -> None:
    user = _hr(db_session)
    row = _v2_template(db_session, user, code="LIFE-APPR")
    row.status = "approved"
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        tpl.require_published_for_launch(db_session, row.id)
    assert exc.value.status_code == 409


def test_template_effective_for_cycle_period() -> None:
    """九月周期不应接受十月才生效的模板。"""
    from datetime import date

    row = PerformanceTemplate(
        name="十月模板",
        code="EFF-OCT",
        status="published",
        effective_from=date(2026, 10, 1),
    )
    sep_start, sep_end = date(2026, 9, 1), date(2026, 9, 30)
    oct_start, oct_end = date(2026, 10, 1), date(2026, 10, 31)
    assert tpl.is_template_effective_for_period(row, sep_start, sep_end) is False
    assert tpl.is_template_effective_for_period(row, oct_start, oct_end) is True

    row.effective_from = date(2026, 9, 15)
    assert tpl.is_template_effective_for_period(row, sep_start, sep_end) is True

    row.effective_from = None
    row.effective_to = date(2026, 8, 31)
    assert tpl.is_template_effective_for_period(row, sep_start, sep_end) is False


def test_require_published_checks_cycle_window(db_session: Session) -> None:
    user = _hr(db_session)
    row = _v2_template(db_session, user, code="LIFE-OCT")
    row.status = "published"
    row.effective_from = date(2026, 10, 1)
    cycle = PerformanceCycle(period_label="2026年9月考核周期", cycle_type="monthly", status="assessing")
    db_session.add(cycle)
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        tpl.require_published_for_launch(db_session, row.id, cycle=cycle)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "KPI_TEMPLATE_OUT_OF_EFFECTIVE_DATE"


def test_legacy_reject_stays_draft(db_session: Session) -> None:
    user = _hr(db_session)
    row = PerformanceTemplate(
        name="旧模板",
        code="LIFE-LEGACY",
        status="pending_review",
        engine_version="legacy",
        scoring_mode="legacy_weighted",
        created_by=user.id,
    )
    db_session.add(row)
    db_session.commit()
    tpl.apply_review_result(db_session, row.id, approved=False)
    db_session.refresh(row)
    assert row.status == "draft"
