"""删除未使用的绩效模板。"""
import json

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.performance import (
    PerformanceAssessment,
    PerformanceCycle,
    PerformanceTemplate,
    PerformanceTemplateItem,
)
from app.models.user import User
from app.services.performance_template import create_template, delete_template

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


def test_delete_unused_template(db_session: Session) -> None:
    tpl = create_template(db_session, name="可删", code="TPL-DEL-1", items=BASE_ITEMS, rules_json=RULES)
    tid = tpl.id
    delete_template(db_session, tid)
    assert db_session.query(PerformanceTemplate).filter(PerformanceTemplate.id == tid).first() is None
    assert (
        db_session.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == tid)
        .count()
        == 0
    )


def test_delete_used_template_rejected(db_session: Session) -> None:
    user = User(username="tpl_del_emp", password_hash=hash_password("x"), real_name="员工", is_active=True)
    cycle = PerformanceCycle(period_label="2099-13")
    db_session.add_all([user, cycle])
    db_session.commit()
    tpl = create_template(db_session, name="已用", code="TPL-DEL-USED", items=BASE_ITEMS, rules_json=RULES)
    db_session.add(PerformanceAssessment(cycle_id=cycle.id, user_id=user.id, template_id=tpl.id))
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        delete_template(db_session, tpl.id)
    assert exc.value.status_code == 409
