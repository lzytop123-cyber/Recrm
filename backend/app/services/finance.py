"""合同财务闭环服务。

余额一律从事实表汇总，不保存可漂移的冗余余额。涉及金额占用的操作锁定主记录，
并用业务幂等键防止页面刷新、网络重试造成重复入账。
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.rbac import resolve_data_scope, user_dept_scope
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.finance import (
    ALLOCATION_STATUS_ACTIVE,
    ALLOCATION_STATUS_PENDING,
    ALLOCATION_STATUS_REJECTED,
    ALLOCATION_STATUS_REVERSED,
    RECEIPT_STATUS_CONFIRMED,
    RECEIPT_STATUS_PENDING_REVIEW,
    RECEIPT_STATUS_REJECTED,
    RECEIVABLE_STATUS_CANCELLED,
    RECEIVABLE_STATUS_PAID,
    RECEIVABLE_STATUS_PARTIALLY_PAID,
    RECEIVABLE_STATUS_UNPAID,
    REFUND_STATUS_CANCELLED,
    REFUND_STATUS_CONFIRMED,
    REFUND_STATUS_PENDING,
    REFUND_STATUS_REJECTED,
    Receipt,
    ReceiptAllocation,
    ReceivablePlan,
    Refund,
)
from app.models.user import User
from app.schemas.finance import (
    AllocationCreate,
    AllocationReverseRequest,
    AllocationReviewRequest,
    ReceiptCreate,
    ReceiptReviewRequest,
    ReceivableCancelRequest,
    ReceivableCreate,
    ReceivableUpdate,
    RefundCreate,
    RefundReviewRequest,
)
from app.services.contract import assert_can_view

ZERO = Decimal("0.00")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _number(prefix: str) -> str:
    return f"{prefix}{date.today():%Y%m%d}{uuid4().hex[:10].upper()}"


def _user_name(db: Session, user_id: int | None) -> str | None:
    if not user_id:
        return None
    item = db.query(User).filter(User.id == user_id).first()
    return (item.real_name or item.username) if item else None


def _apply_contract_scope(query, user: User):
    role_codes = {role.code for role in user.roles}
    if "admin" in role_codes:
        return query
    scope = resolve_data_scope(user, "contract")
    if scope == "company":
        return query
    if scope == "department" and user.department_id:
        dept_ids = user_dept_scope(user)
        return query.filter(
            or_(
                Contract.department_id.in_(dept_ids) if dept_ids else False,
                Contract.owner_id == user.id,
                Contract.creator_id == user.id,
            )
        )
    return query.filter(or_(Contract.owner_id == user.id, Contract.creator_id == user.id))


def _contract(db: Session, user: User, contract_id: int, *, lock: bool = False) -> Contract:
    query = db.query(Contract).filter(Contract.id == contract_id)
    if lock:
        query = query.with_for_update()
    contract = query.first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view(user, contract)
    return contract


def _receivable(db: Session, user: User, item_id: int, *, lock: bool = False) -> ReceivablePlan:
    query = db.query(ReceivablePlan).filter(ReceivablePlan.id == item_id)
    if lock:
        query = query.with_for_update()
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="应收计划不存在")
    _contract(db, user, item.contract_id)
    return item


def _receipt(db: Session, user: User, item_id: int, *, lock: bool = False) -> Receipt:
    query = db.query(Receipt).filter(Receipt.id == item_id)
    if lock:
        query = query.with_for_update()
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="收款记录不存在")
    _contract(db, user, item.contract_id)
    return item


def _allocation(db: Session, user: User, item_id: int, *, lock: bool = False) -> ReceiptAllocation:
    query = db.query(ReceiptAllocation).filter(ReceiptAllocation.id == item_id)
    if lock:
        query = query.with_for_update()
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="核销记录不存在")
    _receipt(db, user, item.receipt_id)
    return item


def _refund(db: Session, user: User, item_id: int, *, lock: bool = False) -> Refund:
    query = db.query(Refund).filter(Refund.id == item_id)
    if lock:
        query = query.with_for_update()
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="退款记录不存在")
    _receipt(db, user, item.receipt_id)
    return item


def _allocation_sum(
    db: Session,
    *,
    receipt_id: int | None = None,
    receivable_plan_id: int | None = None,
    statuses: list[str],
) -> Decimal:
    query = db.query(func.coalesce(func.sum(ReceiptAllocation.amount), 0)).filter(
        ReceiptAllocation.status.in_(statuses)
    )
    if receipt_id is not None:
        query = query.filter(ReceiptAllocation.receipt_id == receipt_id)
    if receivable_plan_id is not None:
        query = query.filter(ReceiptAllocation.receivable_plan_id == receivable_plan_id)
    return _money(query.scalar())


def _allocated_to_receivable(db: Session, item_id: int) -> Decimal:
    return _allocation_sum(
        db, receivable_plan_id=item_id, statuses=[ALLOCATION_STATUS_ACTIVE]
    )


def _reserved_to_receivable(db: Session, item_id: int) -> Decimal:
    return _allocation_sum(
        db,
        receivable_plan_id=item_id,
        statuses=[ALLOCATION_STATUS_ACTIVE, ALLOCATION_STATUS_PENDING],
    )


def _allocated_from_receipt(db: Session, item_id: int) -> Decimal:
    return _allocation_sum(db, receipt_id=item_id, statuses=[ALLOCATION_STATUS_ACTIVE])


def _pending_from_receipt(db: Session, item_id: int) -> Decimal:
    return _allocation_sum(db, receipt_id=item_id, statuses=[ALLOCATION_STATUS_PENDING])


def _reserved_from_receipt(db: Session, item_id: int) -> Decimal:
    return _allocation_sum(
        db,
        receipt_id=item_id,
        statuses=[ALLOCATION_STATUS_ACTIVE, ALLOCATION_STATUS_PENDING],
    )


def _refund_amount(db: Session, item_id: int, *, include_pending: bool) -> Decimal:
    statuses = [REFUND_STATUS_CONFIRMED]
    if include_pending:
        statuses.append(REFUND_STATUS_PENDING)
    value = (
        db.query(func.coalesce(func.sum(Refund.amount), 0))
        .filter(Refund.receipt_id == item_id, Refund.status.in_(statuses))
        .scalar()
    )
    return _money(value)


def _sync_receivable_status(db: Session, item: ReceivablePlan) -> None:
    if item.status == RECEIVABLE_STATUS_CANCELLED:
        return
    allocated = _allocated_to_receivable(db, item.id)
    if allocated >= _money(item.amount):
        item.status = RECEIVABLE_STATUS_PAID
    elif allocated > ZERO:
        item.status = RECEIVABLE_STATUS_PARTIALLY_PAID
    else:
        item.status = RECEIVABLE_STATUS_UNPAID
    item.version += 1


def enrich_receivable(db: Session, item: ReceivablePlan) -> ReceivablePlan:
    allocated = _allocated_to_receivable(db, item.id)
    reserved = _reserved_to_receivable(db, item.id)
    outstanding = max(ZERO, _money(item.amount) - reserved)
    if item.status == RECEIVABLE_STATUS_CANCELLED:
        effective = RECEIVABLE_STATUS_CANCELLED
    elif allocated >= _money(item.amount):
        effective = RECEIVABLE_STATUS_PAID
    elif allocated > ZERO:
        effective = RECEIVABLE_STATUS_PARTIALLY_PAID
    elif item.due_date < date.today():
        effective = "overdue"
    else:
        effective = RECEIVABLE_STATUS_UNPAID
    item.allocated_amount = allocated  # type: ignore[attr-defined]
    item.outstanding_amount = outstanding  # type: ignore[attr-defined]
    item.effective_status = effective  # type: ignore[attr-defined]
    contract = db.query(Contract).filter(Contract.id == item.contract_id).first()
    customer = (
        db.query(Customer).filter(Customer.id == contract.customer_id).first()
        if contract
        else None
    )
    item.contract_no = contract.contract_no if contract else None  # type: ignore[attr-defined]
    item.contract_title = contract.title if contract else None  # type: ignore[attr-defined]
    item.customer_name = customer.name if customer else None  # type: ignore[attr-defined]
    item.owner_name = _user_name(db, contract.owner_id if contract else None)  # type: ignore[attr-defined]
    return item


def enrich_receipt(db: Session, item: Receipt) -> Receipt:
    allocated = _allocated_from_receipt(db, item.id)
    pending = _pending_from_receipt(db, item.id)
    refunded = _refund_amount(db, item.id, include_pending=False)
    reserved_refund = _refund_amount(db, item.id, include_pending=True)
    item.allocated_amount = allocated  # type: ignore[attr-defined]
    item.pending_allocation_amount = pending  # type: ignore[attr-defined]
    item.refunded_amount = refunded  # type: ignore[attr-defined]
    item.available_amount = max(  # type: ignore[attr-defined]
        ZERO, _money(item.amount) - allocated - pending - reserved_refund
    )
    contract = db.query(Contract).filter(Contract.id == item.contract_id).first()
    customer = (
        db.query(Customer).filter(Customer.id == contract.customer_id).first()
        if contract
        else None
    )
    item.contract_no = contract.contract_no if contract else None  # type: ignore[attr-defined]
    item.contract_title = contract.title if contract else None  # type: ignore[attr-defined]
    item.customer_name = customer.name if customer else None  # type: ignore[attr-defined]
    item.submitted_by_name = _user_name(db, item.submitted_by)  # type: ignore[attr-defined]
    item.confirmed_by_name = _user_name(db, item.confirmed_by)  # type: ignore[attr-defined]
    return item


def create_receivable(
    db: Session, user: User, contract_id: int, payload: ReceivableCreate
) -> ReceivablePlan:
    contract = _contract(db, user, contract_id, lock=True)
    existing_total = _money(
        db.query(func.coalesce(func.sum(ReceivablePlan.amount), 0))
        .filter(
            ReceivablePlan.contract_id == contract_id,
            ReceivablePlan.status != RECEIVABLE_STATUS_CANCELLED,
        )
        .scalar()
    )
    if existing_total + _money(payload.amount) > _money(contract.amount):
        raise HTTPException(status_code=409, detail="应收计划总额不能超过合同金额")
    sequence_no = payload.sequence_no
    if sequence_no is None:
        sequence_no = (
            db.query(func.coalesce(func.max(ReceivablePlan.sequence_no), 0))
            .filter(ReceivablePlan.contract_id == contract_id)
            .scalar()
            + 1
        )
    duplicate = db.query(ReceivablePlan.id).filter(
        ReceivablePlan.contract_id == contract_id,
        ReceivablePlan.sequence_no == sequence_no,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="该合同的应收期次已存在")
    item = ReceivablePlan(
        contract_id=contract_id,
        sequence_no=sequence_no,
        title=payload.title.strip(),
        amount=payload.amount,
        due_date=payload.due_date,
        currency=contract.currency,
        created_by=user.id,
        department_id=contract.department_id,
        remark=payload.remark,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return enrich_receivable(db, item)


def list_receivables(db: Session, user: User, contract_id: int) -> list[ReceivablePlan]:
    _contract(db, user, contract_id)
    items = (
        db.query(ReceivablePlan)
        .filter(ReceivablePlan.contract_id == contract_id)
        .order_by(ReceivablePlan.sequence_no.asc())
        .all()
    )
    return [enrich_receivable(db, item) for item in items]


def list_receivables_workbench(
    db: Session,
    user: User,
    *,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[ReceivablePlan]]:
    query = db.query(ReceivablePlan).join(
        Contract, Contract.id == ReceivablePlan.contract_id
    ).outerjoin(Customer, Customer.id == Contract.customer_id)
    query = _apply_contract_scope(query, user)
    if status:
        if status == "overdue":
            query = query.filter(
                ReceivablePlan.status == RECEIVABLE_STATUS_UNPAID,
                ReceivablePlan.due_date < date.today(),
            )
        else:
            query = query.filter(ReceivablePlan.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                ReceivablePlan.title.ilike(like),
                Contract.contract_no.ilike(like),
                Contract.title.ilike(like),
                Customer.name.ilike(like),
            )
        )
    total = query.count()
    items = (
        query.order_by(ReceivablePlan.due_date.asc(), ReceivablePlan.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, [enrich_receivable(db, item) for item in items]


def get_receivable(db: Session, user: User, item_id: int) -> ReceivablePlan:
    return enrich_receivable(db, _receivable(db, user, item_id))


def update_receivable(
    db: Session, user: User, item_id: int, payload: ReceivableUpdate
) -> ReceivablePlan:
    item = _receivable(db, user, item_id, lock=True)
    if item.version != payload.version:
        raise HTTPException(status_code=409, detail="应收计划已被其他操作修改，请刷新后重试")
    if item.status == RECEIVABLE_STATUS_CANCELLED:
        raise HTTPException(status_code=409, detail="已取消的应收计划不能编辑")
    allocated = _allocated_to_receivable(db, item.id)
    new_amount = _money(payload.amount if payload.amount is not None else item.amount)
    if new_amount < allocated:
        raise HTTPException(status_code=409, detail="应收金额不能小于已核销金额")
    other_total = _money(
        db.query(func.coalesce(func.sum(ReceivablePlan.amount), 0))
        .filter(
            ReceivablePlan.contract_id == item.contract_id,
            ReceivablePlan.id != item.id,
            ReceivablePlan.status != RECEIVABLE_STATUS_CANCELLED,
        )
        .scalar()
    )
    contract = _contract(db, user, item.contract_id, lock=True)
    if other_total + new_amount > _money(contract.amount):
        raise HTTPException(status_code=409, detail="应收计划总额不能超过合同金额")
    for field, value in payload.model_dump(exclude_unset=True, exclude={"version"}).items():
        setattr(item, field, value.strip() if field == "title" else value)
    item.version += 1
    db.commit()
    db.refresh(item)
    return enrich_receivable(db, item)


def cancel_receivable(
    db: Session, user: User, item_id: int, payload: ReceivableCancelRequest
) -> ReceivablePlan:
    item = _receivable(db, user, item_id, lock=True)
    if item.version != payload.version:
        raise HTTPException(status_code=409, detail="应收计划已被其他操作修改，请刷新后重试")
    if item.status == RECEIVABLE_STATUS_CANCELLED:
        return enrich_receivable(db, item)
    if _allocated_to_receivable(db, item.id) > ZERO:
        raise HTTPException(status_code=409, detail="已有核销的应收计划不能取消，请先冲销")
    item.status = RECEIVABLE_STATUS_CANCELLED
    item.remark = ((item.remark or "") + f"\n[取消] {payload.reason.strip()}").strip()
    item.version += 1
    db.commit()
    db.refresh(item)
    return enrich_receivable(db, item)


def create_receipt(db: Session, user: User, payload: ReceiptCreate) -> Receipt:
    if payload.idempotency_key:
        existing = db.query(Receipt).filter(Receipt.idempotency_key == payload.idempotency_key).first()
        if existing:
            _contract(db, user, existing.contract_id)
            return enrich_receipt(db, existing)
    contract = _contract(db, user, payload.contract_id, lock=True)
    item = Receipt(
        receipt_no=_number("SK"),
        contract_id=payload.contract_id,
        amount=payload.amount,
        paid_date=payload.paid_date,
        payer_name=payload.payer_name.strip(),
        payment_method=payload.payment_method,
        bank_reference=payload.bank_reference,
        proof_filename=payload.proof_filename,
        submitted_by=user.id,
        department_id=contract.department_id,
        idempotency_key=payload.idempotency_key,
        remark=payload.remark,
    )
    db.add(item)
    db.flush()

    # AP-16 到账确认：财务确认到账
    from app.services import approval_flow

    if approval_flow.select_rule(db, "receipt", {}) is not None:
        approval_flow.start_instance(
            db,
            biz_type="receipt",
            biz_id=item.id,
            initiator=user,
            title=f"到账确认 {item.receipt_no} · ¥{item.amount}",
            summary=f"{item.payer_name} · {_contract_brief_no(db, item.contract_id)}",
            amount=_money(item.amount),
            department_id=item.department_id,
            deep_link=(f"/contracts/{item.contract_id}" if item.contract_id else "/approvals"),
            commit=False,
        )
    db.commit()
    db.refresh(item)
    return enrich_receipt(db, item)


def _contract_brief_no(db: Session, contract_id) -> str:
    if not contract_id:
        return "—"
    c = db.query(Contract).filter(Contract.id == contract_id).first()
    return (c.contract_no if c else None) or f"#{contract_id}"


def on_receipt_flow_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-16 终审回调：通过则复用 review_receipt(置确认到账)，驳回/撤回置驳回。"""
    from app.services import approval_flow

    item = db.query(Receipt).filter(Receipt.id == instance.biz_id).first()
    if not item or item.status != RECEIPT_STATUS_PENDING_REVIEW:
        return
    if withdrawn:
        item.status = RECEIPT_STATUS_REJECTED
        item.version += 1
        return
    actor = approval_flow.last_actor(db, instance)
    if actor is None:
        return
    review_receipt(
        db, actor, item.id,
        ReceiptReviewRequest(remark=instance.reject_reason if not approved else None, version=item.version),
        approve=approved,
    )


