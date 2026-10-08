"""建周期 → 生成考核单（含 items）→ 审批推进。"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.approval_flow import ApprovalInstance
from app.models.customer import Customer
from app.models.opportunity import OPP_STAGE_WON, Opportunity
from app.models.performance import PerformanceAssessmentItem
from app.models.role import Role
from app.models.user import User
from app.schemas.performance import ItemRateIn, ManagerRateRequest, SelfRateRequest
from app.seed import seed_approval_rules
from app.services.performance import create_cycle, generate_assessments, rate_manager, rate_self
from app.services.performance_template import create_template


ITEMS = [
    {
        "order_no": 1,
        "name": "销售额",
        "weight": 50,
        "data_source": "system",
        "source_ref": "customer.deals",
        "target_value": "100000",
    },
    {
        "order_no": 2,
        "name": "协作",
        "weight": 50,
        "data_source": "manual",
    },
]


def _user(db: Session, username: str, **kw) -> User:
    u = User(
        username=username,
        password_hash=hash_password("x"),
        real_name=username,
        is_active=True,
        **kw,
    )
    db.add(u)
    db.flush()
    return u


def test_create_cycle_generates_items_and_approval(db_session: Session) -> None:
    seed_approval_rules(db_session)
    skip = _user(db_session, "skip")
    mgr = _user(db_session, "mgr", manager_id=skip.id)
    staff = _user(db_session, "staff", manager_id=mgr.id)
    hr_role = Role(name="人力资源", code="hr", data_scope="company")
    hr = _user(db_session, "hr")
    hr.roles.append(hr_role)
    db_session.add(hr_role)
    db_session.flush()

    cust = Customer(name="客户A", owner_id=staff.id)
    db_session.add(cust)
    db_session.flush()
    opp = Opportunity(
        opportunity_no="OPP-1",
        title="赢单",
        customer_id=cust.id,
        stage=OPP_STAGE_WON,
        expected_amount=Decimal("80000"),
        owner_id=staff.id,
        won_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    db_session.add(opp)
    db_session.commit()

    tpl = create_template(db_session, name="销售", code="TPL-C1", items=ITEMS)
    cycle = create_cycle(db_session, "2026-07", tpl.id, cycle_type="monthly")
    rows = generate_assessments(db_session, cycle.id, scope={"user_ids": [staff.id]})
    assert len(rows) == 1
    row = rows[0]
    assert row.template_id == tpl.id
    assert row.approval_instance_id is not None
    items = (
        db_session.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == row.id)
        .order_by(PerformanceAssessmentItem.order_no)
        .all()
    )
    assert [i.name for i in items] == ["销售额", "协作"]
    deal = items[0]
    assert deal.actual_value is not None
    assert deal.system_score is None

    inst = db_session.query(ApprovalInstance).filter(ApprovalInstance.id == row.approval_instance_id).first()
    assert inst is not None
    assert inst.rule_code == "AP-KPI-01"
    assert inst.current_seq == 1
    assert sorted({t.seq for t in inst.tasks}) == [1, 2, 3, 4]

    rated = rate_self(
        db_session,
        staff,
        row.id,
        SelfRateRequest(
            self_score=80,
            items=[ItemRateIn(item_id=items[1].id, self_score=Decimal("80"), self_comment="还行")],
        ),
    )
    assert rated.status == "pending_manager"
    db_session.refresh(inst)
    assert inst.current_seq == 2

    rated = rate_manager(
        db_session,
        mgr,
        row.id,
        ManagerRateRequest(
            okr_score=80,
            kpi_score=80,
            behavior_score=80,
            comment="同意",
            items=[
                ItemRateIn(item_id=items[0].id, leader_score=Decimal("80")),
                ItemRateIn(item_id=items[1].id, leader_score=Decimal("90")),
            ],
        ),
    )
    assert rated.status == "pending_manager"
    db_session.refresh(inst)
    assert inst.current_seq == 3

    rated = rate_manager(
        db_session,
        skip,
        row.id,
        ManagerRateRequest(okr_score=80, kpi_score=80, behavior_score=80, comment="复核通过"),
    )
    assert rated.status == "pending_calibration"
    db_session.refresh(inst)
    assert inst.current_seq == 4

    rated = rate_manager(
        db_session,
        hr,
        row.id,
        ManagerRateRequest(okr_score=80, kpi_score=80, behavior_score=80, comment="归档"),
    )
    assert rated.status == "completed"
    assert rated.final_score is not None
    assert rated.grade in {"A+", "A", "B", "C", "D"}
