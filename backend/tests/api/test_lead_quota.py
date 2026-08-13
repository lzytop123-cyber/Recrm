"""线索公海额度与退回原因。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.lead import LEAD_STATUS_PENDING, Lead, LeadLog
from app.models.role import Role
from app.models.user import User
from app.schemas.lead import LeadCreate
from app.services import lead as lead_service


def _seed_sales_user(db: Session) -> User:
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
        username="sales_quota",
        password_hash=hash_password("x"),
        real_name="销售甲",
        is_active=True,
        department_id=dept.id,
    )
    user.roles.append(role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_claim_quota_blocks_over_daily_limit(db_session: Session, monkeypatch) -> None:
    from app.config import Settings, get_settings

    monkeypatch.setattr(
        "app.services.lead.get_settings",
        lambda: Settings(
            lead_daily_claim_limit=1,
            lead_protect_hold_limit=100,
            lead_protect_days=7,
        ),
    )
    get_settings.cache_clear()

    user = _seed_sales_user(db_session)
    lead1 = lead_service.create_lead(
        db_session,
        user,
        LeadCreate(name="客户一", company_name="A公司", phone="13800000001", self_follow=False),
    )
    lead2 = lead_service.create_lead(
        db_session,
        user,
        LeadCreate(name="客户二", company_name="B公司", phone="13800000002", self_follow=False),
    )
    assert lead1.status == LEAD_STATUS_PENDING

    lead_service.claim_lead(db_session, user, lead1.id)
    quota = lead_service.get_lead_quota(db_session, user)
    assert quota["daily_claimed"] == 1
    assert quota["can_claim"] is False

    try:
        lead_service.claim_lead(db_session, user, lead2.id)
        assert False, "should block second claim"
    except Exception as exc:
        assert "上限" in str(exc.detail if hasattr(exc, "detail") else exc)


def test_return_writes_reason_type(db_session: Session) -> None:
    user = _seed_sales_user(db_session)
    lead = lead_service.create_lead(
        db_session,
        user,
        LeadCreate(name="客户三", company_name="C公司", phone="13800000003", self_follow=False),
    )
    claimed = lead_service.claim_lead(db_session, user, lead.id)
    lead_service.return_to_pool(
        db_session,
        user,
        claimed.id,
        "暂时联系不上",
        reason_type="unreachable",
    )
    log = (
        db_session.query(LeadLog)
        .filter(LeadLog.lead_id == claimed.id, LeadLog.action == "return")
        .order_by(LeadLog.id.desc())
        .first()
    )
    assert log is not None
    assert "unreachable" in (log.detail or "")


def test_lead_log_shows_real_name(db_session: Session) -> None:
    user = _seed_sales_user(db_session)
    lead = lead_service.create_lead(
        db_session,
        user,
        LeadCreate(name="客户四", company_name="D公司", phone="13800000004", self_follow=False),
    )
    claimed = lead_service.claim_lead(db_session, user, lead.id)
    create_log = (
        db_session.query(LeadLog)
        .filter(LeadLog.lead_id == claimed.id, LeadLog.action == "create")
        .first()
    )
    assert create_log is not None
    assert create_log.username == "销售甲"

    create_log.username = user.username
    db_session.commit()

    detail = lead_service.get_lead_detail(db_session, user, claimed.id)
    shown = next(x for x in detail.logs if x.action == "create")
    assert shown.username == "销售甲"