def list_receipts(
    db: Session,
    user: User,
    *,
    contract_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Receipt]]:
    query = db.query(Receipt).join(Contract, Contract.id == Receipt.contract_id).outerjoin(
        Customer, Customer.id == Contract.customer_id
    )
    query = _apply_contract_scope(query, user)
    if contract_id:
        query = query.filter(Receipt.contract_id == contract_id)
    if status:
        query = query.filter(Receipt.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Receipt.receipt_no.ilike(like),
                Receipt.payer_name.ilike(like),
                Contract.contract_no.ilike(like),
                Contract.title.ilike(like),
                Customer.name.ilike(like),
            )
        )
    total = query.count()
    items = (
        query.order_by(Receipt.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, [enrich_receipt(db, item) for item in items]


def get_receipt(db: Session, user: User, item_id: int) -> Receipt:
    return enrich_receipt(db, _receipt(db, user, item_id))


def review_receipt(
    db: Session, user: User, item_id: int, payload: ReceiptReviewRequest, *, approve: bool
) -> Receipt:
    item = _receipt(db, user, item_id, lock=True)
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "receipt", item.id) is not None:
        raise HTTPException(status_code=409, detail="该到账已进入审批流程，请在审批中心处理")
    if item.version != payload.version:
        raise HTTPException(status_code=409, detail="收款记录已被其他操作修改，请刷新后重试")
    if item.status != RECEIPT_STATUS_PENDING_REVIEW:
        raise HTTPException(status_code=409, detail="仅待复核收款可以审批")
    item.status = RECEIPT_STATUS_CONFIRMED if approve else RECEIPT_STATUS_REJECTED
    item.confirmed_by = user.id
    item.confirmed_at = _now()
    if payload.remark:
        item.remark = ((item.remark or "") + f"\n[复核] {payload.remark}").strip()
    item.version += 1
    db.commit()
    db.refresh(item)
    return enrich_receipt(db, item)


def create_allocation(
    db: Session, user: User, receipt_id: int, payload: AllocationCreate
) -> ReceiptAllocation:
    """提交核销申请，进入待审批；通过后才计入应收已收。"""
    if payload.idempotency_key:
        existing = (
            db.query(ReceiptAllocation)
            .filter(
                ReceiptAllocation.receipt_id == receipt_id,
                ReceiptAllocation.idempotency_key == payload.idempotency_key,
            )
            .first()
        )
        if existing:
            _receipt(db, user, receipt_id)
            return existing
    receipt = _receipt(db, user, receipt_id, lock=True)
    receivable = _receivable(db, user, payload.receivable_plan_id, lock=True)
    if receipt.status != RECEIPT_STATUS_CONFIRMED:
        raise HTTPException(status_code=409, detail="仅已确认到账的收款可以核销")
    if receivable.status == RECEIVABLE_STATUS_CANCELLED:
        raise HTTPException(status_code=409, detail="已取消的应收计划不能核销")
    if receipt.contract_id != receivable.contract_id:
        raise HTTPException(status_code=409, detail="收款与应收计划不属于同一合同")
    amount = _money(payload.amount)
    receipt_available = (
        _money(receipt.amount)
        - _reserved_from_receipt(db, receipt.id)
        - _refund_amount(db, receipt.id, include_pending=True)
    )
    receivable_outstanding = _money(receivable.amount) - _reserved_to_receivable(
        db, receivable.id
    )
    if amount > receipt_available:
        raise HTTPException(status_code=409, detail="核销金额超过收款可用余额")
    if amount > receivable_outstanding:
        raise HTTPException(status_code=409, detail="核销金额超过应收未收余额")
    item = ReceiptAllocation(
        receipt_id=receipt.id,
        receivable_plan_id=receivable.id,
        amount=amount,
        status=ALLOCATION_STATUS_PENDING,
        allocated_by=user.id,
        idempotency_key=payload.idempotency_key,
    )
    db.add(item)
    db.flush()
    receipt.version += 1

    # AP-17 收款金额差异：核销额≠应收计划额时走分级审批
    from app.services import approval_flow

    plan_amount = _money(receivable.amount)
    if amount != plan_amount and approval_flow.select_rule(db, "receipt_diff", {}) is not None:
        diff = abs(amount - plan_amount)
        approval_flow.start_instance(
            db,
            biz_type="receipt_diff",
            biz_id=item.id,
            initiator=user,
            title=f"收款差异核销 {receipt.receipt_no} → {receivable.title}",
            summary=f"核销 ¥{amount}，计划 ¥{plan_amount}，差异 ¥{diff}",
            amount=diff,
            department_id=receipt.department_id,
            deep_link=_receipt_deep_link(receipt.contract_id),
            facts={"allocation_amount": str(amount), "plan_amount": str(plan_amount), "diff": str(diff)},
            commit=False,
        )

    db.commit()
    db.refresh(item)
    return item


def _receipt_deep_link(contract_id: int | None) -> str:
    return f"/contracts/{contract_id}" if contract_id else "/sales?tab=contracts"


def on_receipt_diff_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-17 终审回调：通过则生效核销，驳回/撤回置驳回。"""
    from app.services import approval_flow

    item = db.query(ReceiptAllocation).filter(ReceiptAllocation.id == instance.biz_id).first()
    if not item or item.status != ALLOCATION_STATUS_PENDING:
        return
    if withdrawn:
        item.status = ALLOCATION_STATUS_REJECTED
        item.review_remark = "申请人撤回"
        item.version += 1
        return
    actor = approval_flow.last_actor(db, instance)
    if actor is None:
        return
    review_allocation(
        db,
        actor,
        item.id,
        AllocationReviewRequest(
            remark=instance.reject_reason if not approved else None,
            version=item.version,
        ),
        approve=approved,
    )


def list_allocations(db: Session, user: User, receipt_id: int) -> list[ReceiptAllocation]:
    _receipt(db, user, receipt_id)
    return (
        db.query(ReceiptAllocation)
        .filter(ReceiptAllocation.receipt_id == receipt_id)
        .order_by(ReceiptAllocation.created_at.asc())
        .all()
    )


def review_allocation(
    db: Session, user: User, item_id: int, payload: AllocationReviewRequest, *, approve: bool
) -> ReceiptAllocation:
    item = _allocation(db, user, item_id, lock=True)
    if item.version != payload.version:
        raise HTTPException(status_code=409, detail="核销记录已被其他操作修改，请刷新后重试")
    if item.status != ALLOCATION_STATUS_PENDING:
        raise HTTPException(status_code=409, detail="仅待审批核销可以审批")
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "receipt_diff", item.id) is not None:
        raise HTTPException(status_code=409, detail="该核销已进入差异审批流程，请在审批中心处理")
    receipt = _receipt(db, user, item.receipt_id, lock=True)
    receivable = _receivable(db, user, item.receivable_plan_id, lock=True)
    if approve:
        receipt_others = _reserved_from_receipt(db, receipt.id) - _money(item.amount)
        receivable_others = _reserved_to_receivable(db, receivable.id) - _money(item.amount)
        receipt_available = (
            _money(receipt.amount)
            - receipt_others
            - _refund_amount(db, receipt.id, include_pending=True)
        )
        receivable_outstanding = _money(receivable.amount) - receivable_others
        if _money(item.amount) > receipt_available:
            raise HTTPException(status_code=409, detail="核销金额超过收款可用余额")
        if _money(item.amount) > receivable_outstanding:
            raise HTTPException(status_code=409, detail="核销金额超过应收未收余额")
        if receivable.status == RECEIVABLE_STATUS_CANCELLED:
            raise HTTPException(status_code=409, detail="已取消的应收计划不能核销")
        item.status = ALLOCATION_STATUS_ACTIVE
    else:
        item.status = ALLOCATION_STATUS_REJECTED
    item.approved_by = user.id
    item.approved_at = _now()
    if payload.remark:
        item.review_remark = payload.remark.strip()
    item.version += 1
    receipt.version += 1
    db.flush()
    if approve:
        _sync_receivable_status(db, receivable)
    db.commit()
    db.refresh(item)
    return item


def reverse_allocation(
    db: Session, user: User, item_id: int, payload: AllocationReverseRequest
) -> ReceiptAllocation:
    item = _allocation(db, user, item_id, lock=True)
    if item.version != payload.version:
        raise HTTPException(status_code=409, detail="核销记录已被其他操作修改，请刷新后重试")
    if item.status != ALLOCATION_STATUS_ACTIVE:
        raise HTTPException(status_code=409, detail="仅已生效核销可以冲销")
    receipt = _receipt(db, user, item.receipt_id, lock=True)
    receivable = _receivable(db, user, item.receivable_plan_id, lock=True)
    item.status = ALLOCATION_STATUS_REVERSED
    item.reversed_by = user.id
    item.reversed_at = _now()
    item.reverse_reason = payload.reason.strip()
    item.version += 1
    receipt.version += 1
    db.flush()
    _sync_receivable_status(db, receivable)
    db.commit()
    db.refresh(item)
    return item


def create_refund(db: Session, user: User, receipt_id: int, payload: RefundCreate) -> Refund:
    if payload.idempotency_key:
        existing = db.query(Refund).filter(Refund.idempotency_key == payload.idempotency_key).first()
        if existing:
            _receipt(db, user, existing.receipt_id)
            return existing
    receipt = _receipt(db, user, receipt_id, lock=True)
    if receipt.status != RECEIPT_STATUS_CONFIRMED:
        raise HTTPException(status_code=409, detail="仅已确认到账的收款可以退款")
    available = (
        _money(receipt.amount)
        - _reserved_from_receipt(db, receipt.id)
        - _refund_amount(db, receipt.id, include_pending=True)
    )
    if _money(payload.amount) > available:
        raise HTTPException(status_code=409, detail="退款金额超过未核销可用余额，请先冲销相关核销记录")
    item = Refund(
        refund_no=_number("TK"),
        receipt_id=receipt.id,
        amount=payload.amount,
        reason=payload.reason.strip(),
        requested_by=user.id,
        idempotency_key=payload.idempotency_key,
    )
    db.add(item)
    receipt.version += 1
    db.flush()

    # AP-18 退款审批流：财务专员提交 → 总经理审批 → 财务负责人执行（禁止自审）
    from app.services import approval_flow

    approval_flow.start_instance(
        db,
        biz_type="refund",
        biz_id=item.id,
        initiator=user,
        title=f"退款 {item.refund_no} · ¥{item.amount}",
        summary=item.reason,
        amount=_money(item.amount),
        department_id=receipt.department_id,
        deep_link=(f"/contracts/{receipt.contract_id}" if receipt.contract_id else "/approvals"),
        facts={"amount": _money(item.amount)},
        commit=False,
    )
    db.commit()
    db.refresh(item)
    return item


def _refund_flow_instance(db: Session, refund_id: int):
    """取退款对应的、仍在审批中的实例。"""
    from app.models.approval_flow import INSTANCE_PENDING, ApprovalInstance

    return (
        db.query(ApprovalInstance)
        .filter(
            ApprovalInstance.biz_type == "refund",
            ApprovalInstance.biz_id == refund_id,
            ApprovalInstance.status == INSTANCE_PENDING,
        )
        .order_by(ApprovalInstance.id.desc())
        .first()
    )


def on_refund_flow_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """审批流终审回调：把结果落到退款单（不在此提交，由引擎调用方统一提交）。"""
    refund = db.query(Refund).filter(Refund.id == instance.biz_id).first()
    if not refund or refund.status != REFUND_STATUS_PENDING:
        return
    if withdrawn:
        refund.status = REFUND_STATUS_CANCELLED
        refund.review_remark = "发起人撤回退款申请"
    elif approved:
        refund.status = REFUND_STATUS_CONFIRMED
        # 执行人 = 最后一个通过节点的处理人（财务负责人）
        executor = next(
            (
                t.acted_by
                for t in sorted(instance.tasks, key=lambda x: x.seq, reverse=True)
                if t.acted_by
            ),
            None,
        )
        refund.confirmed_by = executor
        refund.confirmed_at = _now()
    else:
        refund.status = REFUND_STATUS_REJECTED
        refund.review_remark = instance.reject_reason or "审批驳回"
    refund.version += 1
    receipt = db.query(Receipt).filter(Receipt.id == refund.receipt_id).first()
    if receipt:
        receipt.version += 1


def list_refunds(db: Session, user: User, receipt_id: int) -> list[Refund]:
    _receipt(db, user, receipt_id)
    return (
        db.query(Refund)
        .filter(Refund.receipt_id == receipt_id)
        .order_by(Refund.created_at.desc())
        .all()
    )


def review_refund(
    db: Session, user: User, item_id: int, payload: RefundReviewRequest, *, approve: bool
) -> Refund:
    """按 AP-18 走三级审批流推进当前节点（禁止自审、逐级串行）。

    兼容旧接口：退款单当前激活节点若是本人角色且非本人发起，则推进一步；
    终审通过后才由回调把退款置为「已确认」。
    """
    item = _refund(db, user, item_id, lock=True)
    if item.version != payload.version:
        raise HTTPException(status_code=409, detail="退款记录已被其他操作修改，请刷新后重试")
    if item.status != REFUND_STATUS_PENDING:
        raise HTTPException(status_code=409, detail="仅待审批退款可以处理")
    instance = _refund_flow_instance(db, item.id)
    if instance is None:
        raise HTTPException(status_code=409, detail="该退款未在审批流程中，请在审批中心处理")
    comment = (payload.remark or "").strip() or ("同意退款" if approve else "驳回退款")

    from app.services import approval_flow

    approval_flow.act(db, user, instance, approve=approve, comment=comment)
    db.refresh(item)
    return item


def financial_summary(db: Session, user: User, contract_id: int) -> dict:
    contract = _contract(db, user, contract_id)
    receivables = (
        db.query(ReceivablePlan)
        .filter(
            ReceivablePlan.contract_id == contract_id,
            ReceivablePlan.status != RECEIVABLE_STATUS_CANCELLED,
        )
        .all()
    )
    receipt_ids = [
        row[0]
        for row in db.query(Receipt.id)
        .filter(
            Receipt.contract_id == contract_id,
            Receipt.status == RECEIPT_STATUS_CONFIRMED,
        )
        .all()
    ]
    receivable_total = sum((_money(x.amount) for x in receivables), ZERO)
    confirmed_receipt_total = _money(
        db.query(func.coalesce(func.sum(Receipt.amount), 0))
        .filter(
            Receipt.contract_id == contract_id,
            Receipt.status == RECEIPT_STATUS_CONFIRMED,
        )
        .scalar()
    )
    allocated_total = ZERO
    refunded_total = ZERO
    if receipt_ids:
        allocated_total = _money(
            db.query(func.coalesce(func.sum(ReceiptAllocation.amount), 0))
            .filter(
                ReceiptAllocation.receipt_id.in_(receipt_ids),
                ReceiptAllocation.status == ALLOCATION_STATUS_ACTIVE,
            )
            .scalar()
        )
        refunded_total = _money(
            db.query(func.coalesce(func.sum(Refund.amount), 0))
            .filter(
                Refund.receipt_id.in_(receipt_ids),
                Refund.status == REFUND_STATUS_CONFIRMED,
            )
            .scalar()
        )
    overdue = sum(
        (
            max(ZERO, _money(item.amount) - _allocated_to_receivable(db, item.id))
            for item in receivables
            if item.due_date < date.today()
        ),
        ZERO,
    )
    return {
        "contract_id": contract.id,
        "contract_amount": _money(contract.amount),
        "receivable_total": receivable_total,
        "confirmed_receipt_total": confirmed_receipt_total,
        "refunded_total": refunded_total,
        "allocated_total": allocated_total,
        "outstanding_receivable": max(ZERO, receivable_total - allocated_total),
        "unallocated_receipt_balance": max(
            ZERO,
            confirmed_receipt_total
            - (
                _money(
                    db.query(func.coalesce(func.sum(ReceiptAllocation.amount), 0))
                    .filter(
                        ReceiptAllocation.receipt_id.in_(receipt_ids),
                        ReceiptAllocation.status.in_(
                            [ALLOCATION_STATUS_ACTIVE, ALLOCATION_STATUS_PENDING]
                        ),
                    )
                    .scalar()
                )
                if receipt_ids
                else ZERO
            )
            - refunded_total
        ),
        "overdue_receivable": overdue,
    }


def finance_stats(db: Session, user: User) -> dict:
    receivable_query = db.query(ReceivablePlan).join(
        Contract, Contract.id == ReceivablePlan.contract_id
    )
    receivables = _apply_contract_scope(receivable_query, user).filter(
        ReceivablePlan.status != RECEIVABLE_STATUS_CANCELLED
    ).all()

    receipt_query = db.query(Receipt).join(Contract, Contract.id == Receipt.contract_id)
    receipts = _apply_contract_scope(receipt_query, user).all()
    confirmed = [item for item in receipts if item.status == RECEIPT_STATUS_CONFIRMED]
    pending_review = [
        item for item in receipts if item.status == RECEIPT_STATUS_PENDING_REVIEW
    ]

    receivable_total = sum((_money(item.amount) for item in receivables), ZERO)
    outstanding = sum(
        (
            max(ZERO, _money(item.amount) - _allocated_to_receivable(db, item.id))
            for item in receivables
        ),
        ZERO,
    )
    overdue_items = [
        item
        for item in receivables
        if item.due_date < date.today()
        and _money(item.amount) > _allocated_to_receivable(db, item.id)
    ]
    overdue_amount = sum(
        (
            _money(item.amount) - _allocated_to_receivable(db, item.id)
            for item in overdue_items
        ),
        ZERO,
    )
    confirmed_amount = sum((_money(item.amount) for item in confirmed), ZERO)
    allocated_amount = sum(
        (_allocated_from_receipt(db, item.id) for item in confirmed), ZERO
    )
    refunded_amount = sum(
        (_refund_amount(db, item.id, include_pending=False) for item in confirmed), ZERO
    )
    unallocated_amount = max(
        ZERO,
        confirmed_amount
        - sum((_reserved_from_receipt(db, item.id) for item in confirmed), ZERO)
        - refunded_amount,
    )
    pending_review_amount = sum((_money(item.amount) for item in pending_review), ZERO)

    month_start = date.today().replace(day=1)
    contract_query = db.query(Contract).filter(Contract.created_at >= month_start)
    visible_contracts = _apply_contract_scope(contract_query, user).all()
    month_contract_amount = sum(
        (_money(item.amount) for item in visible_contracts), ZERO
    )
    collection_rate = (
        (allocated_amount / receivable_total * Decimal("100")).quantize(Decimal("0.01"))
        if receivable_total > ZERO
        else ZERO
    )
    return {
        "month_contract_amount": month_contract_amount,
        "confirmed_receipt_amount": confirmed_amount,
        "receivable_total": receivable_total,
        "outstanding_receivable_amount": outstanding,
        "allocated_amount": allocated_amount,
        "unallocated_receipt_amount": unallocated_amount,
        "pending_review_count": len(pending_review),
        "pending_review_amount": pending_review_amount,
        "overdue_count": len(overdue_items),
        "overdue_amount": overdue_amount,
        "collection_rate": collection_rate,
        "forecast_gross_margin": Decimal("34.8"),
    }
