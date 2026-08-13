"""商机业务逻辑：创建、列表、阶段推进、跟进、起草合同。"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import resolve_data_scope, user_can
from app.models.customer import Customer
from app.models.opportunity import (
    OPP_OPEN_STAGES,
    OPP_STAGE_LABEL,
    OPP_STAGE_LOST,
    OPP_STAGE_NEED,
    OPP_STAGE_WON,
    OPP_STAGES,
    Opportunity,
    OpportunityActivity,
)
from app.models.user import User
from app.schemas.opportunity import (
    OpportunityActivityCreate,
    OpportunityCreate,
    OpportunityStageChange,
    OpportunityUpdate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return None
    return u.real_name or u.username


def _gen_opportunity_no(db: Session) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"SJ{today}"
    last = (
        db.query(Opportunity.opportunity_no)
        .filter(Opportunity.opportunity_no.like(f"{prefix}%"))
        .order_by(Opportunity.opportunity_no.desc())
        .first()
    )
    seq = int(last[0][-4:]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def enrich_opportunity(db: Session, opp: Opportunity) -> Opportunity:
    customer = db.query(Customer).filter(Customer.id == opp.customer_id).first()
    opp.customer_name = customer.name if customer else None  # type: ignore[attr-defined]
    opp.owner_name = _user_name(db, opp.owner_id)  # type: ignore[attr-defined]
    opp.creator_name = _user_name(db, opp.creator_id)  # type: ignore[attr-defined]
    return opp


def _active_contract_for_opportunity(db: Session, opportunity_id: int):
    """商机关联的未终止合同（同一商机仅允许一份有效合同）。"""
    from app.models.contract import CONTRACT_STATUS_TERMINATED, Contract

    return (
        db.query(Contract)
        .filter(
            Contract.opportunity_id == opportunity_id,
            Contract.status != CONTRACT_STATUS_TERMINATED,
        )
        .order_by(Contract.id.desc())
        .first()
    )


def attach_linked_contract(db: Session, opp: Opportunity) -> Opportunity:
    linked = _active_contract_for_opportunity(db, opp.id)
    opp.linked_contract_id = linked.id if linked else None  # type: ignore[attr-defined]
    opp.linked_contract_no = linked.contract_no if linked else None  # type: ignore[attr-defined]
    opp.linked_contract_status = linked.status if linked else None  # type: ignore[attr-defined]
    return opp


def append_contract_milestone(
    db: Session,
    user: User,
    *,
    opportunity_id: Optional[int],
    content: str,
    contract_no: Optional[str] = None,
) -> None:
    """商机轨迹仅记录合同关键里程碑，不替代合同详情内的完整状态。"""
    if not opportunity_id:
        return
    db.add(
        OpportunityActivity(
            opportunity_id=opportunity_id,
            user_id=user.id,
            activity_type="contract",
            content=content.strip(),
            evidence=contract_no,
        )
    )


def assert_can_view(user: User, opp: Opportunity) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes or user_can(user, "opportunity:manage"):
        return
    scope = resolve_data_scope(user, "opportunity")
    if scope == "company":
        return
    if opp.owner_id == user.id or opp.creator_id == user.id:
        return
    if scope == "department" and user.department_id and opp.department_id == user.department_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该商机")


def assert_can_edit(user: User, opp: Opportunity) -> None:
    if opp.stage in {OPP_STAGE_WON, OPP_STAGE_LOST}:
        raise HTTPException(status_code=400, detail="已关闭商机不可编辑")
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes or user_can(user, "opportunity:manage"):
        return
    if opp.owner_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权编辑该商机")


def create_opportunity(db: Session, user: User, payload: OpportunityCreate) -> Opportunity:
    from app.services import platform as platform_service

    platform_service.assert_business_type(db, payload.business_type, enabled_only=True)
    stage = payload.stage or OPP_STAGE_NEED
    if stage not in OPP_STAGES:
        raise HTTPException(status_code=400, detail="无效的商机阶段")
    if not (payload.requirement_summary or "").strip():
        raise HTTPException(status_code=400, detail="需求与成交依据为必填项")
    customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    if not customer:
        raise HTTPException(status_code=400, detail="客户不存在")

    opp = Opportunity(
        opportunity_no=_gen_opportunity_no(db),
        title=payload.title.strip(),
        customer_id=payload.customer_id,
        source_lead_id=payload.source_lead_id,
        business_type=payload.business_type,
        stage=stage,
        expected_amount=payload.expected_amount or Decimal("0"),
        currency="CNY",
        owner_id=user.id,
        creator_id=user.id,
        department_id=user.department_id or customer.department_id,
        requirement_summary=payload.requirement_summary,
        next_action_at=payload.next_action_at,
        next_action_note=payload.next_action_note,
        remark=payload.remark,
    )
    db.add(opp)
    db.flush()
    db.add(
        OpportunityActivity(
            opportunity_id=opp.id,
            user_id=user.id,
            activity_type="create",
            content=f"创建商机，阶段：{OPP_STAGE_LABEL.get(stage, stage)}",
            to_stage=stage,
        )
    )
    db.commit()
    db.refresh(opp)
    return enrich_opportunity(db, opp)


def update_opportunity(
    db: Session, user: User, opportunity_id: int, payload: OpportunityUpdate
) -> Opportunity:
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="商机不存在")
    assert_can_view(user, opp)
    assert_can_edit(user, opp)

    data = payload.model_dump(exclude_unset=True)
    if "business_type" in data and data["business_type"] is not None:
        from app.services import platform as platform_service

        data["business_type"] = platform_service.assert_business_type(
            db, data["business_type"], enabled_only=True
        )
    if "title" in data and data["title"]:
        data["title"] = data["title"].strip()
    for k, v in data.items():
        setattr(opp, k, v)

    db.commit()
    db.refresh(opp)
    return enrich_opportunity(db, opp)


def list_opportunities(
    db: Session,
    user: User,
    *,
    stage: Optional[str] = None,
    keyword: Optional[str] = None,
    customer_id: Optional[int] = None,
    scope_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Opportunity]]:
    q = db.query(Opportunity)
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    scope = resolve_data_scope(user, "opportunity")

    if scope_filter == "mine":
        q = q.filter(Opportunity.owner_id == user.id)
    else:
        if not is_admin and scope == "personal":
            q = q.filter(or_(Opportunity.owner_id == user.id, Opportunity.creator_id == user.id))
        elif not is_admin and scope == "department" and user.department_id:
            q = q.filter(
                or_(
                    Opportunity.department_id == user.department_id,
                    Opportunity.owner_id == user.id,
                    Opportunity.creator_id == user.id,
                )
            )

    if stage:
        q = q.filter(Opportunity.stage == stage)
    if customer_id:
        q = q.filter(Opportunity.customer_id == customer_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                Opportunity.title.ilike(like),
                Opportunity.opportunity_no.ilike(like),
                Opportunity.requirement_summary.ilike(like),
            )
        )

    total = q.count()
    items = (
        q.order_by(Opportunity.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, [enrich_opportunity(db, x) for x in items]


def get_opportunity_detail(db: Session, user: User, opportunity_id: int) -> Opportunity:
    opp = (
        db.query(Opportunity)
        .options(joinedload(Opportunity.activities))
        .filter(Opportunity.id == opportunity_id)
        .first()
    )
    if not opp:
        raise HTTPException(status_code=404, detail="商机不存在")
    assert_can_view(user, opp)
    activities = sorted(opp.activities or [], key=lambda x: x.id, reverse=True)
    for act in activities:
        act.user_name = _user_name(db, act.user_id)  # type: ignore[attr-defined]
    opp.activities = activities
    enrich_opportunity(db, opp)
    return attach_linked_contract(db, opp)


def change_stage(
    db: Session, user: User, opportunity_id: int, payload: OpportunityStageChange
) -> Opportunity:
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="商机不存在")
    assert_can_view(user, opp)
    assert_can_edit(user, opp)

    to_stage = payload.stage
    if to_stage not in OPP_STAGES:
        raise HTTPException(status_code=400, detail="无效的目标阶段")
    if to_stage == opp.stage:
        raise HTTPException(status_code=400, detail="阶段未变化")
    if not (payload.evidence or "").strip():
        raise HTTPException(status_code=400, detail="阶段变更须填写依据")
    if to_stage == OPP_STAGE_LOST and not (payload.lost_reason or "").strip():
        raise HTTPException(status_code=400, detail="输单须填写原因")

    from_stage = opp.stage
    now = _now()
    opp.stage = to_stage
    if to_stage == OPP_STAGE_WON:
        opp.won_at = now
        opp.closed_at = now
        opp.lost_reason = None
    elif to_stage == OPP_STAGE_LOST:
        opp.lost_at = now
        opp.closed_at = now
        opp.lost_reason = payload.lost_reason
    elif to_stage in OPP_OPEN_STAGES:
        opp.won_at = None
        opp.lost_at = None
        opp.closed_at = None
        if to_stage != OPP_STAGE_LOST:
            opp.lost_reason = None

    db.add(
        OpportunityActivity(
            opportunity_id=opp.id,
            user_id=user.id,
            activity_type="stage_change",
            content=(
                f"阶段：{OPP_STAGE_LABEL.get(from_stage, from_stage)}"
                f" → {OPP_STAGE_LABEL.get(to_stage, to_stage)}"
            ),
            evidence=payload.evidence,
            from_stage=from_stage,
            to_stage=to_stage,
        )
    )
    db.commit()
    db.refresh(opp)
    return enrich_opportunity(db, opp)


def add_activity(
    db: Session, user: User, opportunity_id: int, payload: OpportunityActivityCreate
) -> OpportunityActivity:
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="商机不存在")
    assert_can_view(user, opp)
    assert_can_edit(user, opp)

    act = OpportunityActivity(
        opportunity_id=opp.id,
        user_id=user.id,
        activity_type="follow",
        content=payload.content.strip(),
        evidence=payload.evidence,
        next_action_at=payload.next_action_at,
    )
    if payload.next_action_at:
        opp.next_action_at = payload.next_action_at
    if payload.next_action_note is not None:
        opp.next_action_note = payload.next_action_note
    db.add(act)
    db.commit()
    db.refresh(act)
    act.user_name = _user_name(db, act.user_id)  # type: ignore[attr-defined]
    return act


def opportunity_stats(db: Session, user: User) -> dict:
    def _count(stage: Optional[str] = None) -> int:
        total, _ = list_opportunities(db, user, stage=stage, page=1, page_size=1)
        return total

    total = _count()
    won = _count(OPP_STAGE_WON)
    lost = _count(OPP_STAGE_LOST)
    negotiation = _count("negotiation")
    open_count = total - won - lost

    # 进行中金额 / 逾期动作 / 待生成合同：在可见范围内聚合
    _, all_items = list_opportunities(db, user, page=1, page_size=500)
    now = _now()
    open_amount = Decimal("0")
    won_amount = Decimal("0")
    overdue = 0
    pending_contract = 0
    for item in all_items:
        if item.stage == OPP_STAGE_WON:
            won_amount += Decimal(item.expected_amount or 0)
            pending_contract += 1
        elif item.stage != OPP_STAGE_LOST:
            open_amount += Decimal(item.expected_amount or 0)
            if item.next_action_at:
                na = item.next_action_at
                if na.tzinfo is None:
                    na = na.replace(tzinfo=timezone.utc)
                if na < now:
                    overdue += 1

    from app.models.customer import CUSTOMER_STATUS_ACTIVE, CUSTOMER_STATUS_POTENTIAL
    from app.services import customer as customer_service

    potential, _ = customer_service.list_customers(
        db, user, status=CUSTOMER_STATUS_POTENTIAL, page=1, page_size=1
    )
    active, _ = customer_service.list_customers(
        db, user, status=CUSTOMER_STATUS_ACTIVE, page=1, page_size=1
    )
    customer_total = potential + active

    return {
        "total": total,
        "open_count": max(open_count, 0),
        "open_amount": open_amount,
        "won": won,
        "lost": lost,
        "negotiation": negotiation,
        "overdue_actions": overdue,
        "pending_contract": pending_contract,
        "customer_count": customer_total,
        "won_amount": won_amount,
    }


def draft_contract_from_opportunity(db: Session, user: User, opportunity_id: int):
    """从赢单/谈判中商机起草合同草稿。同一商机仅允许一份未终止合同。"""
    from app.schemas.contract import ContractCreate
    from app.services import contract as contract_service

    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="商机不存在")
    assert_can_view(user, opp)
    if opp.stage == OPP_STAGE_LOST:
        raise HTTPException(status_code=400, detail="输单商机不可起草合同")
    if opp.stage not in {OPP_STAGE_WON, "negotiation"}:
        raise HTTPException(status_code=400, detail="仅商务谈判或赢单阶段可发起合同")

    existing = _active_contract_for_opportunity(db, opportunity_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"该商机已有合同 {existing.contract_no}，不可重复发起",
        )

    from app.services import platform as platform_service

    type_values = platform_service.business_type_values(db, enabled_only=False)
    payload = ContractCreate(
        title=f"{opp.title}-合同",
        customer_id=opp.customer_id,
        contract_type=opp.business_type if opp.business_type in type_values else "other",
        amount=opp.expected_amount or Decimal("0"),
        remark=f"由商机 {opp.opportunity_no} 起草",
        opportunity_id=opportunity_id,
    )
    return contract_service.create_contract(db, user, payload)
