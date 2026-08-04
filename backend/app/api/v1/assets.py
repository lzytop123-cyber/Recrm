"""固定资产 API。"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.asset import (
    AssetCreate,
    AssetOut,
    AssetWorkbenchOut,
    BorrowCreate,
    BorrowOut,
    BorrowRejectRequest,
    InventorySessionOut,
    ScanRequest,
    ScanResultOut,
)
from app.services import asset as asset_service

router = APIRouter(prefix="/assets", tags=["固定资产"])


@router.get("/workbench", response_model=AssetWorkbenchOut, summary="固定资产工作台")
def workbench(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> AssetWorkbenchOut:
    data = asset_service.get_workbench(db, current_user)
    return AssetWorkbenchOut(
        stats=data["stats"],
        assets=[AssetOut.model_validate(x) for x in data["assets"]],
        borrows=[BorrowOut.model_validate(x) for x in data["borrows"]],
        inventory=InventorySessionOut.model_validate(data["inventory"]) if data["inventory"] else None,
        category_usage=data["category_usage"],
        alerts=data["alerts"],
        top_borrows=data["top_borrows"],
        can_manage=data["can_manage"],
    )


@router.get("", response_model=List[AssetOut], summary="资产列表")
def list_assets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
    category: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
) -> List[AssetOut]:
    _ = current_user
    return [
        AssetOut.model_validate(x)
        for x in asset_service.list_assets(db, category=category, status=status, keyword=keyword)
    ]


@router.post("", response_model=AssetOut, summary="设备入库")
def create_asset(
    payload: AssetCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> AssetOut:
    return AssetOut.model_validate(asset_service.create_asset(db, current_user, payload))


@router.get("/borrows", response_model=List[BorrowOut], summary="借用申请列表")
def list_borrows(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
    status: Optional[str] = None,
    mine: bool = Query(False),
) -> List[BorrowOut]:
    return [
        BorrowOut.model_validate(x)
        for x in asset_service.list_borrows(db, current_user, status=status, mine=mine)
    ]


@router.post("/borrows", response_model=BorrowOut, summary="新建借用申请")
def create_borrow(
    payload: BorrowCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> BorrowOut:
    return BorrowOut.model_validate(asset_service.create_borrow(db, current_user, payload))


@router.post("/borrows/{request_id}/approve", response_model=BorrowOut, summary="批准借用")
def approve_borrow(
    request_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> BorrowOut:
    return BorrowOut.model_validate(asset_service.approve_borrow(db, current_user, request_id))


@router.post("/borrows/{request_id}/reject", response_model=BorrowOut, summary="驳回借用")
def reject_borrow(
    request_id: int,
    payload: BorrowRejectRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> BorrowOut:
    return BorrowOut.model_validate(
        asset_service.reject_borrow(db, current_user, request_id, payload)
    )


@router.post("/borrows/{request_id}/checkout", response_model=BorrowOut, summary="扫码领用")
def checkout_borrow(
    request_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> BorrowOut:
    return BorrowOut.model_validate(asset_service.checkout_borrow(db, current_user, request_id))


@router.post("/borrows/{request_id}/return", response_model=BorrowOut, summary="扫码归还")
def return_borrow(
    request_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> BorrowOut:
    return BorrowOut.model_validate(asset_service.return_borrow(db, current_user, request_id))


@router.post("/scan", response_model=ScanResultOut, summary="扫码盘点/领用/归还")
def scan(
    payload: ScanRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> ScanResultOut:
    data = asset_service.scan_asset(db, current_user, payload)
    return ScanResultOut(
        ok=data["ok"],
        message=data["message"],
        asset=AssetOut.model_validate(data["asset"]) if data.get("asset") else None,
        inventory=InventorySessionOut.model_validate(data["inventory"])
        if data.get("inventory")
        else None,
    )


@router.get("/{asset_id}", response_model=AssetOut, summary="资产详情")
def get_asset(
    asset_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> AssetOut:
    _ = current_user
    return AssetOut.model_validate(asset_service.get_asset(db, asset_id))
