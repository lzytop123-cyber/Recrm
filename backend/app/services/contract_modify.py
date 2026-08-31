"""AP-04 合同修改重审。"""
from __future__ import annotations

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.rbac import user_can
from app.models.contract import (
    CONTRACT_STATUS_ACTIVE,
    CONTRACT_STATUS_APPROVED,
    CONTRACT_STATUS_SIGNED,
    Contract,
)
from app.models.user import User
from app.schemas.contract import ContractModifyRequest
from app.services.contract import (
    _apply_proofs,
    _normalize_proof_items,
    assert_can_view,
    enrich_contract,
)

MODIFY_ALLOWED_STATUSES = {
    CONTRACT_STATUS_APPROVED,
    CONTRACT_STATUS_SIGNED,
    CONTRACT_STATUS_ACTIVE,
}


def _modification_pending(contract: Contract) -> bool:
    return bool(getattr(contract, "modification_snapshot_json", None))


def enrich_modification_flags(contract: Contract) -> None:
    contract.modification_pending = _modification_pending(contract)  # type: ignore[attr-defined]


def _apply_snapshot(db: Session, contract: Contract, snapshot: dict) -> None:
    from app.services import platform as platform_service

    for key in ("title", "currency", "payment_method", "effective_date", "expire_date", "remark"):
        if key in snapshot and snapshot[key] is not None:
            setattr(contract, key, snapshot[key])
    if snapshot.get("contract_type") is not None:
        contract.contract_type = platform_service.assert_business_type(
            db, snapshot["contract_type"], enabled_only=True
        )
    if snapshot.get("amount") is not None:
        contract.amount = Decimal(str(snapshot["amount"]))
    if "proofs" in snapshot:
        _apply_proofs(contract, _normalize_proof_items(snapshot.get("proofs") or []))


def submit_modification(
    db: Session, user: User, contract_id: int, payload: ContractModifyRequest
) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view(user, contract)
    if contract.status not in MODIFY_ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="仅已审批/已签署/执行中合同可发起修改重审")
    role_codes = {r.code for r in user.roles}
    if (
        contract.owner_id != user.id
        and contract.creator_id != user.id
        and not user_can(user, "contract:manage")
        and "admin" not in role_codes
    ):
        raise HTTPException(status_code=403, detail="仅合同负责人或管理员可发起修改")

    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "contract_modify", contract.id) is not None:
        raise HTTPException(status_code=409, detail="该合同修改审批进行中")
    if _modification_pending(contract):
        raise HTTPException(status_code=409, detail="已有待审批的修改快照")

    data = payload.model_dump(exclude_unset=True, exclude={"reason"})
    if not data:
        raise HTTPException(status_code=400, detail="请填写至少一项修改内容")
    if "contract_type" in data and data["contract_type"] is not None:
        from app.services import platform as platform_service

        data["contract_type"] = platform_service.assert_business_type(
            db, data["contract_type"], enabled_only=True
        )
    if "proofs" in data:
        data["proofs"] = _normalize_proof_items(data.get("proofs"))

    new_amount = data.get("amount", contract.amount)
    snapshot = {**data, "reason": payload.reason.strip(), "prev_revision": contract.revision}
    contract.modification_snapshot_json = json.dumps(snapshot, ensure_ascii=False, default=str)

    if approval_flow.select_rule(db, "contract_modify", {"amount": new_amount}) is not None:
        approval_flow.start_instance(
            db,
            biz_type="contract_modify",
            biz_id=contract.id,
            initiator=user,
            title=f"合同修改重审 {contract.contract_no} · {contract.title}",
            summary=payload.reason.strip(),
            amount=Decimal(str(new_amount)),
            department_id=contract.department_id,
            deep_link=f"/contracts/{contract.id}",
            facts={"amount": str(new_amount), "revision": contract.revision + 1},
            commit=False,
        )
    db.commit()
    db.refresh(contract)
    return enrich_contract(db, contract)


def on_contract_modify_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    contract = db.query(Contract).filter(Contract.id == instance.biz_id).first()
    if not contract or not contract.modification_snapshot_json:
        return
    if not approved:
        if not withdrawn:
            contract.remark = (
                (contract.remark or "") + f"\n[修改驳回] {instance.reject_reason or '—'}"
            ).strip()
        contract.modification_snapshot_json = None
        return
    try:
        snapshot = json.loads(contract.modification_snapshot_json)
    except json.JSONDecodeError:
        contract.modification_snapshot_json = None
        return
    if not isinstance(snapshot, dict):
        contract.modification_snapshot_json = None
        return
    reason = str(snapshot.pop("reason", "") or "")
    prev_revision = int(snapshot.pop("prev_revision", contract.revision) or contract.revision)
    _apply_snapshot(db, contract, snapshot)
    contract.revision = prev_revision + 1
    contract.modification_snapshot_json = Nonea 
    if reason:
        contract.remark = (
            (contract.remark or "") + f"\n[修改通过 v{contract.revision}] {reason}"
        ).strip()
