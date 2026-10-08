"""KPI 运行期增量模型：表、外键、唯一约束与旧模板兼容。"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.performance import (
    PerformanceActionLog,
    PerformanceAssessment,
    PerformanceAssessmentBatch,
    PerformanceAssessmentItem,
    PerformanceCycle,
    PerformanceIndicatorDefinition,
    PerformanceMaterialTask,
    PerformanceTemplate,
    PerformanceTemplateItem,
    PerformanceTemplateScope,
)
from app.models.user import User


def _seed_user_dept(db: Session) -> tuple[User, Department]:
    dept = Department(name="市场部", code="MARKET")
    db.add(dept)
    db.flush()
    user = User(
        username="kpi_model_u1",
        password_hash=hash_password("x"),
        real_name="模型测试员",
        is_active=True,
        department_id=dept.id,
        job_title="市场业务",
    )
    db.add(user)
    db.flush()
    return user, dept


def test_alembic_head_chains_from_confirmed_revision() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    heads = script.get_heads()
    assert len(heads) == 1
    head = script.get_revision(heads[0])
    assert head.revision == "s1t2u3v4w5x6"
    assert head.down_revision == "r0s1t2u3v4w5"


def test_legacy_approved_template_still_readable(db_session: Session) -> None:
    user, dept = _seed_user_dept(db_session)
    tpl = PerformanceTemplate(
        name="旧加权模板",
        code="LEGACY-READ-1",
        owner_type="hr",
        status="approved",
        engine_version="legacy",
        scoring_mode="legacy_weighted",
        created_by=user.id,
        owner_dept_id=dept.id,
    )
    db_session.add(tpl)
    db_session.flush()
    item = PerformanceTemplateItem(
        template_id=tpl.id,
        order_no=1,
        name="销售额",
        weight=Decimal("100"),
        data_source="manual",
    )
    db_session.add(item)
    db_session.commit()

    loaded = db_session.query(PerformanceTemplate).filter_by(code="LEGACY-READ-1").one()
    assert loaded.status == "approved"
    assert loaded.effective_from is None
    assert loaded.published_at is None
    assert loaded.eligibility_policy_json is None
    loaded_item = (
        db_session.query(PerformanceTemplateItem).filter_by(template_id=loaded.id).one()
    )
    assert loaded_item.indicator_definition_id is None
    assert loaded_item.scoring_type is None
    assert loaded_item.handling_mode is None


def test_indicator_definition_metric_key_unique(db_session: Session) -> None:
    user, dept = _seed_user_dept(db_session)
    row = PerformanceIndicatorDefinition(
        metric_key="market.signed_clients",
        name="签约数",
        department_id=dept.id,
        job_title="市场业务",
        scoring_type="quantity",
        unit="个",
        data_source_code="crm_lead",
        handling_mode="system_supplement",
        status="active",
        created_by=user.id,
    )
    db_session.add(row)
    db_session.flush()
    dup = PerformanceIndicatorDefinition(
        metric_key="market.signed_clients",
        name="签约数重复",
        scoring_type="quantity",
        unit="个",
        data_source_code="crm_lead",
        handling_mode="system_auto",
        status="draft",
        created_by=user.id,
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_template_scope_unique(db_session: Session) -> None:
    user, dept = _seed_user_dept(db_session)
    tpl = PerformanceTemplate(
        name="市场月度",
        code="SCOPE-TPL-1",
        status="draft",
        created_by=user.id,
    )
    db_session.add(tpl)
    db_session.flush()
    db_session.add(
        PerformanceTemplateScope(
            template_id=tpl.id, department_id=dept.id, job_title="市场业务"
        )
    )
    db_session.flush()
    db_session.add(
        PerformanceTemplateScope(
            template_id=tpl.id, department_id=dept.id, job_title="市场业务"
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_assessment_batch_idempotency_unique_and_fk(db_session: Session) -> None:
    user, dept = _seed_user_dept(db_session)
    tpl = PerformanceTemplate(name="批次模板", code="BATCH-TPL-1", status="published", created_by=user.id)
    cycle = PerformanceCycle(period_label="2026-10-batch", status="assessing")
    db_session.add_all([tpl, cycle])
    db_session.flush()
    batch = PerformanceAssessmentBatch(
        cycle_id=cycle.id,
        template_id=tpl.id,
        status="launched",
        hr_review_required=False,
        idempotency_key="idem-batch-1",
        created_by=user.id,
    )
    db_session.add(batch)
    db_session.flush()
    dup = PerformanceAssessmentBatch(
        cycle_id=cycle.id,
        template_id=tpl.id,
        status="launched",
        hr_review_required=False,
        idempotency_key="idem-batch-1",
        created_by=user.id,
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_material_task_unique_prevents_duplicate(db_session: Session) -> None:
    user, dept = _seed_user_dept(db_session)
    tpl = PerformanceTemplate(name="材料模板", code="MAT-TPL-1", status="published", created_by=user.id)
    cycle = PerformanceCycle(period_label="2026-10-mat", status="assessing")
    db_session.add_all([tpl, cycle])
    db_session.flush()
    assessment = PerformanceAssessment(
        cycle_id=cycle.id,
        user_id=user.id,
        department_id=dept.id,
        template_id=tpl.id,
        status="employee_pending",
        instance_key="mat_primary",
        engine_version="v2",
        revision=1,
    )
    db_session.add(assessment)
    db_session.flush()
    aitem = PerformanceAssessmentItem(
        assessment_id=assessment.id,
        order_no=1,
        name="客户行业",
        weight=Decimal("10"),
        data_source="system",
    )
    db_session.add(aitem)
    db_session.flush()
    task = PerformanceMaterialTask(
        assessment_id=assessment.id,
        assessment_item_id=aitem.id,
        source_record_type="crm_customer",
        source_record_id="C-100",
        title="补充客户行业",
        status="pending",
        revision=1,
    )
    db_session.add(task)
    db_session.flush()
    dup = PerformanceMaterialTask(
        assessment_id=assessment.id,
        assessment_item_id=aitem.id,
        source_record_type="crm_customer",
        source_record_id="C-100",
        title="重复任务",
        status="pending",
        revision=1,
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_assessment_runtime_fields_and_action_log(db_session: Session) -> None:
    user, dept = _seed_user_dept(db_session)
    manager = User(
        username="kpi_mgr",
        password_hash=hash_password("x"),
        real_name="主管",
        is_active=True,
        department_id=dept.id,
    )
    db_session.add(manager)
    db_session.flush()
    tpl = PerformanceTemplate(
        name="发布模板",
        code="PUB-TPL-1",
        status="published",
        effective_from=date(2026, 9, 1),
        effective_to=date(2026, 12, 31),
        published_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        published_by=user.id,
        eligibility_policy_json='{"min_days_in_period":15}',
        created_by=user.id,
    )
    cycle = PerformanceCycle(period_label="2026-10-rt", status="assessing")
    db_session.add_all([tpl, cycle])
    db_session.flush()
    batch = PerformanceAssessmentBatch(
        cycle_id=cycle.id,
        template_id=tpl.id,
        status="launched",
        hr_review_required=True,
        idempotency_key="idem-rt-1",
        created_by=user.id,
    )
    db_session.add(batch)
    db_session.flush()
    assessment = PerformanceAssessment(
        cycle_id=cycle.id,
        user_id=user.id,
        department_id=dept.id,
        template_id=tpl.id,
        batch_id=batch.id,
        manager_id=manager.id,
        current_handler_type="employee",
        current_handler_id=user.id,
        person_snapshot_json='{"job_title":"市场业务"}',
        workflow_config_json='{"hr_review_required":true}',
        status="employee_pending",
        instance_key="rt_primary",
        engine_version="v2",
        revision=1,
    )
    db_session.add(assessment)
    db_session.flush()
    log = PerformanceActionLog(
        assessment_id=assessment.id,
        action="launch",
        from_status=None,
        to_status="employee_pending",
        actor_id=user.id,
        note="批量发起",
        payload_json='{"batch_id":%d}' % batch.id,
    )
    db_session.add(log)
    db_session.commit()

    loaded = db_session.query(PerformanceAssessment).filter_by(id=assessment.id).one()
    assert loaded.batch_id == batch.id
    assert loaded.manager_id == manager.id
    assert loaded.current_handler_type == "employee"
    assert loaded.person_snapshot_json is not None
    assert db_session.query(PerformanceActionLog).filter_by(assessment_id=loaded.id).count() == 1


def test_template_item_snapshot_from_indicator(db_session: Session) -> None:
    user, dept = _seed_user_dept(db_session)
    ind = PerformanceIndicatorDefinition(
        metric_key="market.visits",
        name="拜访",
        department_id=dept.id,
        job_title="市场业务",
        scoring_type="quantity",
        default_target="20",
        unit="次",
        data_source_code="crm_lead",
        handling_mode="employee_submit",
        rule_config_json='{"type":"proportional"}',
        evidence_policy_json='{"required_fields":["visit_note"]}',
        status="active",
        created_by=user.id,
    )
    tpl = PerformanceTemplate(name="快照模板", code="SNAP-TPL-1", status="draft", created_by=user.id)
    db_session.add_all([ind, tpl])
    db_session.flush()
    item = PerformanceTemplateItem(
        template_id=tpl.id,
        order_no=1,
        name=ind.name,
        weight=Decimal("20"),
        data_source="system",
        metric_key=ind.metric_key,
        indicator_definition_id=ind.id,
        scoring_type=ind.scoring_type,
        unit=ind.unit,
        handling_mode=ind.handling_mode,
        evidence_policy_json=ind.evidence_policy_json,
        rule_config_json=ind.rule_config_json,
        max_points=Decimal("20"),
    )
    db_session.add(item)
    db_session.commit()
    loaded = db_session.query(PerformanceTemplateItem).filter_by(template_id=tpl.id).one()
    assert loaded.indicator_definition_id == ind.id
    assert loaded.scoring_type == "quantity"
    assert loaded.handling_mode == "employee_submit"
    assert "visit_note" in (loaded.evidence_policy_json or "")
