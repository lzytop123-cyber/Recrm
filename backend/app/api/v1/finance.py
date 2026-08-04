"""合同应收、收款、核销和退款 API。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.finance import (
    AllocationCreate,
    AllocationOut,
    AllocationReverseRequest,
    AllocationReviewRequest,
    ContractFinancialSummary,
    FinanceStatsOut,
    ReceiptCreate,
    ReceiptListOut,
    ReceiptOut,
    ReceiptReviewRequest,
    ReceivableCancelRequest,
    ReceivableCreate,
    ReceivableListOut,
    ReceivableOut,
    ReceivableUpdate,
    RefundCreate,
    RefundOut,
    RefundReviewRequest,
)
from app.services import finance as finance_service

router = APIRouter(tags=["合同财务闭环"])

VIEW_FINANCE = PermissionChecker(["payment:view"])
MANAGE_RECEIVABLE = PermissionChecker(["contract:manage", "payment:manage"], any_of=True)
CLAIM_RECEIPT = PermissionChecker(["payment:claim", "payment:manage"], any_of=True)
CONFIRM_RECEIPT = PermissionChecker(["payment:confirm", "payment:manage"], any_of=True)
ALLOCATE_RECEIPT = PermissionChecker(["payment:allocate", "payment:manage"], any_of=True)
REFUND_RECEIPT = PermissionChecker(["payment:refund", "payment:manage"], any_of=True)


@router.get("/finance/stats", response_model=FinanceStatsOut, summary="财务工作台统计")
def finance_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_FINANCE)],
) -> FinanceStatsOut:
    return FinanceStatsOut(**finance_service.finance_stats(db, current_user))


@router.post(
    "/contracts/{contract_id}/receivables",
    response_model=ReceivableOut,
    summary="新建合同应收计划",
)
def create_receivable(
    contract_id: int,
    payload: ReceivableCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_RECEIVABLE)],
) -> ReceivableOut:
    return ReceivableOut.model_validate(
        finance_service.create_receivable(db, current_user, contract_id, payload)
    )


@router.get(
    "/contracts/{contract_id}/receivables",
    response_model=list[ReceivableOut],
    summary="合同应收计划",
)
def list_receivables(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_FINANCE)],
) -> list[ReceivableOut]:
    return [
        ReceivableOut.model_validate(item)
        for item in finance_service.list_receivables(db, current_user, contract_id)
    ]


@router.get("/receivables", response_model=ReceivableListOut, summary="应收工作台列表")
def list_receivables_workbench(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_FINANCE)],
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ReceivableListOut:
    total, items = finance_service.list_receivables_workbench(
        db,
        current_user,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ReceivableListOut(
        total=total,
        items=[ReceivableOut.model_validate(item) for item in items],
    )


@router.get("/receivables/{item_id}", response_model=ReceivableOut, summary="应收详情")
def get_receivable(
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_FINANCE)],
) -> ReceivableOut:
    return ReceivableOut.model_validate(
        finance_service.get_receivable(db, current_user, item_id)
    )


@router.patch("/receivables/{item_id}", response_model=ReceivableOut, summary="编辑应收计划")
def update_receivable(
    item_id: int,
    payload: ReceivableUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_RECEIVABLE)],
) -> ReceivableOut:
    return ReceivableOut.model_validate(
        finance_service.update_receivable(db, current_user, item_id, payload)
    )


@router.post(
    "/receivables/{item_id}/cancel",
    response_model=ReceivableOut,
    summary="取消应收计划",
)
def cancel_receivable(
    item_id: int,
    payload: ReceivableCancelRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(MANAGE_RECEIVABLE)],
) -> ReceivableOut:
    return ReceivableOut.model_validate(
        finance_service.cancel_receivable(db, current_user, item_id, payload)
    )


@router.post("/receipts", response_model=ReceiptOut, summary="提交到款认领")
def create_receipt(
    payload: ReceiptCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(CLAIM_RECEIPT)],
) -> ReceiptOut:
    return ReceiptOut.model_validate(
        finance_service.create_receipt(db, current_user, payload)
    )


@router.get("/receipts", response_model=ReceiptListOut, summary="到账工作台列表")
def list_receipts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_FINANCE)],
    contract_id: int | None = Query(None, ge=1),
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ReceiptListOut:
    total, items = finance_service.list_receipts(
        db,
        current_user,
        contract_id=contract_id,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ReceiptListOut(
        total=total,
        items=[ReceiptOut.model_validate(item) for item in items],
    )


@router.get("/receipts/{item_id}", response_model=ReceiptOut, summary="收款详情")
def get_receipt(
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_FINANCE)],
) -> ReceiptOut:
    return ReceiptOut.model_validate(finance_service.get_receipt(db, current_user, item_id))


@router.post("/receipts/{item_id}/confirm", response_model=ReceiptOut, summary="确认到账")
def confirm_receipt(
    item_id: int,
    payload: ReceiptReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(CONFIRM_RECEIPT)],
) -> ReceiptOut:
    return ReceiptOut.model_validate(
        finance_service.review_receipt(db, current_user, item_id, payload, approve=True)
    )


@router.post("/receipts/{item_id}/reject", response_model=ReceiptOut, summary="驳回到款认领")
def reject_receipt(
    item_id: int,
    payload: ReceiptReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(CONFIRM_RECEIPT)],
) -> ReceiptOut:
    return ReceiptOut.model_validate(
        finance_service.review_receipt(db, current_user, item_id, payload, approve=False)
    )


@router.post(
    "/receipts/{receipt_id}/allocations",
    response_model=AllocationOut,
    summary="提交收款核销（待审批）",
)
def create_allocation(
    receipt_id: int,
    payload: AllocationCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(ALLOCATE_RECEIPT)],
) -> AllocationOut:
    return AllocationOut.model_validate(
        finance_service.create_allocation(db, current_user, receipt_id, payload)
    )


@router.get(
    "/receipts/{receipt_id}/allocations",
    response_model=list[AllocationOut],
    summary="收款核销明细",
)
def list_allocations(
    receipt_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_FINANCE)],
) -> list[AllocationOut]:
    return [
        AllocationOut.model_validate(item)
        for item in finance_service.list_allocations(db, current_user, receipt_id)
    ]


@router.post(
    "/allocations/{item_id}/confirm",
    response_model=AllocationOut,
    summary="通过核销审批",
)
def confirm_allocation(
    item_id: int,
    payload: AllocationReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(CONFIRM_RECEIPT)],
) -> AllocationOut:
    return AllocationOut.model_validate(
        finance_service.review_allocation(db, current_user, item_id, payload, approve=True)
    )


@router.post(
    "/allocations/{item_id}/reject",
    response_model=AllocationOut,
    summary="驳回核销审批",
)
def reject_allocation(
    item_id: int,
    payload: AllocationReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(CONFIRM_RECEIPT)],
) -> AllocationOut:
    return AllocationOut.model_validate(
        finance_service.review_allocation(db, current_user, item_id, payload, approve=False)
    )


@router.post(
    "/allocations/{item_id}/reverse",
    response_model=AllocationOut,
    summary="冲销核销记录",
)
def reverse_allocation(
    item_id: int,
    payload: AllocationReverseRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(ALLOCATE_RECEIPT)],
) -> AllocationOut:
    return AllocationOut.model_validate(
        finance_service.reverse_allocation(db, current_user, item_id, payload)
    )


@router.post("/receipts/{receipt_id}/refunds", response_model=RefundOut, summary="申请退款")
def create_refund(
    receipt_id: int,
    payload: RefundCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(REFUND_RECEIPT)],
) -> RefundOut:
    return RefundOut.model_validate(
        finance_service.create_refund(db, current_user, receipt_id, payload)
    )


@router.get(
    "/receipts/{receipt_id}/refunds",
    response_model=list[RefundOut],
    summary="收款退款记录",
)
def list_refunds(
    receipt_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_FINANCE)],
) -> list[RefundOut]:
    return [
        RefundOut.model_validate(item)
        for item in finance_service.list_refunds(db, current_user, receipt_id)
    ]


@router.post("/refunds/{item_id}/confirm", response_model=RefundOut, summary="确认退款")
def confirm_refund(
    item_id: int,
    payload: RefundReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(REFUND_RECEIPT)],
) -> RefundOut:
    return RefundOut.model_validate(
        finance_service.review_refund(db, current_user, item_id, payload, approve=True)
    )


@router.post("/refunds/{item_id}/reject", response_model=RefundOut, summary="驳回退款")
def reject_refund(
    item_id: int,
    payload: RefundReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(REFUND_RECEIPT)],
) -> RefundOut:
    return RefundOut.model_validate(
        finance_service.review_refund(db, current_user, item_id, payload, approve=False)
    )


@router.get(
    "/contracts/{contract_id}/financial-summary",
    response_model=ContractFinancialSummary,
    summary="合同财务汇总",
)
def financial_summary(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(VIEW_FINANCE)],
) -> ContractFinancialSummary:
    return ContractFinancialSummary(
        **finance_service.financial_summary(db, current_user, contract_id)
    )
