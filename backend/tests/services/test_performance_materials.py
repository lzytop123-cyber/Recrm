"""材料任务生成与逐项退回。"""
import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.performance import (
    ASSESS_EMPLOYEE_PENDING,
    ASSESS_MANAGER_PENDING,
    PerformanceAssessment,
    PerformanceAssessmentItem,
    PerformanceCycle,
    PerformanceMaterialTask,
    PerformanceMetricFact,
    PerformanceTemplate,
    PerformanceTemplateItem,
)
from app.models.user import User
from app.services import performance_materials as mats


def _setup(db: Session, *, with_fact_missing: bool = True, with_complete_fact: bool = False):
    dept = Department(name="市场部", code="MAT_MKT")
    db.add(dept)
    db.flush()
    mgr = User(
        username="mat_mgr",
        password_hash=hash_password("x"),
        real_name="主管",
        is_active=True,
        department_id=dept.id,
    )
    emp = User(
        username="mat_emp",
        password_hash=hash_password("x"),
        real_name="员工",
        is_active=True,
        department_id=dept.id,
        manager_id=None,
    )
    db.add_all([mgr, emp])
    db.flush()
    emp.manager_id = mgr.id
    tpl = PerformanceTemplate(
        name="材料模板",
        code="MAT-TPL",
        status="published",
        engine_version="kpi-v2",
        scoring_mode="points_sum",
    )
    cycle = PerformanceCycle(period_label="2026-10-mat", status="assessing")
    db.add_all([tpl, cycle])
    db.flush()
    titem = PerformanceTemplateItem(
        template_id=tpl.id,
        order_no=1,
        name="客户拓展",
        weight=Decimal("10"),
        data_source="system",
        metric_key="market.new_customers",
        scoring_type="quantity",
        handling_mode="system_supplement",
        evidence_policy_json=json.dumps({"required_fields": ["customer_industry"]}),
    )
    db.add(titem)
    db.flush()
    assessment = PerformanceAssessment(
        cycle_id=cycle.id,
        user_id=emp.id,
        department_id=dept.id,
        template_id=tpl.id,
        manager_id=mgr.id,
        status=ASSESS_EMPLOYEE_PENDING,
        instance_key="mat_1",
        engine_version="v2",
        revision=1,
        current_handler_type="employee",
        current_handler_id=emp.id,
    )
    db.add(assessment)
    db.flush()
    aitem = PerformanceAssessmentItem(
        assessment_id=assessment.id,
        template_item_id=titem.id,
        order_no=1,
        name="客户拓展",
        weight=Decimal("10"),
        data_source="system",
        metric_key="market.new_customers",
    )
    db.add(aitem)
    db.flush()
    if with_complete_fact:
        db.add(
            PerformanceMetricFact(
                metric_key="market.new_customers",
                owner_id=emp.id,
                value=Decimal("3"),
                unit="个",
                source_record_id="C-OK",
                status="confirmed",
                revision=1,
            )
        )
    if with_fact_missing:
        db.add(
            PerformanceMetricFact(
                metric_key="market.new_customers",
                owner_id=emp.id,
                value=Decimal("1"),
                unit="个",
                source_record_id="C-100",
                status="pending",
                revision=1,
            )
        )
    db.commit()
    return emp, mgr, assessment, aitem


def test_no_task_when_system_data_complete(db_session: Session) -> None:
    emp, _, assessment, _ = _setup(db_session, with_fact_missing=False, with_complete_fact=True)
    # 完整事实也没有 customer_industry —— 按规则仍会缺字段。改 evidence 为空模拟完整。
    titem = db_session.query(PerformanceTemplateItem).first()
    titem.evidence_policy_json = json.dumps({"required_fields": []})
    db_session.commit()
    created = mats.generate_material_tasks(db_session, assessment.id)
    db_session.commit()
    assert created == []
    assert db_session.query(PerformanceMaterialTask).count() == 0


def test_system_supplement_no_facts_defaults_gap_task(db_session: Session) -> None:
    """未配 evidence_policy、也无业务事实时，system_supplement 仍应生成补充任务。"""
    _, _, assessment, _ = _setup(db_session, with_fact_missing=False, with_complete_fact=False)
    titem = db_session.query(PerformanceTemplateItem).first()
    titem.evidence_policy_json = None
    db_session.commit()
    created = mats.generate_material_tasks(db_session, assessment.id)
    db_session.commit()
    assert len(created) == 1
    assert created[0].title.startswith("补充数据：")
    assert json.loads(created[0].missing_fields_json) == ["value"]


