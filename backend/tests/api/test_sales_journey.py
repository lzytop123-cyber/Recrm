"""销售旅程聚合：线索→商机→合同主线。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.lead import LEAD_STATUS_FOLLOWING
from app.models.opportunity import Opportunity
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.schemas.lead import LeadConvertRequest, LeadCreate, LeadFollowUpCreate
from app.services import lead as lead_service
from app.services import sales_journey as journey_service


def _ensure_sales(db: Session) -> User:
    role = db.query(Role).filter(Role.code == "sales").first()
    if not role:
        role = Role(name="销售", code="sales", data_scope="personal")
        db.add(role)
        db.flush()
    for code, name in (("lead:view", "查看线索"), ("opportunity:view", "查看商机")):
        perm = db.query(Permission).filter(Permission.code == code).first()
        if not perm:
            perm = Permission(name=name, code=code, module=code.split(":")[0])
            db.add(perm)
            db.flush()
        if perm not in role.permissions:
            role.permissions.append(perm)
    dept = db.query(Department).filter(Department.code == "ROOT").first()
    if not dept:
        dept = Department(name="总公司", code="ROOT")
        db.add(dept)
        db.flush()
    u = User(
        username="journey_sales",
        password_hash=hash_password("x"),
        real_name="旅程销售",
        is_active=True,
        department_id=dept.id,
    )
    u.roles.append(role)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_journey_before_and_after_convert(db_session: Session) -> None:
    sales = _ensure_sales(db_session)
    lead = lead_service.create_lead(
        db_session,
        sales,
        LeadCreate(name="旅程客户", company_name="旅程公司", phone="13800001111"),
    )
    lead_service.add_follow_up(
        db_session,
        sales,
        lead.id,
        LeadFollowUpCreate(method="phone", content="首通", result="advance"),
    )
    lead = lead_service.get_lead_detail(db_session, sales, lead.id)
    assert lead.status == LEAD_STATUS_FOLLOWING

    before = journey_service.build_sales_journey(db_session, lead=lead)
    keys = [m["key"] for m in before["milestones"]]
    assert keys[:4] == ["lead_created", "lead_assigned", "lead_following", "lead_converted"]
    assert before["current_key"] == "lead_following"
    assert before["links"]["opportunity_id"] is None
    assert any(m["key"] == "contract" and m["status"] == "pending" for m in before["milestones"])

    result = lead_service.convert_lead(
        db_session,
        sales,
        lead.id,
        LeadConvertRequest(opportunity_title="旅程商机", business_type="ai_product"),
    )
    assert result["opportunity_id"]
    lead = lead_service.get_lead_detail(db_session, sales, lead.id)
    assert lead.converted_opportunity_id == result["opportunity_id"]

    after = journey_service.build_sales_journey(db_session, lead=lead)
    assert after["links"]["opportunity_id"] == result["opportunity_id"]
    assert after["links"]["customer_id"] == result["customer_id"]
    assert after["current_key"] == "opp_need_confirm"
    converted = next(m for m in after["milestones"] if m["key"] == "lead_converted")
    assert converted["status"] == "done"

    opp = db_session.get(Opportunity, result["opportunity_id"])
    from_opp = journey_service.build_sales_journey(db_session, opportunity=opp)
    assert from_opp["links"]["lead_id"] == lead.id
    assert from_opp["current_key"] == "opp_need_confirm"

    # 推进到赢单并挂合同后，当前节点应落在合同
    from decimal import Decimal

    from app.models.contract import CONTRACT_STATUS_SIGNED, Contract
    from app.models.opportunity import OPP_STAGE_WON

    opp.stage = OPP_STAGE_WON
    db_session.add(
        Contract(
            contract_no="HT-JOURNEY-001",
            title="旅程合同",
            customer_id=result["customer_id"],
            opportunity_id=opp.id,
            contract_type="ai_product",
            amount=Decimal("10000"),
            status=CONTRACT_STATUS_SIGNED,
            owner_id=sales.id,
            creator_id=sales.id,
        )
    )
    db_session.commit()
    db_session.refresh(opp)

    with_contract = journey_service.build_sales_journey(db_session, opportunity=opp)
    assert with_contract["current_key"] == "contract"
    assert with_contract["links"]["contract_id"]
    contract_node = next(m for m in with_contract["milestones"] if m["key"] == "contract")
    assert contract_node["status"] == "current"
    assert "已签署" in contract_node["label"]
