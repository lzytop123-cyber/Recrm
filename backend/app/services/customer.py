"""
客户管理业务逻辑：录入、编辑、列表、详情、跟进、数据范围过滤。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import collect_data_scopes, user_can, widest_data_scope
from app.models.customer import (
    CUSTOMER_STATUS_ACTIVE,
    CUSTOMER_STATUS_PAUSED,
    CUSTOMER_STATUS_POTENTIAL,
    CUSTOMER_STATUS_TERMINATED,
    CUSTOMER_STATUSES,
    Customer,
    CustomerFollowUp,
)
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerFollowUpCreate, CustomerUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return None
    return u.real_name or u.username


def enrich_customer(db: Session, customer: Customer) -> Customer:
    customer.owner_name = _user_name(db, customer.owner_id)  # type: ignore[attr-defined]
    customer.creator_name = _user_name(db, customer.creator_id)  # type: ignore[attr-defined]
    return customer


def assert_can_view(user: User, customer: Customer) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes or user_can(user, "customer:manage"):
        return
    scope = widest_data_scope(collect_data_scopes(user))
    if scope == "company":
        return
    if customer.owner_id == user.id or customer.creator_id == user.id:
        return
    if scope == "department" and user.department_id and customer.department_id == user.department_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该客户")


def assert_can_edit(user: User, customer: Customer) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes or user_can(user, "customer:manage"):
        return
    if customer.owner_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权编辑该客户")


def create_customer(db: Session, user: User, payload: CustomerCreate) -> Customer:
    if payload.status not in CUSTOMER_STATUSES:
        raise HTTPException(status_code=400, detail="无效的客户状态")
    customer = Customer(
        name=payload.name.strip(),
        short_name=payload.short_name,
        contact_name=payload.contact_name,
        phone=payload.phone,
        email=payload.email,
        industry=payload.industry,
        company_size=payload.company_size,
        address=payload.address,
        source=payload.source or "manual",
        status=payload.status,
        owner_id=user.id,
        creator_id=user.id,
        department_id=user.department_id,
        remark=payload.remark,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return enrich_customer(db, customer)


def update_customer(db: Session, user: User, customer_id: int, payload: CustomerUpdate) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    assert_can_view(user, customer)
    assert_can_edit(user, customer)

    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in CUSTOMER_STATUSES:
        raise HTTPException(status_code=400, detail="无效的客户状态")
    if "owner_id" in data and data["owner_id"] is not None:
        if not user_can(user, "customer:manage") and "admin" not in {r.code for r in user.roles}:
            raise HTTPException(status_code=403, detail="无权变更负责人")
        owner = db.query(User).filter(User.id == data["owner_id"]).first()
        if not owner:
            raise HTTPException(status_code=400, detail="负责人不存在")
        customer.department_id = owner.department_id or customer.department_id

    for k, v in data.items():
        setattr(customer, k, v)

    db.commit()
    db.refresh(customer)
    return enrich_customer(db, customer)


def list_customers(
    db: Session,
    user: User,
    *,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    scope_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Customer]]:
    """
    scope_filter:
      - mine: 我负责的
      - all: 按数据范围
    """
    q = db.query(Customer)
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    scope = widest_data_scope(collect_data_scopes(user)) if not is_admin else "company"

    if scope_filter == "mine":
        q = q.filter(Customer.owner_id == user.id)
    else:
        if not is_admin and scope == "personal":
            q = q.filter(or_(Customer.owner_id == user.id, Customer.creator_id == user.id))
        elif not is_admin and scope == "department" and user.department_id:
            q = q.filter(
                or_(
                    Customer.department_id == user.department_id,
                    Customer.owner_id == user.id,
                    Customer.creator_id == user.id,
                )
            )

    if status:
        q = q.filter(Customer.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                Customer.name.ilike(like),
                Customer.short_name.ilike(like),
                Customer.contact_name.ilike(like),
                Customer.phone.ilike(like),
            )
        )

    total = q.count()
    items = (
        q.order_by(Customer.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, [enrich_customer(db, x) for x in items]


def get_customer_detail(db: Session, user: User, customer_id: int) -> Customer:
    customer = (
        db.query(Customer)
        .options(joinedload(Customer.follow_ups))
        .filter(Customer.id == customer_id)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    assert_can_view(user, customer)
    customer.follow_ups = sorted(customer.follow_ups or [], key=lambda x: x.id, reverse=True)
    for fu in customer.follow_ups:
        fu.user_name = _user_name(db, fu.user_id)  # type: ignore[attr-defined]
    return enrich_customer(db, customer)


def add_follow_up(
    db: Session, user: User, customer_id: int, payload: CustomerFollowUpCreate
) -> CustomerFollowUp:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    assert_can_edit(user, customer)

    follow_at = payload.follow_at or _now()
    fu = CustomerFollowUp(
        customer_id=customer.id,
        user_id=user.id,
        follow_at=follow_at,
        method=payload.method,
        content=payload.content,
        next_follow_at=payload.next_follow_at,
    )
    db.add(fu)
    customer.last_followed_at = follow_at
    db.commit()
    db.refresh(fu)
    fu.user_name = _user_name(db, fu.user_id)  # type: ignore[attr-defined]
    return fu


def customer_stats(db: Session, user: User) -> dict:
    def _count(*, status: Optional[str] = None, scope_filter: Optional[str] = None) -> int:
        total, _ = list_customers(
            db, user, status=status, scope_filter=scope_filter, page=1, page_size=1
        )
        return total

    return {
        "total": _count(),
        "potential": _count(status=CUSTOMER_STATUS_POTENTIAL),
        "active": _count(status=CUSTOMER_STATUS_ACTIVE),
        "paused": _count(status=CUSTOMER_STATUS_PAUSED),
        "terminated": _count(status=CUSTOMER_STATUS_TERMINATED),
        "mine": _count(scope_filter="mine"),
    }
