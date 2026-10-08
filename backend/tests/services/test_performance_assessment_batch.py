"""批量发起：幂等、事务回滚、快照不变。"""
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.performance import (
    PerformanceAssessment,
    PerformanceAssessmentBatch,
    PerformanceCycle,
    PerformanceTemplate,
    PerformanceTemplateItem,
    PerformanceTemplateScope,
)
from app.models.user import User
from app.services import performance_assessment_batch as batch_svc
from app.services import performance_personnel_matcher as matcher


def _due_chain(*, hr: bool = False) -> dict:
    base = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)
    payload = {
        "employee_due_at": base.isoformat(),
        "manager_due_at": (base + timedelta(days=3)).isoformat(),
        "hr_review_required": hr,
        "hr_review_due_at": (base + timedelta(days=5)).isoformat() if hr else None,
        "confirm_due_at": (base + timedelta(days=8)).isoformat(),
    }
    return payload


def _fixture(db: Session):
    dept = Department(name="市场部", code="BATCH_MKT")
    db.add(dept)
    db.flush()
    mgr = User(
        username="batch_mgr",
        password_hash=hash_password("x"),
        real_name="主管",
        is_active=True,
        department_id=dept.id,
        job_title="市场主管",
    )
    db.add(mgr)
    db.flush()
    u1 = User(
        username="batch_u1",
        password_hash=hash_password("x"),
        real_name="张明",
        is_active=True,
        department_id=dept.id,
        job_title="市场业务",
        manager_id=mgr.id,
        employment_status="正式",
        hire_date=date(2025, 1, 1),
    )
    u2 = User(
        username="batch_u2",
        password_hash=hash_password("x"),
        real_name="王芳",
        is_active=True,
        department_id=dept.id,
        job_title="市场业务",
        manager_id=mgr.id,
        employment_status="正式",
        hire_date=date(2025, 1, 1),
    )
    db.add_all([u1, u2])
    db.flush()
    matcher.seed_attendance_days(db, u1.id, date(2026, 10, 1), 30)
    matcher.seed_attendance_days(db, u2.id, date(2026, 10, 1), 30)
    tpl = PerformanceTemplate(
        name="市场月度",
        code="BATCH-TPL-1",
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
    )
    cycle = PerformanceCycle(period_label="2026-10", status="assessing", cycle_type="monthly")
    db.add_all([tpl, cycle])
    db.flush()
    db.add(
        PerformanceTemplateItem(
            template_id=tpl.id,
            order_no=1,
            name="签约数",
            weight=Decimal("100"),
            data_source="system",
            metric_key="market.signed_clients",
            scoring_type="quantity",
            handling_mode="system_supplement",
            evidence_policy_json=json.dumps({"required_fields": ["customer_industry"]}),
        )
    )
    db.add(PerformanceTemplateScope(template_id=tpl.id, department_id=dept.id, job_title="市场业务"))
    db.commit()
    return dept, mgr, u1, u2, tpl, cycle


def test_idempotent_batch_returns_same(db_session: Session) -> None:
    _, mgr, u1, u2, tpl, cycle = _fixture(db_session)
    payload = {
        "cycle_id": cycle.id,
        "template_id": tpl.id,
        "people": [
            {"user_id": u1.id, "selected": True, "adjustment_reason": None},
            {"user_id": u2.id, "selected": True, "adjustment_reason": None},
        ],
        **_due_chain(),
    }
    first = batch_svc.create_assessment_batch(db_session, mgr, payload, idempotency_key="idem-1")
    second = batch_svc.create_assessment_batch(db_session, mgr, payload, idempotency_key="idem-1")
    assert first["id"] == second["id"]
    assert second["idempotent"] is True
    assert db_session.query(PerformanceAssessmentBatch).count() == 1
    assert db_session.query(PerformanceAssessment).filter_by(batch_id=first["id"]).count() == 2


def test_duplicate_key_different_idem_blocks(db_session: Session) -> None:
    _, mgr, u1, _, tpl, cycle = _fixture(db_session)
    payload = {
        "cycle_id": cycle.id,
        "template_id": tpl.id,
        "people": [{"user_id": u1.id, "selected": True, "adjustment_reason": None}],
        **_due_chain(),
    }
    batch_svc.create_assessment_batch(db_session, mgr, payload, idempotency_key="idem-a")
    with pytest.raises(HTTPException) as exc:
        batch_svc.create_assessment_batch(db_session, mgr, payload, idempotency_key="idem-b")
    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert detail["code"] == "KPI_PERSON_BLOCKED"
    assert detail["details"]["reason_code"] == "duplicate_assessment"
    assert "重复" in detail["message"]
    assert db_session.query(PerformanceAssessmentBatch).count() == 1


