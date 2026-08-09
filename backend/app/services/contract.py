"""
合同管理业务逻辑：起草、提交审批、审批、签署、执行、完成/终止。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.rbac import collect_data_scopes, user_can, widest_data_scope
from app.models.contract import (
    CONTRACT_STATUS_ACTIVE,
    CONTRACT_STATUS_APPROVED,
    CONTRACT_STATUS_COMPLETED,
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_PENDING_APPROVAL,
    CONTRACT_STATUS_SIGNED,
    CONTRACT_STATUS_TERMINATED,
    CONTRACT_STATUSES,
    Contract,
)
from app.models.customer import Customer
from app.models.finance import (
    ALLOCATION_STATUS_ACTIVE,
    RECEIPT_STATUS_CONFIRMED,
    RECEIVABLE_STATUS_CANCELLED,
    REFUND_STATUS_CONFIRMED,
    Receipt,
    ReceiptAllocation,
    ReceivablePlan,
    Refund,
)
from app.models.payment import (
    PAYMENT_RECORD_PLAN,
    PAYMENT_STATUS_CONFIRMED,
    PAYMENT_STATUS_PENDING,
    Payment,
)
from app.models.user import User
from app.schemas.contract import (
    ContractCreate,
    ContractSignRequest,
    ContractTerminateRequest,
    ContractUpdate,
)


def _log_opp_contract_milestone(db: Session, user: User, contract: Contract, content: str) -> None:
    from app.services import opportunity as opportunity_service

    opportunity_service.append_contract_milestone(
        db,
        user,
        opportunity_id=contract.opportunity_id,
        content=content,
        contract_no=contract.contract_no,
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


def _gen_contract_no(db: Session) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"HT{today}"
    count = db.query(Contract).filter(Contract.contract_no.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def _contract_net_paid(db: Session, contract: Contract) -> Decimal:
    """合同已确认净到账（确认收款 − 确认退款；无新财务则看旧 Payment）。"""
    has_new_finance = (
        db.query(ReceivablePlan.id).filter(ReceivablePlan.contract_id == contract.id).first()
        or db.query(Receipt.id).filter(Receipt.contract_id == contract.id).first()
    )
    if has_new_finance:
        confirmed_receipt_ids = [
            row[0]
            for row in db.query(Receipt.id)
            .filter(
                Receipt.contract_id == contract.id,
                Receipt.status == RECEIPT_STATUS_CONFIRMED,
            )
            .all()
        ]
        receipt_total = Decimal(
            str(
                db.query(func.coalesce(func.sum(Receipt.amount), 0))
                .filter(
                    Receipt.contract_id == contract.id,
                    Receipt.status == RECEIPT_STATUS_CONFIRMED,
                )
                .scalar()
                or 0
            )
        )
        refunded_total = Decimal("0")
        if confirmed_receipt_ids:
            refunded_total = Decimal(
                str(
                    db.query(func.coalesce(func.sum(Refund.amount), 0))
                    .filter(
                        Refund.receipt_id.in_(confirmed_receipt_ids),
                        Refund.status == REFUND_STATUS_CONFIRMED,
                    )
                    .scalar()
                    or 0
                )
            )
        return max(Decimal("0"), receipt_total - refunded_total)

    paid = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.contract_id == contract.id, Payment.status == PAYMENT_STATUS_CONFIRMED)
        .scalar()
    )
    return Decimal(str(paid or 0))


def is_collection_complete(db: Session, contract: Contract) -> bool:
    """回款是否收齐：以合同金额为准，确认净到账 >= 合同金额才算收齐。"""
    amount = Decimal(str(contract.amount or 0))
    if amount <= 0:
        return True
    return _contract_net_paid(db, contract) >= amount


def _can_complete_contract(user: User) -> bool:
    """正常完成合同（回款已齐）：contract:complete / contract:manage / admin。"""
    if user_can(user, "contract:complete") or user_can(user, "contract:manage"):
        return True
    return "admin" in {r.code for r in user.roles}


def enrich_contract(db: Session, contract: Contract) -> Contract:
    customer = db.query(Customer).filter(Customer.id == contract.customer_id).first()
    contract.customer_name = customer.name if customer else None  # type: ignore[attr-defined]
    contract.owner_name = _user_name(db, contract.owner_id)  # type: ignore[attr-defined]
    contract.creator_name = _user_name(db, contract.creator_id)  # type: ignore[attr-defined]
    contract.approved_by_name = _user_name(db, contract.approved_by)  # type: ignore[attr-defined]

    has_new_finance = (
        db.query(ReceivablePlan.id).filter(ReceivablePlan.contract_id == contract.id).first()
        or db.query(Receipt.id).filter(Receipt.contract_id == contract.id).first()
    )
    paid_amount = _contract_net_paid(db, contract)
    if has_new_finance:
        next_due = (
            db.query(ReceivablePlan.due_date)
            .filter(
                ReceivablePlan.contract_id == contract.id,
                ReceivablePlan.status.notin_(["paid", RECEIVABLE_STATUS_CANCELLED]),
            )
            .order_by(ReceivablePlan.due_date.asc())
            .first()
        )
    else:
        next_due = (
            db.query(Payment.due_date)
            .filter(
                Payment.contract_id == contract.id,
                Payment.status == PAYMENT_STATUS_PENDING,
                Payment.record_type == PAYMENT_RECORD_PLAN,
                Payment.due_date.isnot(None),
            )
            .order_by(Payment.due_date.asc())
            .first()
        )
    contract.paid_amount = paid_amount  # type: ignore[attr-defined]
    contract.next_due_date = next_due[0] if next_due else None  # type: ignore[attr-defined]
    if is_collection_complete(db, contract):
        contract.collection_status = "collected"  # type: ignore[attr-defined]
    else:
        contract.collection_status = "collecting"  # type: ignore[attr-defined]
    contract.proof_url = (  # type: ignore[attr-defined]
        f"/uploads/{contract.proof_path}" if contract.proof_path else None
    )
    return contract


def assert_can_view(user: User, contract: Contract) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes or user_can(user, "contract:manage"):
        return
    scope = widest_data_scope(collect_data_scopes(user))
    if scope == "company":
        return
    if contract.owner_id == user.id or contract.creator_id == user.id:
        return
    if scope == "department" and user.department_id and contract.department_id == user.department_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该合同")


def assert_can_edit_draft(user: User, contract: Contract) -> None:
    if contract.status != CONTRACT_STATUS_DRAFT:
        raise HTTPException(status_code=400, detail="仅草稿状态可编辑")
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes or user_can(user, "contract:manage"):
        return
    if contract.owner_id == user.id or contract.creator_id == user.id:
        return
    raise HTTPException(status_code=403, detail="无权编辑该合同")


def create_contract(db: Session, user: User, payload: ContractCreate) -> Contract:
    from app.services import platform as platform_service

    platform_service.assert_business_type(db, payload.contract_type, enabled_only=True)
    customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    if not customer:
        raise HTTPException(status_code=400, detail="客户不存在")
    if payload.opportunity_id is not None:
        from app.models.opportunity import Opportunity

        opp = db.query(Opportunity).filter(Opportunity.id == payload.opportunity_id).first()
        if not opp:
            raise HTTPException(status_code=400, detail="商机不存在")
        if opp.customer_id != payload.customer_id:
            raise HTTPException(status_code=400, detail="商机与客户不匹配")

    contract = Contract(
        contract_no=_gen_contract_no(db),
        title=payload.title.strip(),
        customer_id=payload.customer_id,
        opportunity_id=payload.opportunity_id,
        contract_type=payload.contract_type,
        amount=payload.amount,
        currency=payload.currency or "CNY",
        payment_method=payload.payment_method,
        effective_date=payload.effective_date,
        expire_date=payload.expire_date,
        status=CONTRACT_STATUS_DRAFT,
        owner_id=user.id,
        creator_id=user.id,
        department_id=user.department_id or customer.department_id,
        remark=payload.remark,
        proof_filename=payload.proof_filename,
        proof_path=payload.proof_path,
    )
    db.add(contract)
    db.flush()
    if contract.opportunity_id:
        _log_opp_contract_milestone(db, user, contract, f"已发起合同 {contract.contract_no}")
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def update_contract(db: Session, user: User, contract_id: int, payload: ContractUpdate) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view(user, contract)
    assert_can_edit_draft(user, contract)

    data = payload.model_dump(exclude_unset=True)
    if "contract_type" in data and data["contract_type"] is not None:
        from app.services import platform as platform_service

        data["contract_type"] = platform_service.assert_business_type(
            db, data["contract_type"], enabled_only=True
        )
    if "customer_id" in data:
        customer = db.query(Customer).filter(Customer.id == data["customer_id"]).first()
        if not customer:
            raise HTTPException(status_code=400, detail="客户不存在")

    for k, v in data.items():
        setattr(contract, k, v)

    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def list_contracts(
    db: Session,
    user: User,
    *,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    customer_id: Optional[int] = None,
    scope_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    enrich: bool = True,
) -> tuple[int, list[Contract]]:
    q = db.query(Contract)
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    scope = widest_data_scope(collect_data_scopes(user)) if not is_admin else "company"

    if scope_filter == "mine":
        q = q.filter(or_(Contract.owner_id == user.id, Contract.creator_id == user.id))
    else:
        if not is_admin and scope == "personal":
            q = q.filter(or_(Contract.owner_id == user.id, Contract.creator_id == user.id))
        elif not is_admin and scope == "department" and user.department_id:
            q = q.filter(
                or_(
                    Contract.department_id == user.department_id,
                    Contract.owner_id == user.id,
                    Contract.creator_id == user.id,
                )
            )

    if status:
        q = q.filter(Contract.status == status)
    if customer_id:
        q = q.filter(Contract.customer_id == customer_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(or_(Contract.title.ilike(like), Contract.contract_no.ilike(like)))

    total = q.count()
    items = (
        q.order_by(Contract.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    if not enrich:
        return total, items
    return total, [enrich_contract(db, x) for x in items]


def get_contract(db: Session, user: User, contract_id: int) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view(user, contract)
    return enrich_contract(db, contract)


def submit_approval(db: Session, user: User, contract_id: int) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view(user, contract)
    assert_can_edit_draft(user, contract)
    if contract.amount is None or contract.amount < 0:
        raise HTTPException(status_code=400, detail="合同金额无效")
    if not contract.proof_path or not contract.proof_filename:
        raise HTTPException(status_code=400, detail="请先上传合同照片或证明后再提交审批")
    contract.status = CONTRACT_STATUS_PENDING_APPROVAL
    _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 已提交审批")
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def can_approve_contract(user: User) -> bool:
    """合同审批：优先权限码，兼容 admin。"""
    if user_can(user, "contract:approve") or user_can(user, "contract:manage"):
        return True
    return "admin" in {r.code for r in user.roles}


def approve_contract(db: Session, user: User, contract_id: int) -> Contract:
    if not can_approve_contract(user):
        raise HTTPException(status_code=403, detail="无权审批合同")

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.status != CONTRACT_STATUS_PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="仅待审批合同可审批")
    contract.status = CONTRACT_STATUS_APPROVED
    contract.approved_by = user.id
    contract.approved_at = _now()
    _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 审批通过")
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def reject_contract(db: Session, user: User, contract_id: int, reason: Optional[str] = None) -> Contract:
    if not can_approve_contract(user):
        raise HTTPException(status_code=403, detail="无权驳回合同")

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.status != CONTRACT_STATUS_PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="仅待审批合同可驳回")
    contract.status = CONTRACT_STATUS_DRAFT
    if reason:
        contract.remark = ((contract.remark or "") + f"\n[驳回] {reason}").strip()
    _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 审批驳回" + (f"：{reason}" if reason else ""))
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def sign_contract(db: Session, user: User, contract_id: int, payload: ContractSignRequest) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view(user, contract)
    if contract.status != CONTRACT_STATUS_APPROVED:
        raise HTTPException(status_code=400, detail="仅已审批合同可签署")
    # 仅合同负责人可签署（线索/商机分配到谁，谁负责签）；admin 可代操作
    role_codes = {r.code for r in user.roles}
    if "admin" not in role_codes and contract.owner_id != user.id:
        raise HTTPException(status_code=403, detail="仅合同负责人可签署")
    contract.status = CONTRACT_STATUS_SIGNED
    contract.signed_date = payload.signed_date or date.today()
    if payload.effective_date:
        contract.effective_date = payload.effective_date
    elif not contract.effective_date:
        contract.effective_date = contract.signed_date
    if payload.expire_date:
        contract.expire_date = payload.expire_date
    _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 已签署")
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def activate_contract(db: Session, user: User, contract_id: int) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view(user, contract)
    if contract.status != CONTRACT_STATUS_SIGNED:
        raise HTTPException(status_code=400, detail="仅已签署合同可进入执行")
    contract.status = CONTRACT_STATUS_ACTIVE
    _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 进入执行")
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def complete_contract(db: Session, user: User, contract_id: int) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view(user, contract)
    if contract.status != CONTRACT_STATUS_ACTIVE:
        raise HTTPException(status_code=400, detail="仅执行中合同可完成")

    if not is_collection_complete(db, contract):
        raise HTTPException(
            status_code=409,
            detail="回款尚未收齐，不能完成；请先完成到款核销",
        )
    if not _can_complete_contract(user):
        raise HTTPException(status_code=403, detail="无权完成合同")
    _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 已完成")

    contract.status = CONTRACT_STATUS_COMPLETED
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def withdraw_approval(db: Session, user: User, contract_id: int) -> Contract:
    """待审批合同由负责人/创建人撤回为草稿。"""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view(user, contract)
    if contract.status != CONTRACT_STATUS_PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="仅待审批合同可撤回")
    role_codes = {r.code for r in user.roles}
    if (
        not user_can(user, "contract:manage")
        and "admin" not in role_codes
        and contract.owner_id != user.id
        and contract.creator_id != user.id
    ):
        raise HTTPException(status_code=403, detail="无权撤回该合同审批")
    contract.status = CONTRACT_STATUS_DRAFT
    _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 撤回审批")
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def terminate_contract(
    db: Session, user: User, contract_id: int, payload: ContractTerminateRequest
) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view(user, contract)
    # 仅已签署/执行中可终止；待审批请用撤回，草稿请直接编辑
    if contract.status not in {CONTRACT_STATUS_SIGNED, CONTRACT_STATUS_ACTIVE}:
        raise HTTPException(status_code=400, detail="仅已签署或执行中的合同可终止")
    # 终止需管理权限或负责人
    role_codes = {r.code for r in user.roles}
    if (
        not user_can(user, "contract:manage")
        and "admin" not in role_codes
        and contract.owner_id != user.id
    ):
        raise HTTPException(status_code=403, detail="无权终止合同")
    contract.status = CONTRACT_STATUS_TERMINATED
    contract.terminate_reason = payload.reason
    _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 已终止")
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def contract_stats(db: Session, user: User) -> dict:
    def _count(*, status: Optional[str] = None, scope_filter: Optional[str] = None) -> int:
        total, _ = list_contracts(
            db, user, status=status, scope_filter=scope_filter, page=1, page_size=1
        )
        return total

    return {
        "total": _count(),
        "draft": _count(status=CONTRACT_STATUS_DRAFT),
        "pending_approval": _count(status=CONTRACT_STATUS_PENDING_APPROVAL),
        "approved": _count(status=CONTRACT_STATUS_APPROVED),
        "signed": _count(status=CONTRACT_STATUS_SIGNED),
        "active": _count(status=CONTRACT_STATUS_ACTIVE),
        "completed": _count(status=CONTRACT_STATUS_COMPLETED),
        "terminated": _count(status=CONTRACT_STATUS_TERMINATED),
        "mine": _count(scope_filter="mine"),
    }


# silence unused import warning for type checkers
_ = CONTRACT_STATUSES
