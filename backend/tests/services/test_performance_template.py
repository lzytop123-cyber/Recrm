"""模板 fork 与权重校验。"""
import json

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.performance import PerformanceTemplate, PerformanceTemplateItem
from app.models.user import User
from app.seed import seed_approval_rules
from app.services.performance_template import (
    create_template,
    fork_template,
    submit_for_review,
    validate_weights,
)


RULES = json.dumps(
    {
        "weight_bounds": {"system": [40, 60], "manual": [0, 30]},
        "allowed_sources": ["system", "okr", "manual", "self_manual"],
    },
    ensure_ascii=False,
)

BASE_ITEMS = [
    {"order_no": 1, "name": "销售额", "weight": 50, "data_source": "system", "source_ref": "customer.deals"},
    {"order_no": 2, "name": "OKR", "weight": 30, "data_source": "okr", "source_ref": "okr.kr_progress"},
    {"order_no": 3, "name": "协作", "weight": 20, "data_source": "manual"},
]


def test_validate_weights_must_sum_100() -> None:
    with pytest.raises(HTTPException):
        validate_weights([{"weight": 40, "data_source": "system"}])


def test_validate_weights_bounds() -> None:
    with pytest.raises(HTTPException):
        validate_weights(
            [
                {"weight": 70, "data_source": "system"},
                {"weight": 30, "data_source": "okr"},
            ],
            json.loads(RULES),
        )


def test_update_points_sum_skips_weight_total_100(db_session: Session) -> None:
    """points_sum 模板 weight≈max_points，草稿保存不要求权重合计 100。"""
    from decimal import Decimal

    from app.models.performance import PerformanceTemplate
    from app.services.performance_template import update_template

    row = PerformanceTemplate(
        name="直播主播",
        code="TPL-LIVE-SKIP-W",
        status="draft",
        engine_version="kpi-v2",
        scoring_mode="points_sum",
        nominal_total=Decimal("100"),
    )
    db_session.add(row)
    db_session.commit()
    updated = update_template(
        db_session,
        row.id,
        items=[
            {
                "order_no": 1,
                "name": "完成率",
                "weight": 20,
                "data_source": "system",
                "max_points": 20,
            },
            {
                "order_no": 2,
                "name": "转化率",
                "weight": 20,
                "data_source": "system",
                "max_points": 20,
            },
            {
                "order_no": 3,
                "name": "额外项",
                "weight": 80,
                "data_source": "manual",
                "max_points": 80,
            },
        ],
    )
    assert len(updated.items) == 3  # type: ignore[attr-defined]
    total = sum(Decimal(str(i.weight)) for i in updated.items)  # type: ignore[attr-defined]
    assert total == Decimal("120")


def test_submit_promotes_legacy_with_max_points(db_session: Session) -> None:
    """误标为 legacy 但指标带 max_points 的模板，提交时升级为 points_sum 且不校验权重 100。"""
    from decimal import Decimal

    from app.core.security import hash_password
    from app.models.performance import PerformanceTemplate, PerformanceTemplateItem
    from app.models.user import User
    from app.seed import seed_approval_rules
    from app.services.performance_template import submit_for_review

    seed_approval_rules(db_session)
    db_session.commit()
    user = User(username="kpi_hr2", password_hash=hash_password("x"), real_name="HR", is_active=True)
    db_session.add(user)
    db_session.flush()
    row = PerformanceTemplate(
        name="误建满分制",
        code="TPL-MISLABEL-110",
        status="draft",
        engine_version="legacy",
        scoring_mode="legacy_weighted",
    )
    db_session.add(row)
    db_session.flush()
    for i, (name, pts) in enumerate(
        [("A", 80), ("B", 10), ("C", 10), ("D", 10)],
        start=1,
    ):
        db_session.add(
            PerformanceTemplateItem(
                template_id=row.id,
                order_no=i,
                name=name,
                weight=Decimal(str(pts)),
                data_source="system",
                max_points=Decimal(str(pts)),
            )
        )
    db_session.commit()
    out = submit_for_review(db_session, row.id, user)
    assert out.status == "pending_review"
    assert out.scoring_mode == "points_sum"
    assert out.engine_version == "kpi-v2"
    assert out.nominal_total == Decimal("110")


def test_fork_keeps_base_rules(db_session: Session) -> None:
    dept = Department(name="销售部", code="SALES")
    db_session.add(dept)
    db_session.flush()
    base = create_template(
        db_session,
        name="销售基础",
        code="TPL-SALES",
        items=BASE_ITEMS,
        rules_json=RULES,
    )
    child = fork_template(db_session, base.id, owner_dept_id=dept.id)
    assert child.base_template_id == base.id
    assert child.owner_type == "dept"
    assert child.owner_dept_id == dept.id
    assert child.rules_json == base.rules_json
    child_items = (
        db_session.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == child.id)
        .all()
    )
    assert len(child_items) == 3
    assert {i.name for i in child_items} == {"销售额", "OKR", "协作"}


def test_submit_for_review_starts_approval(db_session: Session) -> None:
    seed_approval_rules(db_session)
    db_session.commit()
    user = User(username="hr1", password_hash=hash_password("x"), real_name="HR", is_active=True)
    db_session.add(user)
    db_session.flush()
    tpl = create_template(db_session, name="基础", code="TPL-HR", items=BASE_ITEMS, rules_json=RULES)
    row = submit_for_review(db_session, tpl.id, user)
    assert row.status == "pending_review"
    assert row.approval_instance_id is not None