def test_one_person_failure_rolls_back(db_session: Session) -> None:
    _, mgr, u1, u2, tpl, cycle = _fixture(db_session)
    # u2 缺主管 → blocked
    u2.manager_id = None
    db_session.commit()
    payload = {
        "cycle_id": cycle.id,
        "template_id": tpl.id,
        "people": [
            {"user_id": u1.id, "selected": True, "adjustment_reason": None},
            {"user_id": u2.id, "selected": True, "adjustment_reason": "强行纳入"},
        ],
        **_due_chain(),
    }
    with pytest.raises(HTTPException) as exc:
        batch_svc.create_assessment_batch(db_session, mgr, payload, idempotency_key="idem-fail")
    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert detail["code"] == "KPI_PERSON_BLOCKED"
    assert detail["details"]["reason_code"] == "missing_manager"
    assert "主管" in detail["message"]
    assert db_session.query(PerformanceAssessmentBatch).count() == 0
    assert db_session.query(PerformanceAssessment).count() == 0


def test_person_snapshot_unchanged_after_transfer(db_session: Session) -> None:
    dept, mgr, u1, _, tpl, cycle = _fixture(db_session)
    payload = {
        "cycle_id": cycle.id,
        "template_id": tpl.id,
        "people": [{"user_id": u1.id, "selected": True, "adjustment_reason": None}],
        **_due_chain(),
    }
    out = batch_svc.create_assessment_batch(db_session, mgr, payload, idempotency_key="idem-snap")
    assessment = db_session.query(PerformanceAssessment).filter_by(id=out["assessment_ids"][0]).one()
    snap = json.loads(assessment.person_snapshot_json)
    assert snap["job_title"] == "市场业务"
    assert snap["manager_id"] == mgr.id

    new_dept = Department(name="讲师部", code="BATCH_LEC")
    db_session.add(new_dept)
    db_session.flush()
    u1.department_id = new_dept.id
    u1.job_title = "讲师"
    u1.manager_id = None
    db_session.commit()

    db_session.refresh(assessment)
    snap2 = json.loads(assessment.person_snapshot_json)
    assert snap2["job_title"] == "市场业务"
    assert snap2["manager_id"] == mgr.id
    assert snap2["department_name"] == "市场部"


def test_exclude_matched_requires_reason(db_session: Session) -> None:
    _, mgr, u1, _, tpl, cycle = _fixture(db_session)
    payload = {
        "cycle_id": cycle.id,
        "template_id": tpl.id,
        "people": [{"user_id": u1.id, "selected": False, "adjustment_reason": None}],
        **_due_chain(),
    }
    with pytest.raises(HTTPException) as exc:
        batch_svc.create_assessment_batch(db_session, mgr, payload, idempotency_key="idem-ex")
    assert exc.value.status_code == 422


def _second_dept_template(db: Session, mgr: User, cycle: PerformanceCycle):
    ops = Department(name="AI技术运维", code="BATCH_OPS")
    db.add(ops)
    db.flush()
    emp = User(
        username="batch_ops_u1",
        password_hash=hash_password("x"),
        real_name="陈浩",
        is_active=True,
        department_id=ops.id,
        job_title="运维专员",
        manager_id=mgr.id,
        employment_status="正式",
        hire_date=date(2025, 1, 1),
    )
    db.add(emp)
    db.flush()
    matcher.seed_attendance_days(db, emp.id, date(2026, 10, 1), 30)
    tpl = PerformanceTemplate(
        name="运维月度",
        code="BATCH-TPL-OPS",
        status="published",
        family_code="AI_OPS_MONTHLY",
        version=1,
        engine_version="kpi-v2",
        scoring_mode="points_sum",
        assessment_kind="monthly",
        published_at=datetime.now(timezone.utc),
        published_by=mgr.id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )
    db.add(tpl)
    db.flush()
    db.add(
        PerformanceTemplateItem(
            template_id=tpl.id,
            order_no=1,
            name="可用率",
            weight=Decimal("100"),
            data_source="system",
            metric_key="ops.availability",
            scoring_type="ratio",
            handling_mode="system_supplement",
        )
    )
    db.add(PerformanceTemplateScope(template_id=tpl.id, department_id=ops.id, job_title="运维专员"))
    db.commit()
    return ops, emp, tpl


