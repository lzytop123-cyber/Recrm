"""模板修订、分配、试算、确认归档、阶段与观察期。"""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.data.performance_templates import load_drafts
from app.models.performance import (
    PerformanceAssessment,
    PerformanceAssessmentItem,
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
    # 入职考核开案要求员工有直属主管（否则会卡在待主管评分）
    subject.manager_id = reviewer.id
    db_session.commit()
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
    # 入职考核开案需要对应的入职模板已发布（按 阶段 + 岗类 关联）
    load_drafts(db_session)
    onboard = (
        db_session.query(PerformanceTemplate)
        .filter(PerformanceTemplate.family_code == "ONBOARD_SALES_D5")
        .one()
    )
    onboard.status = "published"
    db_session.commit()
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
    assert opened["instance_key"] == f"onboarding_{subject.id}_D5_{cycle.id}"
    assert opened["template_id"] == onboard.id
    assert opened["item_count"] > 0
    assert again["idempotent"] is True
    assert again["assessment_id"] == opened["assessment_id"]
    released = performance_kpi.open_observation(db_session, {"user_id": subject.id, "end_score": "80", "retriggered": False})
    held = performance_kpi.open_observation(db_session, {"user_id": subject.id, "end_score": "80", "retriggered": True})
    assert released["status"] == "released"
    assert held["status"] == "hr_todo"
    assert "工资" in (held["hr_todo"] or "")

def test_open_stage_case_requires_manager(db_session: Session) -> None:
    """入职考核开案：员工没有直属主管时应被拒绝（否则会卡在待主管评分）。"""
    subject = _user(db_session, "onboard_no_manager")
    assert subject.manager_id is None
    load_drafts(db_session)
    onboard = (
        db_session.query(PerformanceTemplate)
        .filter(PerformanceTemplate.family_code == "ONBOARD_SALES_D5")
        .one()
    )
    onboard.status = "published"
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        performance_kpi.open_stage_case(
            db_session,
            {"user_id": subject.id, "stage": "D5", "role_kind": "SALES"},
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "KPI_ONBOARDING_MANAGER_REQUIRED"


def test_open_stage_case_copies_training_evaluator(db_session: Session) -> None:
    """开案时把模板指标的评分人带进考核单。

    漏带的后果：入职考核的「培训部评分」节点会被整体跳过（主管一人评完直接进 HR 复核）。
    """
    load_drafts(db_session)
    mgr = _user(db_session, "onboard_eval_mgr")
    subject = _user(db_session, "onboard_eval_subject")
    subject.manager_id = mgr.id
    tpl = (
        db_session.query(PerformanceTemplate)
        .filter(PerformanceTemplate.family_code == "ONBOARD_SALES_M1")
        .one()
    )
    tpl.status = "published"
    db_session.commit()

    opened = performance_kpi.open_stage_case(
        db_session, {"user_id": subject.id, "stage": "M1", "role_kind": "SALES"}
    )
    items = (
        db_session.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == opened["assessment_id"])
        .all()
    )
    training = sorted(i.name for i in items if (i.evaluator or "") == "training")
    assert training == sorted(["学习任务完成度", "产品知识掌握", "月度述职汇报"])
    # M1 业务岗：培训部 60 分 / 主管 40 分
    tr_points = sum(Decimal(str(i.max_points)) for i in items if i.evaluator == "training")
    mg_points = sum(Decimal(str(i.max_points)) for i in items if i.evaluator != "training")
    assert tr_points == Decimal("60")
    assert mg_points == Decimal("40")


def test_onboarding_review_permission_is_type_aware(db_session: Session) -> None:
    """入职考核复核权限：培训部负责人可复核；同人自审时交给 HR；月度考核不受影响。"""
    from types import SimpleNamespace

    from app.models.permission import Permission
    from app.models.role import Role
    from app.services import performance_assessment_flow as flow

    training_lead = _user(db_session, "training_lead_user")
    hr_user = _user(db_session, "hr_review_user")
    onboard_perm = db_session.query(Permission).filter(Permission.code == "kpi:onboarding:manage").first()
    if onboard_perm is None:
        onboard_perm = Permission(name="入职考核管理", code="kpi:onboarding:manage", module="kpi")
        db_session.add(onboard_perm)
        db_session.commit()
    role = Role(name="培训部负责人", code="training_lead", data_scope="company", module_scopes={})
    db_session.add(role)
    hr_role = Role(name="人力资源", code="hr", data_scope="company", module_scopes={})
    db_session.add(hr_role)
    db_session.commit()
    role.permissions = [onboard_perm]
    training_lead.roles = [role]
    hr_user.roles = [hr_role]
    db_session.commit()

    def asmt(kind: str, manager_id: int | None):
        return SimpleNamespace(assessment_kind=kind, manager_id=manager_id)

    # 培训部负责人可复核「别人带的新员工」的入职考核
    assert flow._can_review(asmt("onboarding", 999), training_lead) is True
    # 但不能复核「自己带的新员工」（防自审 → HR 兜底）
    assert flow._can_review(asmt("onboarding", training_lead.id), training_lead) is False
    # 月度考核不受影响：培训部负责人没有复核权
    assert flow._can_review(asmt("monthly", 999), training_lead) is False
    # HR 两种都能复核（含自审场景兜底）
    assert flow._can_review(asmt("onboarding", hr_user.id), hr_user) is True
    assert flow._can_review(asmt("monthly", hr_user.id), hr_user) is True

    # 禁止自审：培训部评分人评过之后不得再自己复核（交 HR）
    def asmt_scored(kind: str, manager_id: int | None, scorer_id: int | None):
        return SimpleNamespace(
            assessment_kind=kind, manager_id=manager_id, training_scorer_id=scorer_id
        )

    assert flow._can_review(asmt_scored("onboarding", 999, training_lead.id), training_lead) is False
    # 别人评的培训部维度，培训部负责人仍可复核
    assert flow._can_review(asmt_scored("onboarding", 999, 888), training_lead) is True
    # HR 兜底不受影响
    assert flow._can_review(asmt_scored("onboarding", 999, training_lead.id), hr_user) is True
