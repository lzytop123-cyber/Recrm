"""指标库：筛选、快照隔离、草稿导入。"""
import json
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.performance import (
    PerformanceIndicatorDefinition,
    PerformanceTemplate,
    PerformanceTemplateItem,
)
from app.models.user import User
from app.services import performance_indicator_catalog as catalog


def _user(db: Session) -> User:
    u = User(username="ind_u", password_hash=hash_password("x"), real_name="指标员", is_active=True)
    db.add(u)
    db.flush()
    return u


def test_filter_by_department_and_job_title(db_session: Session) -> None:
    user = _user(db_session)
    market = Department(name="市场部", code="MKT")
    lecturer = Department(name="讲师部", code="LEC")
    db_session.add_all([market, lecturer])
    db_session.flush()
    db_session.add_all(
        [
            PerformanceIndicatorDefinition(
                metric_key="market.signed_clients",
                name="签约数",
                department_id=market.id,
                job_title="市场业务",
                scoring_type="quantity",
                unit="个",
                data_source_code="crm_lead",
                handling_mode="system_supplement",
                status="active",
                created_by=user.id,
            ),
            PerformanceIndicatorDefinition(
                metric_key="lecturer.score",
                name="讲师积分",
                department_id=lecturer.id,
                job_title="讲师",
                scoring_type="subjective",
                unit="分",
                data_source_code="manager_review",
                handling_mode="manager_score",
                status="active",
                created_by=user.id,
            ),
            PerformanceIndicatorDefinition(
                metric_key="common.attendance",
                name="通用出勤",
                department_id=None,
                job_title=None,
                scoring_type="quantity",
                unit="天",
                data_source_code="ledger.manual",
                handling_mode="system_auto",
                status="active",
                created_by=user.id,
            ),
        ]
    )
    db_session.commit()

    market_rows = catalog.list_indicators(
        db_session, department_id=market.id, job_title="市场业务", status="active"
    )
    keys = {r.metric_key for r in market_rows}
    assert "market.signed_clients" in keys
    assert "common.attendance" in keys
    assert "lecturer.score" not in keys

    lec_rows = catalog.list_indicators(
        db_session, department_id=lecturer.id, job_title="讲师", status="active"
    )
    lec_keys = {r.metric_key for r in lec_rows}
    assert "lecturer.score" in lec_keys
    assert "common.attendance" in lec_keys
    assert "market.signed_clients" not in lec_keys


def test_snapshot_isolated_from_catalog_update(db_session: Session) -> None:
    user = _user(db_session)
    ind = catalog.create_indicator(
        db_session,
        user,
        {
            "metric_key": "market.visits",
            "name": "拜访",
            "scoring_type": "quantity",
            "unit": "次",
            "data_source_code": "crm_lead",
            "handling_mode": "system_supplement",
            "rule_config": {
                "target_value": "20",
                "unit": "次",
                "calculation": "proportional",
                "floor_points": "0",
                "cap_at_max": True,
            },
            "evidence_policy_json": {"required_fields": ["visit_note"]},
            "status": "active",
        },
    )
    tpl = PerformanceTemplate(name="快照T", code="SNAP-ISO-1", status="draft", created_by=user.id)
    db_session.add(tpl)
    db_session.flush()
    item = catalog.add_indicator_to_template(
        db_session, template_id=tpl.id, indicator_id=ind.id, weight=Decimal("20"), order_no=1
    )
    assert item.scoring_type == "quantity"
    assert item.name == "拜访"
    original_rule = item.rule_config_json

    catalog.update_indicator(
        db_session,
        ind.id,
        {
            "name": "拜访（改）",
            "rule_config": {
                "target_value": "99",
                "unit": "次",
                "calculation": "proportional",
                "floor_points": "0",
                "cap_at_max": True,
            },
        },
    )
    db_session.refresh(item)
    assert item.name == "拜访"
    assert item.rule_config_json == original_rule
    assert "99" not in (item.rule_config_json or "")


def test_delete_indicator_removes_unused_template_item(db_session: Session) -> None:
    user = _user(db_session)
    ind = catalog.create_indicator(
        db_session,
        user,
        {
            "metric_key": "market.delete_me",
            "name": "待删指标",
            "scoring_type": "quantity",
            "unit": "个",
            "data_source_code": "crm_lead",
            "handling_mode": "system_supplement",
            "rule_config": {
                "target_value": "10",
                "unit": "个",
                "calculation": "proportional",
                "floor_points": "0",
                "cap_at_max": True,
            },
            "status": "draft",
        },
    )
    tpl = PerformanceTemplate(name="删除T", code="DEL-IND-1", status="returned", created_by=user.id)
    db_session.add(tpl)
    db_session.flush()
    item = catalog.add_indicator_to_template(
        db_session, template_id=tpl.id, indicator_id=ind.id, weight=Decimal("10"), order_no=1
    )
    item_id = item.id
    catalog.delete_indicator(db_session, ind.id)
    assert db_session.get(PerformanceIndicatorDefinition, ind.id) is None
    assert db_session.get(PerformanceTemplateItem, item_id) is None


def test_seed_indicators_from_drafts_idempotent(db_session: Session) -> None:
    user = _user(db_session)
    first = catalog.seed_indicators_from_drafts(db_session, created_by=user.id)
    db_session.commit()
    assert first > 0
    second = catalog.seed_indicators_from_drafts(db_session, created_by=user.id)
    db_session.commit()
    assert second == 0
    rows = db_session.query(PerformanceIndicatorDefinition).all()
    assert all(r.status == "active" for r in rows)
    assert len({r.metric_key for r in rows}) == len(rows)


def test_create_rejects_unknown_scoring_type(db_session: Session) -> None:
    user = _user(db_session)
    with pytest.raises(HTTPException) as exc:
        catalog.create_indicator(
            db_session,
            user,
            {
                "metric_key": "x.bad",
                "name": "坏",
                "scoring_type": "unknown_type",
                "unit": "个",
                "data_source_code": "crm_lead",
                "handling_mode": "system_auto",
            },
        )
    assert exc.value.status_code == 422