def test_multi_batch_launch_and_progress_board(db_session: Session) -> None:
    _, mgr, u1, u2, tpl_mkt, cycle = _fixture(db_session)
    _, ops_emp, tpl_ops = _second_dept_template(db_session, mgr, cycle)

    multi = batch_svc.match_personnel_multi(
        db_session, cycle_id=cycle.id, template_ids=[tpl_mkt.id, tpl_ops.id]
    )
    assert multi["cycle_id"] == cycle.id
    assert len(multi["results"]) == 2

    payload = {
        "cycle_id": cycle.id,
        "batches": [
            {
                "template_id": tpl_mkt.id,
                "people": [
                    {"user_id": u1.id, "selected": True},
                    {"user_id": u2.id, "selected": True},
                ],
            },
            {
                "template_id": tpl_ops.id,
                "people": [{"user_id": ops_emp.id, "selected": True}],
            },
        ],
        **_due_chain(),
    }
    first = batch_svc.create_multi_assessment_batches(
        db_session, mgr, payload, idempotency_key="multi-1"
    )
    assert first["idempotent"] is False
    assert first["batch_count"] == 2
    assert first["assessment_count"] == 3
    assert first["hr_review_required"] is False
    assert first["batches"][0]["hr_review_required"] is False
    assert db_session.query(PerformanceAssessmentBatch).count() == 2

    second = batch_svc.create_multi_assessment_batches(
        db_session, mgr, payload, idempotency_key="multi-1"
    )
    assert second["idempotent"] is True
    assert second["batch_count"] == 2
    assert db_session.query(PerformanceAssessmentBatch).count() == 2

    board = batch_svc.list_cycle_batch_progress(db_session, cycle.id)
    market = next(b for b in board["batches"] if b["department_name"] == "市场部")
    assert market["manager_id"] == mgr.id
    assert market["manager_name"] == "主管"
    assert market["people"][0]["manager_id"] == mgr.id
    assert market["people"][0]["manager_name"] == "主管"
    assert board["totals"]["batch_count"] == 2
    assert board["totals"]["total"] == 3
    assert board["totals"]["pending_employee"] == 3
    assert board["totals"]["pending_manager"] == 0
    assert len(board["departments"]) == 2
    names = {d["department_name"] for d in board["departments"]}
    assert "市场部" in names
    assert "AI技术运维" in names

    detail = batch_svc.get_batch_progress(db_session, first["batches"][0]["id"])
    assert detail["total"] >= 1
    assert len(detail["people"]) == detail["total"]

    mine = batch_svc.list_cycle_batch_progress(db_session, cycle.id, u1)
    assert mine["totals"]["batch_count"] == 1
    assert mine["departments"][0]["department_name"] == "市场部"
    as_mgr = batch_svc.list_cycle_batch_progress(db_session, cycle.id, mgr)
    assert as_mgr["totals"]["batch_count"] == 2
    ops_batch_id = next(b["id"] for b in first["batches"] if b["id"] != mine["batches"][0]["id"])
    with pytest.raises(HTTPException) as denied:
        batch_svc.get_batch_progress(db_session, ops_batch_id, u1)
    assert denied.value.status_code == 403


def test_multi_batch_rolls_back_on_second_template_failure(db_session: Session) -> None:
    _, mgr, u1, _, tpl_mkt, cycle = _fixture(db_session)
    _, ops_emp, tpl_ops = _second_dept_template(db_session, mgr, cycle)
    ops_emp.manager_id = None
    db_session.commit()

    payload = {
        "cycle_id": cycle.id,
        "batches": [
            {"template_id": tpl_mkt.id, "people": [{"user_id": u1.id, "selected": True}]},
            {"template_id": tpl_ops.id, "people": [{"user_id": ops_emp.id, "selected": True}]},
        ],
        **_due_chain(),
    }
    with pytest.raises(HTTPException) as exc:
        batch_svc.create_multi_assessment_batches(
            db_session, mgr, payload, idempotency_key="multi-fail"
        )
    assert exc.value.status_code == 409
    assert db_session.query(PerformanceAssessmentBatch).count() == 0
    assert db_session.query(PerformanceAssessment).count() == 0