def test_generate_missing_industry_field_only(db_session: Session) -> None:
    _, _, assessment, _ = _setup(db_session, with_fact_missing=True, with_complete_fact=False)
    created = mats.generate_material_tasks(db_session, assessment.id)
    db_session.commit()
    assert len(created) == 1
    assert "customer_industry" in (created[0].missing_fields_json or "")
    assert created[0].source_record_id == "C-100"


def test_return_one_keeps_others(db_session: Session) -> None:
    emp, mgr, assessment, aitem = _setup(db_session, with_fact_missing=False, with_complete_fact=False)
    titem = db_session.query(PerformanceTemplateItem).first()
    titem.handling_mode = "employee_submit"
    titem.evidence_policy_json = json.dumps({"required_fields": ["content"]})
    db_session.commit()
    mats.generate_material_tasks(db_session, assessment.id)
    db_session.commit()
    # 再手工加第二条
    extra = PerformanceMaterialTask(
        assessment_id=assessment.id,
        assessment_item_id=aitem.id,
        source_record_type="employee_submit",
        source_record_id="extra",
        title="第二条",
        status="submitted",
        employee_content="ok",
        revision=1,
    )
    db_session.add(extra)
    task = db_session.query(PerformanceMaterialTask).filter_by(source_record_id=f"item_{aitem.id}").one()
    mats.save_draft(db_session, task.id, emp, "草稿内容")
    # 整份提交标记
    task = db_session.query(PerformanceMaterialTask).get(task.id)
    task.status = "submitted"
    assessment.status = ASSESS_MANAGER_PENDING
    db_session.commit()

    mats.return_task(db_session, task.id, mgr, "行业写错")
    other = db_session.query(PerformanceMaterialTask).filter_by(source_record_id="extra").one()
    assert other.status == "submitted"
    assert other.employee_content == "ok"
    returned = db_session.query(PerformanceMaterialTask).get(task.id)
    assert returned.status == "returned"
    assert returned.return_reason == "行业写错"


def test_incomplete_blocks_employee_submit(db_session: Session) -> None:
    _, _, assessment, _ = _setup(db_session)
    mats.generate_material_tasks(db_session, assessment.id)
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        mats.assert_materials_ready_for_submit(db_session, assessment.id)
    assert exc.value.status_code == 409


def test_sync_material_drafts_from_actuals_unblocks_submit(db_session: Session) -> None:
    _, _, assessment, aitem = _setup(db_session, with_fact_missing=False, with_complete_fact=False)
    titem = db_session.query(PerformanceTemplateItem).first()
    titem.handling_mode = "employee_submit"
    titem.evidence_policy_json = json.dumps({"required_fields": ["content"]})
    db_session.commit()
    mats.generate_material_tasks(db_session, assessment.id)
    db_session.commit()
    task = db_session.query(PerformanceMaterialTask).one()
    assert task.status == "pending"
    aitem.actual_value = "2"
    db_session.flush()
    assert mats.sync_material_drafts_from_actuals(db_session, assessment.id) == 1
    assert task.status == "draft"
    assert task.employee_content == "2"
    mats.assert_materials_ready_for_submit(db_session, assessment.id)


def test_apply_system_scores_from_material(db_session: Session) -> None:
    emp, _, assessment, aitem = _setup(db_session, with_fact_missing=False, with_complete_fact=False)
    titem = db_session.query(PerformanceTemplateItem).first()
    titem.handling_mode = "system_supplement"
    titem.score_rule = "ratio_bands"
    titem.rule_config_json = json.dumps(
        {
            "type": "ratio_bands",
            "unit": "%",
            "bands": [
                {"min": "0.9", "max": None, "points": "20"},
                {"min": "0.8", "max": "0.9", "points": "18"},
                {"min": "0", "max": "0.8", "points": "5"},
            ],
        }
    )
    titem.evidence_policy_json = None
    db_session.commit()
    mats.generate_material_tasks(db_session, assessment.id)
    db_session.commit()
    task = db_session.query(PerformanceMaterialTask).one()
    mats.save_draft(db_session, task.id, emp, "95")
    mats.submit_all_drafts(db_session, assessment.id)
    n = mats.apply_system_scores(db_session, assessment.id)
    db_session.commit()
    assert n == 0
    db_session.refresh(aitem)
    assert aitem.actual_value == "95"
    assert aitem.system_score is None
    assert aitem.awarded_points is None
    assert aitem.final_score is None
