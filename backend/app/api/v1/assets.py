"""固定资产 API。"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.asset import (
    AlertOut,
    AssetCreate,
    AssetOut,
    AssetReportOut,
    AssetWorkbenchOut,
    BorrowCreate,
    BorrowOut,
    BorrowRejectRequest,
    DepreciationRuleCreate,
    DepreciationRuleOut,
    DepreciationRunRequest,
    DepreciationSnapshotOut,
    DisposalOut,
    DisposalRejectRequest,
    DisposeRequest,
    InventoryCreate,
    InventoryDetailOut,
    InventoryDifferenceOut,
    InventoryLineOut,
    InventorySessionOut,
    MaintenanceCreate,
    MaintenanceOut,
    MaintenanceRejectRequest,
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


@router.get("/inventories", response_model=List[InventorySessionOut], summary="盘点列表")
def list_inventories(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> List[InventorySessionOut]:
    _ = current_user
    return [InventorySessionOut.model_validate(x) for x in asset_service.list_inventories(db)]


@router.post("/inventories", response_model=InventorySessionOut, summary="创建盘点")
def create_inventory(
    payload: InventoryCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> InventorySessionOut:
    return InventorySessionOut.model_validate(
        asset_service.create_inventory(db, current_user, payload)
    )


@router.get("/inventories/{inventory_id}", response_model=InventoryDetailOut, summary="盘点详情")
def get_inventory(
    inventory_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> InventoryDetailOut:
    _ = current_user
    inv = asset_service.get_inventory(db, inventory_id)
    return InventoryDetailOut(
        **InventorySessionOut.model_validate(inv).model_dump(),
        lines=[InventoryLineOut.model_validate(x) for x in getattr(inv, "lines", [])],
    )


@router.post(
    "/inventories/{inventory_id}/submit",
    response_model=InventoryDetailOut,
    summary="提交盘点",
)
def submit_inventory(
    inventory_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> InventoryDetailOut:
    inv = asset_service.submit_inventory(db, current_user, inventory_id)
    return InventoryDetailOut(
        **InventorySessionOut.model_validate(inv).model_dump(),
        lines=[InventoryLineOut.model_validate(x) for x in getattr(inv, "lines", [])],
    )


@router.post(
    "/inventories/{inventory_id}/difference",
    response_model=InventoryDifferenceOut,
    summary="盘点差异",
)
def inventory_difference(
    inventory_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> InventoryDifferenceOut:
    data = asset_service.inventory_difference(db, current_user, inventory_id)
    return InventoryDifferenceOut(
        missing=[InventoryLineOut.model_validate(x) for x in data["missing"]],
        extra=[InventoryLineOut.model_validate(x) for x in data["extra"]],
        anomaly=[InventoryLineOut.model_validate(x) for x in data["anomaly"]],
        matched_count=data["matched_count"],
    )


@router.get("/maintenances", response_model=List[MaintenanceOut], summary="维保列表")
def list_maintenances(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
    status: Optional[str] = None,
) -> List[MaintenanceOut]:
    _ = current_user
    return [
        MaintenanceOut.model_validate(x)
        for x in asset_service.list_maintenances(db, status=status)
    ]


@router.post("/maintenances", response_model=MaintenanceOut, summary="新建维保")
def create_maintenance(
    payload: MaintenanceCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> MaintenanceOut:
    return MaintenanceOut.model_validate(
        asset_service.create_maintenance(db, current_user, payload)
    )


@router.post(
    "/maintenances/{maintenance_id}/approve",
    response_model=MaintenanceOut,
    summary="批准维保",
)
def approve_maintenance(
    maintenance_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> MaintenanceOut:
    return MaintenanceOut.model_validate(
        asset_service.approve_maintenance(db, current_user, maintenance_id)
    )


@router.post(
    "/maintenances/{maintenance_id}/reject",
    response_model=MaintenanceOut,
    summary="驳回维保",
)
def reject_maintenance(
    maintenance_id: int,
    payload: MaintenanceRejectRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> MaintenanceOut:
    return MaintenanceOut.model_validate(
        asset_service.reject_maintenance(db, current_user, maintenance_id, payload)
    )


@router.get(
    "/depreciation-rules",
    response_model=List[DepreciationRuleOut],
    summary="折旧规则列表",
)
def list_depreciation_rules(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> List[DepreciationRuleOut]:
    _ = current_user
    return [
        DepreciationRuleOut.model_validate(x)
        for x in asset_service.list_depreciation_rules(db)
    ]


@router.post(
    "/depreciation-rules",
    response_model=DepreciationRuleOut,
    summary="创建折旧规则",
)
def create_depreciation_rule(
    payload: DepreciationRuleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> DepreciationRuleOut:
    return DepreciationRuleOut.model_validate(
        asset_service.create_depreciation_rule(db, current_user, payload)
    )


@router.post(
    "/depreciation/run",
    response_model=List[DepreciationSnapshotOut],
    summary="运行折旧",
)
def run_depreciation(
    payload: DepreciationRunRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> List[DepreciationSnapshotOut]:
    return [
        DepreciationSnapshotOut.model_validate(x)
        for x in asset_service.run_depreciation(db, current_user, payload)
    ]


@router.get(
    "/depreciation/snapshots",
    response_model=List[DepreciationSnapshotOut],
    summary="折旧快照",
)
def list_depreciation_snapshots(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
    period_label: Optional[str] = None,
) -> List[DepreciationSnapshotOut]:
    _ = current_user
    return [
        DepreciationSnapshotOut.model_validate(x)
        for x in asset_service.list_depreciation_snapshots(db, period_label=period_label)
    ]


@router.post(
    "/disposals/{disposal_id}/approve",
    response_model=DisposalOut,
    summary="批准处置",
)
def approve_disposal(
    disposal_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> DisposalOut:
    return DisposalOut.model_validate(
        asset_service.approve_disposal(db, current_user, disposal_id)
    )


@router.post(
    "/disposals/{disposal_id}/reject",
    response_model=DisposalOut,
    summary="驳回处置",
)
def reject_disposal(
    disposal_id: int,
    payload: DisposalRejectRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> DisposalOut:
    return DisposalOut.model_validate(
        asset_service.reject_disposal(db, current_user, disposal_id, payload)
    )


@router.get("/reports", response_model=AssetReportOut, summary="资产报表")
def reports(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> AssetReportOut:
    _ = current_user
    return AssetReportOut(**asset_service.asset_reports(db))


@router.get("/alerts", response_model=List[AlertOut], summary="资产告警")
def alerts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> List[AlertOut]:
    return [AlertOut(**x) for x in asset_service.asset_alerts(db, current_user)]


@router.post("/{asset_id}/dispose", response_model=DisposalOut, summary="申请处置")
def dispose_asset(
    asset_id: int,
    payload: DisposeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> DisposalOut:
    return DisposalOut.model_validate(
        asset_service.dispose_asset(db, current_user, asset_id, payload)
    )


@router.get("/{asset_id}", response_model=AssetOut, summary="资产详情")
def get_asset(
    asset_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["asset:view"]))],
) -> AssetOut:
    _ = current_user
    return AssetOut.model_validate(asset_service.get_asset(db, asset_id))