def test_current_month_cycle_id_prefers_latest(db_session: Session) -> None:
    today = date.today()
    older = PerformanceCycle(
        period_label=f"{today.year-1}-01",
        status="assessing",
        cycle_type="monthly",
    )
    first = PerformanceCycle(
        period_label=f"{today.year}-{today.month:02d}",
        status="assessing",
        cycle_type="monthly",
    )
    later = PerformanceCycle(
        period_label=f"{today.year}年{today.month}月考核周期",
        status="assessing",
        cycle_type="monthly",
    )
    db_session.add_all([older, first, later])
    db_session.commit()
    assert batch_svc.current_month_cycle_id(db_session) == later.id


def test_multi_batch_rejects_same_person_across_templates(db_session: Session) -> None:
    _, mgr, u1, _, tpl_mkt, cycle = _fixture(db_session)
    _, ops_emp, tpl_ops = _second_dept_template(db_session, mgr, cycle)
    payload = {
        "cycle_id": cycle.id,
        "batches": [
            {"template_id": tpl_mkt.id, "people": [{"user_id": u1.id, "selected": True}]},
            {"template_id": tpl_ops.id, "people": [{"user_id": u1.id, "selected": True}]},
        ],
        **_due_chain(),
    }
    with pytest.raises(HTTPException) as exc:
        batch_svc.create_multi_assessment_batches(
            db_session, mgr, payload, idempotency_key="multi-dup-user"
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "KPI_MULTI_PERSON_DUPLICATE"


def test_assessment_history_scopes_manager_and_employee(db_session: Session) -> None:
    _, mgr, u1, u2, tpl, cycle = _fixture(db_session)
    older = PerformanceCycle(period_label="2026-07", status="locked", cycle_type="monthly")
    outsider = User(
        username="batch_out",
        password_hash=hash_password("x"),
        real_name="外人",
        is_active=True,
        job_title="运维专员",
    )
    db_session.add_all([older, outsider])
    db_session.flush()
    payload = {
        "cycle_id": cycle.id,
        "template_id": tpl.id,
        "people": [
            {"user_id": u1.id, "selected": True},
            {"user_id": u2.id, "selected": True},
        ],
        **_due_chain(),
    }
    batch_svc.create_assessment_batch(db_session, mgr, payload, idempotency_key="hist-1")
    current = {
        row.user_id: row
        for row in db_session.query(PerformanceAssessment).filter_by(cycle_id=cycle.id).all()
    }
    current[u1.id].total_points = Decimal("91")
    current[u2.id].total_points = Decimal("80")
    db_session.add(PerformanceAssessment(
        cycle_id=older.id,
        user_id=u1.id,
        manager_id=mgr.id,
        status="completed",
        total_points=Decimal("80"),
        instance_key="hist-u1",
        person_snapshot_json=json.dumps({
            "name": "张明", "department_name": "市场部", "job_title": "市场业务", "manager_name": "主管",
        }, ensure_ascii=False),
    ))
    db_session.add(PerformanceAssessment(
        cycle_id=cycle.id,
        user_id=outsider.id,
        manager_id=outsider.id,
        status="completed",
        total_points=Decimal("99"),
        instance_key="hist-out",
        person_snapshot_json=json.dumps({
            "name": "外人", "department_name": "AI技术运维", "job_title": "运维专员", "manager_name": "外人",
        }, ensure_ascii=False),
    ))
    db_session.commit()

    as_mgr = batch_svc.list_assessment_history(db_session, mgr, cycle_id=cycle.id, sort="high")
    assert as_mgr["scope"] == "manager"
    assert [row["name"] for row in as_mgr["rows"]] == ["张明", "王芳"]
    assert as_mgr["rows"][0]["score_delta"] == "11.00"
    assert as_mgr["stats"]["count"] == 2

    as_u1 = batch_svc.list_assessment_history(db_session, u1, cycle_id=cycle.id)
    assert as_u1["scope"] == "self"
    assert [row["name"] for row in as_u1["rows"]] == ["张明"]
    assert as_u1["rows"][0]["previous_score"] == "80.00"
