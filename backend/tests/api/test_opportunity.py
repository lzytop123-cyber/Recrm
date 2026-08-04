"""商机创建、阶段变更、线索转化联动。"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.customer import Customer
from app.models.department import Department
from app.models.lead import LEAD_STATUS_ASSIGNED, LEAD_STATUS_CONVERTED, Lead
from app.models.opportunity import OPP_STAGE_NEED, OPP_STAGE_WON, Opportunity
from app.models.role import Role
from app.models.user import User
from app.schemas.lead import LeadConvertRequest, LeadCreate
from app.schemas.opportunity import OpportunityCreate, OpportunityStageChange
from app.services import lead as lead_service
from app.services import opportunity as opportunity_service


def _seed_sales(db: Session) -> User:
    role = db.query(Role).filter(Role.code == "sales").first()
    if not role:
        role = Role(name="销售", code="sales", data_scope="personal")
        db.add(role)
        db.flush()
    dept = db.query(Department).filter(Department.code == "ROOT").first()
    if not dept:
        dept = Department(name="总公司", code="ROOT")
        db.add(dept)
        db.flush()
    user = User(
        username="sales_opp",
        password_hash=hash_password("x"),
        real_name="销售乙",
        is_active=True,
        department_id=dept.id,
    )
    user.roles.append(role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_and_change_stage(db_session: Session) -> None:
    user = _seed_sales(db_session)
    customer = Customer(
        name="测试客户",
        status="potential",
        owner_id=user.id,
        creator_id=user.id,
        department_id=user.department_id,
        source="manual",
    )
    db_session.add(customer)
    db_session.commit()

    opp = opportunity_service.create_opportunity(
        db_session,
        user,
        OpportunityCreate(
            title="AI 项目",
            customer_id=customer.id,
            business_type="ai_custom",
            expected_amount=Decimal("100000"),
            requirement_summary="客户确认二期数据中台需求与预算",
        ),
    )
    assert opp.stage == OPP_STAGE_NEED
    assert opp.opportunity_no.startswith("SJ")

    updated = opportunity_service.change_stage(
        db_session,
        user,
        opp.id,
        OpportunityStageChange(stage="proposal", evidence="已发方案邮件"),
    )
    assert updated.stage == "proposal"

    won = opportunity_service.change_stage(
        db_session,
        user,
        opp.id,
        OpportunityStageChange(stage=OPP_STAGE_WON, evidence="客户确认签约"),
    )
    assert won.stage == OPP_STAGE_WON
    assert won.closed_at is not None


def test_lead_convert_creates_opportunity(db_session: Session) -> None:
    user = _seed_sales(db_session)
    lead = lead_service.create_lead(
        db_session,
        user,
        LeadCreate(name="王总", company_name="星河科技", phone="13900001111", budget=Decimal("50000")),
    )
    # 分配给自己后才能转化（pending 通常不可操作）
    lead_row = db_session.query(Lead).filter(Lead.id == lead.id).first()
    assert lead_row is not None
    lead_row.status = LEAD_STATUS_ASSIGNED
    lead_row.owner_id = user.id
    db_session.commit()

    result = lead_service.convert_lead(
        db_session,
        user,
        lead.id,
        LeadConvertRequest(customer_name="星河科技有限公司", business_type="ai_product"),
    )
    assert result["customer_id"] > 0
    assert result["opportunity_id"] > 0
    assert result["lead"].status == LEAD_STATUS_CONVERTED

    opp = db_session.query(Opportunity).filter(Opportunity.id == result["opportunity_id"]).first()
    assert opp is not None
    assert opp.customer_id == result["customer_id"]
    assert opp.source_lead_id == lead.id
    assert Decimal(opp.expected_amount) == Decimal("50000")
