"""收款管理 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.payment import (
    PaymentClaimCreate,
    PaymentConfirmRequest,
    PaymentCreate,
    PaymentListOut,
    PaymentOut,
    PaymentStatsOut,
    PaymentUpdate,
)
from app.services import payment as payment_service

router = APIRouter(prefix="/payments", tags=["收款管理"])


@router.get("/stats", response_model=PaymentStatsOut, summary="收款统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["payment:view"]))],
) -> PaymentStatsOut:
    return PaymentStatsOut(**payment_service.payment_stats(db, current_user))


@router.get("", response_model=PaymentListOut, summary="收款列表")
def list_payments(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["payment:view"]))],
    status: Optional[str] = None,
    due_status: Optional[str] = Query(None, description="not_due/due_soon/due/overdue/settled"),
    contract_id: Optional[int] = None,
    record_type: Optional[str] = Query(None, description="plan/claim"),
    keyword: Optional[str] = None,
    scope: Optional[str] = Query(None, description="mine/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaymentListOut:
    total, items = payment_service.list_payments(
        db,
        current_user,
        status=status,
        due_status=due_status,
        contract_id=contract_id,
        record_type=record_type,
        keyword=keyword,
        scope_filter=scope,
        page=page,
        page_size=page_size,
    )
    return PaymentListOut(total=total, items=[PaymentOut.model_validate(x) for x in items])


@router.post("", response_model=PaymentOut, summary="登记应收/收款计划")
def create_payment(
    payload: PaymentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["payment:view"]))],
) -> PaymentOut:
    payment = payment_service.create_payment(db, current_user, payload)
    return PaymentOut.model_validate(payment)


@router.post("/claims", response_model=PaymentOut, summary="提交到款认领")
def create_claim(
    payload: PaymentClaimCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["payment:view"]))],
) -> PaymentOut:
    payment = payment_service.create_claim(db, current_user, payload)
    return PaymentOut.model_validate(payment)


@router.get("/{payment_id}", response_model=PaymentOut, summary="收款详情")
def get_payment(
    payment_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["payment:view"]))],
) -> PaymentOut:
    payment = payment_service.get_payment(db, current_user, payment_id)
    return PaymentOut.model_validate(payment)


@router.patch("/{payment_id}", response_model=PaymentOut, summary="编辑待收款")
def update_payment(
    payment_id: int,
    payload: PaymentUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["payment:view"]))],
) -> PaymentOut:
    payment = payment_service.update_payment(db, current_user, payment_id, payload)
    return PaymentOut.model_validate(payment)


@router.post("/{payment_id}/confirm", response_model=PaymentOut, summary="确认到账/核销认领")
def confirm_payment(
    payment_id: int,
    payload: PaymentConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["payment:view"]))],
) -> PaymentOut:
    payment = payment_service.confirm_payment(db, current_user, payment_id, payload)
    return PaymentOut.model_validate(payment)


@router.post("/{payment_id}/refund", response_model=PaymentOut, summary="退款")
def refund_payment(
    payment_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["payment:view"]))],
    reason: Optional[str] = None,
) -> PaymentOut:
    payment = payment_service.refund_payment(db, current_user, payment_id, reason)
    return PaymentOut.model_validate(payment)
