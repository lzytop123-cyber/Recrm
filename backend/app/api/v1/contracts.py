"""合同管理 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.contract import (
    ContractCompleteRequest,
    ContractCreate,
    ContractListOut,
    ContractOut,
    ContractSignRequest,
    ContractStatsOut,
    ContractTerminateRequest,
    ContractUpdate,
)
from app.services import contract as contract_service

router = APIRouter(prefix="/contracts", tags=["合同管理"])


@router.get("/stats", response_model=ContractStatsOut, summary="合同统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
) -> ContractStatsOut:
    return ContractStatsOut(**contract_service.contract_stats(db, current_user))


@router.get("", response_model=ContractListOut, summary="合同列表")
def list_contracts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    customer_id: Optional[int] = None,
    scope: Optional[str] = Query(None, description="mine/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ContractListOut:
    total, items = contract_service.list_contracts(
        db,
        current_user,
        status=status,
        keyword=keyword,
        customer_id=customer_id,
        scope_filter=scope,
        page=page,
        page_size=page_size,
    )
    return ContractListOut(total=total, items=[ContractOut.model_validate(x) for x in items])


@router.post("", response_model=ContractOut, summary="起草合同")
def create_contract(
    payload: ContractCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
) -> ContractOut:
    contract = contract_service.create_contract(db, current_user, payload)
    return ContractOut.model_validate(contract)


@router.get("/{contract_id}", response_model=ContractOut, summary="合同详情")
def get_contract(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
) -> ContractOut:
    contract = contract_service.get_contract(db, current_user, contract_id)
    return ContractOut.model_validate(contract)


@router.patch("/{contract_id}", response_model=ContractOut, summary="编辑草稿")
def update_contract(
    contract_id: int,
    payload: ContractUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
) -> ContractOut:
    contract = contract_service.update_contract(db, current_user, contract_id, payload)
    return ContractOut.model_validate(contract)


@router.post("/{contract_id}/submit", response_model=ContractOut, summary="提交审批")
def submit_contract(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
) -> ContractOut:
    contract = contract_service.submit_approval(db, current_user, contract_id)
    return ContractOut.model_validate(contract)


@router.post("/{contract_id}/withdraw", response_model=ContractOut, summary="撤回审批")
def withdraw_contract(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
) -> ContractOut:
    contract = contract_service.withdraw_approval(db, current_user, contract_id)
    return ContractOut.model_validate(contract)


@router.post("/{contract_id}/approve", response_model=ContractOut, summary="审批通过")
def approve_contract(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
) -> ContractOut:
    contract = contract_service.approve_contract(db, current_user, contract_id)
    return ContractOut.model_validate(contract)


@router.post("/{contract_id}/reject", response_model=ContractOut, summary="审批驳回")
def reject_contract(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
    reason: Optional[str] = None,
) -> ContractOut:
    contract = contract_service.reject_contract(db, current_user, contract_id, reason)
    return ContractOut.model_validate(contract)


@router.post("/{contract_id}/sign", response_model=ContractOut, summary="签署合同")
def sign_contract(
    contract_id: int,
    payload: ContractSignRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
) -> ContractOut:
    contract = contract_service.sign_contract(db, current_user, contract_id, payload)
    return ContractOut.model_validate(contract)


@router.post("/{contract_id}/activate", response_model=ContractOut, summary="进入执行")
def activate_contract(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
) -> ContractOut:
    contract = contract_service.activate_contract(db, current_user, contract_id)
    return ContractOut.model_validate(contract)


@router.post("/{contract_id}/complete", response_model=ContractOut, summary="完成合同")
def complete_contract(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
    payload: ContractCompleteRequest = ContractCompleteRequest(),
) -> ContractOut:
    contract = contract_service.complete_contract(db, current_user, contract_id, payload)
    return ContractOut.model_validate(contract)


@router.post("/{contract_id}/terminate", response_model=ContractOut, summary="终止合同")
def terminate_contract(
    contract_id: int,
    payload: ContractTerminateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["contract:view"]))],
) -> ContractOut:
    contract = contract_service.terminate_contract(db, current_user, contract_id, payload)
    return ContractOut.model_validate(contract)
