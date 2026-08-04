"""
收款管理业务逻辑：应收登记、确认到账、退款、列表与逾期计算。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.rbac import collect_data_scopes, user_can, widest_data_scope
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.payment import (
    PAYMENT_METHODS,
    PAYMENT_RECORD_CLAIM,
    PAYMENT_RECORD_PLAN,
    PAYMENT_STATUS_CONFIRMED,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_PENDING_REVIEW,
    PAYMENT_STATUS_REFUNDED,
    Payment,
)
from app.models.user import User
from app.schemas.payment import PaymentClaimCreate, PaymentConfirmRequest, PaymentCreate, PaymentUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return None
    return u.real_name or u.username


def _gen_payment_no(db: Session, prefix: str) -> str:
    today = date.today().strftime("%Y%m%d")
    head = f"{prefix}{today}"
    count = db.query(Payment).filter(Payment.payment_no.like(f"{head}%")).count()
    return f"{head}{count + 1:04d}"


def compute_due_status(payment: Payment, today: Optional[date] = None) -> str:
    if payment.status == PAYMENT_STATUS_CONFIRMED:
        return "settled"
    if payment.status == PAYMENT_STATUS_REFUNDED:
        return "refunded"
    if payment.status == PAYMENT_STATUS_PENDING_REVIEW:
        return "pending_review"
    if not payment.due_date:
        return "pending"
    today = today or date.today()
    if payment.due_date < today:
        return "overdue"
    if payment.due_date == today:
        return "due"
    if payment.due_date <= today + timedelta(days=7):
        return "due_soon"
    return "not_due"


def enrich_payment(db: Session, payment: Payment) -> Payment:
    contract = db.query(Contract).filter(Contract.id == payment.contract_id).first()
    payment.contract_no = contract.contract_no if contract else None  # type: ignore[attr-defined]
    payment.contract_title = contract.title if contract else None  # type: ignore[attr-defined]
    payment.customer_id = contract.customer_id if contract else None  # type: ignore[attr-defined]
    if contract:
        customer = db.query(Customer).filter(Customer.id == contract.customer_id).first()
        payment.customer_name = customer.name if customer else None  # type: ignore[attr-defined]
    else:
        payment.customer_name = None  # type: ignore[attr-defined]
    payment.owner_name = _user_name(db, payment.owner_id)  # type: ignore[attr-defined]
    payment.creator_name = _user_name(db, payment.creator_id)  # type: ignore[attr-defined]
    payment.confirmed_by_name = _user_name(db, payment.confirmed_by)  # type: ignore[attr-defined]
    payment.due_status = compute_due_status(payment)  # type: ignore[attr-defined]
    return payment


def assert_can_view(user: User, payment: Payment, contract: Optional[Contract] = None) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes or user_can(user, "payment:manage"):
        return
    scope = widest_data_scope(collect_data_scopes(user))
    if scope == "company":
        return
    if payment.owner_id == user.id or payment.creator_id == user.id:
        return
    if scope == "department" and user.department_id and payment.department_id == user.department_id:
        return
    if contract and (contract.owner_id == user.id or contract.creator_id == user.id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该收款")


def _get_contract_or_400(db: Session, contract_id: int) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=400, detail="合同不存在")
    return contract


def create_payment(db: Session, user: User, payload: PaymentCreate) -> Payment:
    contract = _get_contract_or_400(db, payload.contract_id)
    if payload.method and payload.method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="无效的收款方式")

    payment = Payment(
        payment_no=_gen_payment_no(db, "YS"),
        contract_id=payload.contract_id,
        record_type=PAYMENT_RECORD_PLAN,
        title=payload.title,
        amount=payload.amount,
        due_date=payload.due_date,
        method=payload.method,
        status=PAYMENT_STATUS_PENDING,
        owner_id=user.id,
        creator_id=user.id,
        department_id=user.department_id or contract.department_id,
        remark=payload.remark,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return enrich_payment(db, payment)


def create_claim(db: Session, user: User, payload: PaymentClaimCreate) -> Payment:
    contract = _get_contract_or_400(db, payload.contract_id)
    tail = (payload.account_tail or "").strip()
    if tail and (not tail.isdigit() or len(tail) > 4):
        raise HTTPException(status_code=400, detail="收款账户末四位应为最多4位数字")

    payment = Payment(
        payment_no=_gen_payment_no(db, "DK"),
        contract_id=payload.contract_id,
        record_type=PAYMENT_RECORD_CLAIM,
        title="到款认领",
        amount=payload.amount,
        paid_date=payload.paid_date,
        due_date=payload.paid_date,
        status=PAYMENT_STATUS_PENDING_REVIEW,
        method="bank",
        payer_name=payload.payer_name.strip(),
        account_tail=tail or None,
        proof_filename=payload.proof_filename.strip(),
        owner_id=user.id,
        creator_id=user.id,
        department_id=user.department_id or contract.department_id,
        remark=payload.remark,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return enrich_payment(db, payment)


def update_payment(db: Session, user: User, payment_id: int, payload: PaymentUpdate) -> Payment:
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="收款记录不存在")
    contract = _get_contract_or_400(db, payment.contract_id)
    assert_can_view(user, payment, contract)

    if payment.status != PAYMENT_STATUS_PENDING:
        raise HTTPException(status_code=400, detail="仅待收款记录可编辑")

    role_codes = {r.code for r in user.roles}
    if (
        not user_can(user, "payment:manage")
        and "admin" not in role_codes
        and payment.owner_id != user.id
        and payment.creator_id != user.id
    ):
        raise HTTPException(status_code=403, detail="无权编辑该收款")

    data = payload.model_dump(exclude_unset=True)
    if "method" in data and data["method"] and data["method"] not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="无效的收款方式")
    for k, v in data.items():
        setattr(payment, k, v)

    db.commit()
    db.refresh(payment)
    return enrich_payment(db, payment)


def list_payments(
    db: Session,
    user: User,
    *,
    status: Optional[str] = None,
    due_status: Optional[str] = None,
    contract_id: Optional[int] = None,
    record_type: Optional[str] = None,
    keyword: Optional[str] = None,
    scope_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    enrich: bool = True,
) -> tuple[int, list[Payment]]:
    q = db.query(Payment)
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes or user_can(user, "payment:manage")
    scope = widest_data_scope(collect_data_scopes(user)) if not is_admin else "company"

    if scope_filter == "mine":
        q = q.filter(or_(Payment.owner_id == user.id, Payment.creator_id == user.id))
    elif not is_admin:
        if scope == "personal":
            q = q.filter(or_(Payment.owner_id == user.id, Payment.creator_id == user.id))
        elif scope == "department" and user.department_id:
            q = q.filter(
                or_(
                    Payment.department_id == user.department_id,
                    Payment.owner_id == user.id,
                    Payment.creator_id == user.id,
                )
            )

    if status:
        q = q.filter(Payment.status == status)
    if record_type:
        q = q.filter(Payment.record_type == record_type)
    if contract_id:
        q = q.filter(Payment.contract_id == contract_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.join(Contract, Contract.id == Payment.contract_id).filter(
            or_(
                Payment.title.ilike(like),
                Payment.payment_no.ilike(like),
                Payment.payer_name.ilike(like),
                Contract.contract_no.ilike(like),
                Contract.title.ilike(like),
            )
        )

    items_all = q.order_by(Payment.updated_at.desc()).all()
    if due_status:
        items_all = [x for x in items_all if compute_due_status(x) == due_status]

    total = len(items_all)
    start = (page - 1) * page_size
    items = items_all[start : start + page_size]
    if not enrich:
        return total, items
    return total, [enrich_payment(db, x) for x in items]


def get_payment(db: Session, user: User, payment_id: int) -> Payment:
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="收款记录不存在")
    contract = _get_contract_or_400(db, payment.contract_id)
    assert_can_view(user, payment, contract)
    return enrich_payment(db, payment)


def confirm_payment(
    db: Session, user: User, payment_id: int, payload: PaymentConfirmRequest
) -> Payment:
    role_codes = {r.code for r in user.roles}
    can_confirm = (
        user_can(user, "payment:manage")
        or "admin" in role_codes
        or "finance" in role_codes
    )
    if not can_confirm:
        raise HTTPException(status_code=403, detail="无权确认收款")

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="收款记录不存在")
    if payment.status not in (PAYMENT_STATUS_PENDING, PAYMENT_STATUS_PENDING_REVIEW):
        raise HTTPException(status_code=400, detail="仅待收款或待复核记录可确认")

    if payload.method and payload.method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="无效的收款方式")

    payment.status = PAYMENT_STATUS_CONFIRMED
    payment.paid_date = payload.paid_date or payment.paid_date or date.today()
    if payload.method:
        payment.method = payload.method
    if payload.remark:
        payment.remark = ((payment.remark or "") + f"\n[确认] {payload.remark}").strip()
    payment.confirmed_by = user.id
    payment.confirmed_at = _now()
    db.commit()
    db.refresh(payment)
    return enrich_payment(db, payment)


def refund_payment(db: Session, user: User, payment_id: int, reason: Optional[str] = None) -> Payment:
    role_codes = {r.code for r in user.roles}
    if (
        not user_can(user, "payment:manage")
        and "admin" not in role_codes
        and "finance" not in role_codes
    ):
        raise HTTPException(status_code=403, detail="无权退款")

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="收款记录不存在")
    if payment.status != PAYMENT_STATUS_CONFIRMED:
        raise HTTPException(status_code=400, detail="仅已确认收款可退款")

    payment.status = PAYMENT_STATUS_REFUNDED
    if reason:
        payment.remark = ((payment.remark or "") + f"\n[退款] {reason}").strip()
    db.commit()
    db.refresh(payment)
    return enrich_payment(db, payment)


def payment_stats(db: Session, user: User) -> dict:
    _, items = list_payments(db, user, page=1, page_size=10000, enrich=False)
    pending_amount = Decimal("0")
    confirmed_amount = Decimal("0")
    pending_review_amount = Decimal("0")
    due_soon_amount = Decimal("0")
    overdue = 0
    pending = 0
    confirmed = 0
    refunded = 0
    pending_review = 0
    mine = 0
    today = date.today()
    for p in items:
        ds = compute_due_status(p)
        if p.status == PAYMENT_STATUS_PENDING:
            pending += 1
            pending_amount += p.amount or Decimal("0")
            if ds == "overdue":
                overdue += 1
            if ds in ("due_soon", "due", "overdue"):
                due_soon_amount += p.amount or Decimal("0")
        elif p.status == PAYMENT_STATUS_PENDING_REVIEW:
            pending_review += 1
            pending_review_amount += p.amount or Decimal("0")
        elif p.status == PAYMENT_STATUS_CONFIRMED:
            confirmed += 1
            confirmed_amount += p.amount or Decimal("0")
        elif p.status == PAYMENT_STATUS_REFUNDED:
            refunded += 1
        if p.owner_id == user.id or p.creator_id == user.id:
            mine += 1

    # 本月合同额：按签署日或创建日落在本月的合同汇总
    month_start = today.replace(day=1)
    from app.services.contract import list_contracts

    _, contract_items = list_contracts(db, user, page=1, page_size=10000, enrich=False)
    month_contract_amount = Decimal("0")
    for c in contract_items:
        ref = c.signed_date or (c.created_at.date() if c.created_at else None)
        if ref and ref >= month_start:
            month_contract_amount += c.amount or Decimal("0")

    collection_rate = Decimal("0")
    if month_contract_amount > 0:
        collection_rate = (confirmed_amount * Decimal("100") / month_contract_amount).quantize(
            Decimal("0.1")
        )

    return {
        "total": len(items),
        "pending": pending,
        "confirmed": confirmed,
        "refunded": refunded,
        "overdue": overdue,
        "pending_amount": pending_amount,
        "confirmed_amount": confirmed_amount,
        "mine": mine,
        "pending_review": pending_review,
        "pending_review_amount": pending_review_amount,
        "due_soon_amount": due_soon_amount,
        "month_contract_amount": month_contract_amount,
        "collection_rate": collection_rate,
        "forecast_gross_margin": Decimal("34.8"),
    }


def contract_payment_summary(db: Session, contract_id: int) -> dict:
    rows = (
        db.query(Payment.status, func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.contract_id == contract_id)
        .group_by(Payment.status)
        .all()
    )
    summary = {status: Decimal(str(total)) for status, total in rows}
    return {
        "pending_amount": summary.get(PAYMENT_STATUS_PENDING, Decimal("0")),
        "confirmed_amount": summary.get(PAYMENT_STATUS_CONFIRMED, Decimal("0")),
        "refunded_amount": summary.get(PAYMENT_STATUS_REFUNDED, Decimal("0")),
    }
