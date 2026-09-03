"""
合同管理业务逻辑：起草、提交审批、审批、签署、执行、完成/终止。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.rbac import resolve_data_scope, user_can, user_dept_scope
from app.models.contract import (
    CONTRACT_STATUS_ACTIVE,
    CONTRACT_STATUS_APPROVED,
    CONTRACT_STATUS_COMPLETED,
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_PENDING_APPROVAL,
    CONTRACT_STATUS_SIGNED,
    CONTRACT_STATUS_TERMINATED,
    Contract,
)
from app.models.customer import Customer
from app.models.finance import (
    RECEIPT_STATUS_CONFIRMED,
    RECEIVABLE_STATUS_CANCELLED,
    REFUND_STATUS_CONFIRMED,
    Receipt,
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
    ContractProofFile,
    ContractSignRequest,
    ContractTerminateRequest,
    ContractUpdate,
)

CONTRACT_PROOF_MAX = 9


def _normalize_proof_items(
    proofs: Optional[list],
    *,
    fallback_filename: Optional[str] = None,
    fallback_path: Optional[str] = None,
) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for raw in proofs or []:
        if isinstance(raw, ContractProofFile):
            filename = (raw.filename or "").strip()
            path = (raw.path or "").strip()
        elif isinstance(raw, dict):
            filename = str(raw.get("filename") or "").strip()
            path = str(raw.get("path") or "").strip()
        else:
            continue
        if not path or path in seen:
            continue
        seen.add(path)
        items.append(
            {
                "filename": (filename or path.split("/")[-1])[:255],
                "path": path[:500],
            }
        )
        if len(items) >= CONTRACT_PROOF_MAX:
            break
    if not items and fallback_path:
        path = fallback_path.strip()
        if path:
            items.append(
                {
                    "filename": ((fallback_filename or "").strip() or path.split("/")[-1])[:255],
                    "path": path[:500],
                }
            )
    return items


def _apply_proofs(contract: Contract, items: list[dict]) -> None:
    if items:
        contract.proof_files_json = json.dumps(items, ensure_ascii=False)
        contract.proof_filename = items[0]["filename"]
        contract.proof_path = items[0]["path"]
    else:
        contract.proof_files_json = None
        contract.proof_filename = None
        contract.proof_path = None


def _proof_items_from_contract(contract: Contract) -> list[dict]:
    raw = getattr(contract, "proof_files_json", None)
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = []
        if isinstance(data, list):
            return _normalize_proof_items(data)
    if contract.proof_path:
        return _normalize_proof_items(
            None,
            fallback_filename=contract.proof_filename,
            fallback_path=contract.proof_path,
        )
    return []


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
    # 取当天最大编号 +1，避免删除造成空号后 count+1 撞已有编号
    last = (
        db.query(Contract.contract_no)
        .filter(Contract.contract_no.like(f"{prefix}%"))
        .order_by(Contract.contract_no.desc())
        .first()
    )
    seq = int(last[0][-4:]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


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
    from app.services.contract_modify import enrich_modification_flags

    enrich_modification_flags(contract)
    from app.services import approval_flow

    open_id = approval_flow.find_open_item_id(
        db,
        "contract",
        contract.id,
        biz_types=(
            "contract",
            "contract_activate",
            "contract_modify",
            "contract_terminate",
        ),
    )
    contract.approval_in_center = open_id is not None  # type: ignore[attr-defined]
    contract.open_approval_id = open_id  # type: ignore[attr-defined]
    contract.proof_url = (  # type: ignore[attr-defined]
        f"/uploads/{contract.proof_path}" if contract.proof_path else None
    )
    proofs = _proof_items_from_contract(contract)
    contract.proofs = [  # type: ignore[attr-defined]
        ContractProofFile(
            filename=x["filename"],
            path=x["path"],
            url=f"/uploads/{x['path']}",
        )
        for x in proofs
    ]
    return contract


def assert_can_view(user: User, contract: Contract) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes or user_can(user, "contract:manage"):
        return
    scope = resolve_data_scope(user, "contract")
    if scope == "company":
        return
    if contract.owner_id == user.id or contract.creator_id == user.id:
        return
    if scope == "department" and contract.department_id in user_dept_scope(user):
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
    )
    _apply_proofs(
        contract,
        _normalize_proof_items(
            payload.proofs,
            fallback_filename=payload.proof_filename,
            fallback_path=payload.proof_path,
        ),
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

    proofs_set = "proofs" in data
    proofs_payload = data.pop("proofs", None)
    legacy_proof = "proof_filename" in data or "proof_path" in data
    proof_filename = data.pop("proof_filename", None)
    proof_path = data.pop("proof_path", None)
    for k, v in data.items():
        setattr(contract, k, v)

    if proofs_set:
        _apply_proofs(contract, _normalize_proof_items(proofs_payload))
    elif legacy_proof:
        _apply_proofs(
            contract,
            _normalize_proof_items(
                None,
                fallback_filename=proof_filename,
                fallback_path=proof_path,
            ),
        )

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
    scope = resolve_data_scope(user, "contract")

    if scope_filter == "mine":
        q = q.filter(or_(Contract.owner_id == user.id, Contract.creator_id == user.id))
    else:
        if not is_admin and scope == "personal":
            q = q.filter(or_(Contract.owner_id == user.id, Contract.creator_id == user.id))
        elif not is_admin and scope == "department" and user.department_id:
            dept_ids = user_dept_scope(user)
            q = q.filter(
                or_(
                    Contract.department_id.in_(dept_ids) if dept_ids else False,
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
    if not _proof_items_from_contract(contract):
        raise HTTPException(status_code=400, detail="请先上传合同照片或证明后再提交审批")
    contract.status = CONTRACT_STATUS_PENDING_APPROVAL
    _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 已提交审批")

    # AP-01/02 合同分级审批：规则已发布 contract 类型时走引擎；否则退回旧版单节点审批。
    from app.services import approval_flow

    amount = Decimal(str(contract.amount or 0))
    facts = {"amount": amount}
    if approval_flow.select_rule(db, "contract", facts) is not None:
        approval_flow.start_instance(
            db,
            biz_type="contract",
            biz_id=contract.id,
            initiator=user,
            title=f"合同 {contract.contract_no} · {contract.title} · ¥{amount}",
            summary=(contract.remark or None),
            amount=amount,
            currency=contract.currency or "CNY",
            department_id=contract.department_id,
            deep_link=f"/contracts/{contract.id}",
            facts=facts,
            commit=False,
        )
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
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "contract", contract.id) is not None:
        raise HTTPException(status_code=409, detail="该合同已进入分级审批流程，请在审批中心处理")
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
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "contract", contract.id) is not None:
        raise HTTPException(status_code=409, detail="该合同已进入分级审批流程，请在审批中心处理")
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

    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "contract_activate", contract.id) is not None:
        raise HTTPException(status_code=409, detail="该合同激活确认进行中，请在审批中心处理")

    # AP-03 合同签署与激活：财务确认激活（发起人提交，财务在审批中心确认后生效）
    if approval_flow.select_rule(db, "contract_activate", {}) is not None:
        approval_flow.start_instance(
            db,
            biz_type="contract_activate",
            biz_id=contract.id,
            initiator=user,
            title=f"合同激活确认 {contract.contract_no} · {contract.title}",
            amount=Decimal(str(contract.amount or 0)),
            currency=contract.currency or "CNY",
            department_id=contract.department_id,
            deep_link=f"/contracts/{contract.id}",
            commit=False,
        )
    else:
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
    _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 撤回审批")

    from app.services import approval_flow

    inst = approval_flow.find_open_instance(db, "contract", contract.id)
    if inst is not None:
        approval_flow.cancel_instance(db, inst, reason="发起人撤回", commit=False)
    else:
        contract.status = CONTRACT_STATUS_DRAFT
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

    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "contract_terminate", contract.id) is not None:
        raise HTTPException(status_code=409, detail="该合同终止审批进行中，请勿重复提交")

    # AP-05 合同终止审批：通过后合同状态=终止；抄送董事长。
    contract.terminate_reason = payload.reason
    if approval_flow.select_rule(db, "contract_terminate", {}) is not None:
        approval_flow.start_instance(
            db,
            biz_type="contract_terminate",
            biz_id=contract.id,
            initiator=user,
            title=f"终止合同 {contract.contract_no} · {contract.title}",
            summary=payload.reason,
            amount=Decimal(str(contract.amount or 0)),
            currency=contract.currency or "CNY",
            department_id=contract.department_id,
            deep_link=f"/contracts/{contract.id}",
            commit=False,
        )
    else:
        contract.status = CONTRACT_STATUS_TERMINATED
        _log_opp_contract_milestone(db, user, contract, f"合同 {contract.contract_no} 已终止")
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def on_contract_flow_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-01/02 终审回调：通过→已审批；驳回/撤回→草稿。"""
    from app.services import approval_flow

    contract = db.query(Contract).filter(Contract.id == instance.biz_id).first()
    if not contract or contract.status != CONTRACT_STATUS_PENDING_APPROVAL:
        return
    if withdrawn:
        contract.status = CONTRACT_STATUS_DRAFT
        return
    if approved:
        contract.status = CONTRACT_STATUS_APPROVED
        contract.approved_by = approval_flow.last_actor_id(instance)
        contract.approved_at = _now()
    else:
        contract.status = CONTRACT_STATUS_DRAFT
        reason = instance.reject_reason or "审批驳回"
        contract.remark = ((contract.remark or "") + f"\n[驳回] {reason}").strip()


def on_contract_activate_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-03 终审回调：财务确认通过后进入执行。"""
    contract = db.query(Contract).filter(Contract.id == instance.biz_id).first()
    if not contract or contract.status != CONTRACT_STATUS_SIGNED:
        return
    if withdrawn or not approved:
        return
    contract.status = CONTRACT_STATUS_ACTIVE


def on_contract_terminate_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-05 终审回调：通过才终止；驳回/撤回恢复原状。"""
    contract = db.query(Contract).filter(Contract.id == instance.biz_id).first()
    if not contract:
        return
    if withdrawn or not approved:
        if contract.status in {CONTRACT_STATUS_SIGNED, CONTRACT_STATUS_ACTIVE}:
            contract.terminate_reason = None
        return
    if contract.status in {CONTRACT_STATUS_SIGNED, CONTRACT_STATUS_ACTIVE}:
        contract.status = CONTRACT_STATUS_TERMINATED


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
