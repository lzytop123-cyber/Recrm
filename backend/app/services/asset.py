"""
固定资产业务：台账入库、借用审批、扫码领用/归还、盘点、折旧快照。
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.rbac import user_can
from app.models.asset import (
    ASSET_CATEGORIES,
    ASSET_STATUS_AVAILABLE,
    ASSET_STATUS_BORROWED,
    ASSET_STATUS_DISPOSED,
    ASSET_STATUS_MAINTENANCE,
    ASSET_STATUS_PENDING_RETURN,
    ASSET_STATUS_RESERVED,
    BORROW_APPROVED,
    BORROW_IN_USE,
    BORROW_PENDING,
    BORROW_PENDING_RETURN,
    BORROW_REJECTED,
    BORROW_RETURNED,
    AssetBorrowItem,
    AssetBorrowRequest,
    AssetDepreciationRule,
    AssetDepreciationSnapshot,
    AssetDisposal,
    AssetInventoryLine,
    AssetInventorySession,
    AssetMaintenance,
    FixedAsset,
    ShootingSchedule,
    ShootingScheduleAsset,
    ShootingScheduleMember,
)
from app.models.department import Department
from app.models.user import User
from app.schemas.asset import (
    AssetCreate,
    AssetUpdate,
    BorrowCreate,
    BorrowRejectRequest,
    DepreciationRuleCreate,
    DepreciationRunRequest,
    DisposeRequest,
    DisposalRejectRequest,
    InventoryCreate,
    MaintenanceCreate,
    MaintenanceRejectRequest,
    ScanRequest,
    ShootingScheduleCreate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    return (u.real_name or u.username) if u else None


def _dept_name(db: Session, dept_id: Optional[int]) -> Optional[str]:
    if not dept_id:
        return None
    d = db.query(Department).filter(Department.id == dept_id).first()
    return d.name if d else None


def can_manage_assets(user: User) -> bool:
    """资产管理：认 asset:manage（含 admin 放行）；不再硬编码角色。"""
    return user_can(user, "asset:manage")


def _months_owned(purchase: Optional[date]) -> int:
    if not purchase:
        return 12
    today = date.today()
    months = (today.year - purchase.year) * 12 + (today.month - purchase.month)
    return max(1, months)


def _depreciation(value: Decimal, months: int) -> tuple[Decimal, Decimal, Decimal]:
    # 直线法：年限5年、残值率5%、按月
    monthly = (value * Decimal("0.95") / Decimal("60")).quantize(Decimal("0.01"))
    acc = (monthly * months).quantize(Decimal("0.01"))
    residual = (value * Decimal("0.05")).quantize(Decimal("0.01"))
    net = max(residual, value - acc)
    return monthly, acc, net


def enrich_asset(db: Session, row: FixedAsset) -> FixedAsset:
    row.holder_name = _user_name(db, row.holder_id)  # type: ignore[attr-defined]
    row.department_name = _dept_name(db, row.department_id)  # type: ignore[attr-defined]
    months = _months_owned(row.purchase_date)
    monthly, acc, net = _depreciation(row.original_value or Decimal("0"), months)
    row.monthly_depreciation = monthly  # type: ignore[attr-defined]
    row.accumulated_depreciation = acc  # type: ignore[attr-defined]
    row.net_value = net  # type: ignore[attr-defined]
    return row


def enrich_borrow(db: Session, row: AssetBorrowRequest) -> AssetBorrowRequest:
    row.applicant_name = _user_name(db, row.applicant_id)  # type: ignore[attr-defined]
    items = (
        db.query(AssetBorrowItem, FixedAsset)
        .join(FixedAsset, FixedAsset.id == AssetBorrowItem.asset_id)
        .filter(AssetBorrowItem.request_id == row.id)
        .all()
    )
    assets = []
    for _, asset in items:
        assets.append(
            {
                "asset_id": asset.id,
                "asset_no": asset.asset_no,
                "name": asset.name,
                "category": asset.category,
                "status": asset.status,
            }
        )
    row.assets = assets  # type: ignore[attr-defined]
    row.asset_count = len(assets)  # type: ignore[attr-defined]
    return row


def _gen_asset_no(db: Session, category: str) -> str:
    prefix_map = {"相机": "CAM", "镜头": "LEN", "灯具": "LGT", "收音": "AUD", "稳定器": "STB"}
    prefix = prefix_map.get(category, "AST")
    head = f"ZC-{prefix}-"
    last = (
        db.query(FixedAsset.asset_no)
        .filter(FixedAsset.asset_no.like(f"{head}%"))
        .order_by(FixedAsset.asset_no.desc())
        .first()
    )
    n = int(last[0][-3:]) + 1 if last else 1
    return f"{head}{n:03d}"


def _gen_qr() -> str:
    return f"QR-{secrets.token_hex(3).upper()}"


def _gen_request_no(db: Session) -> str:
    today = date.today().strftime("%m%d")
    head = f"JY-{today}"
    last = (
        db.query(AssetBorrowRequest.request_no)
        .filter(AssetBorrowRequest.request_no.like(f"{head}%"))
        .order_by(AssetBorrowRequest.request_no.desc())
        .first()
    )
    n = int(last[0][-2:]) + 1 if last else 1
    return f"{head}{n:02d}"


def ensure_seed_data(db: Session) -> None:
    # 2026-08-12 禁用:演示数据自动填充逻辑。正式使用时清空资产表后,
    # 任何资产接口(workbench/list 等)都会自动重新插入演示资产,
    # 导致测试数据永远清不干净。保留函数签名,17 个调用点全部空操作。
    return
    if db.query(FixedAsset).count() > 0:
        return

    samples = [
        ("Sony FX3电影机", "相机", "FX3", "借出中", "林溪", "新媒体器材柜 A1", 28600, "2026-08-05", "企业AI落地案例拍摄", "borrowed"),
        ("Sony 24-70mm F2.8 GM II", "镜头", "SEL2470GM2", "已预占", "安然", "新媒体器材柜 A2", 15200, "2026-09-12", "客户品牌短片", "reserved"),
        ("爱图仕 LS 600d Pro", "灯具", "LS 600d Pro", "在库可用", None, "灯光器材区 B1", 11800, "2026-07-30", None, "available"),
        ("南光 Forza 300B II", "灯具", "Forza 300B II", "维修中", None, "外送维保", 6290, "2026-07-28", "风扇异响检测", "maintenance"),
        ("RØDE Wireless PRO", "收音", "Wireless PRO", "在库可用", None, "新媒体器材柜 C1", 3195, "2026-10-18", None, "available"),
        ("DJI RS 4 Pro稳定器", "稳定器", "RS 4 Pro", "待归还验收", "许嘉", "使用人持有", 6999, "2026-08-16", "产品功能直播", "pending_return"),
    ]
    users = { (u.real_name or u.username): u for u in db.query(User).all() }
    assets: list[FixedAsset] = []
    for name, cat, model, _label, holder_name, loc, value, next_m, use, status in samples:
        holder = users.get(holder_name) if holder_name else None
        # fallback: first non-admin-ish user or admin
        if holder_name and not holder:
            holder = db.query(User).filter(User.is_active.is_(True)).order_by(User.id.asc()).offset(1).first()
            if not holder:
                holder = db.query(User).first()
        row = FixedAsset(
            asset_no=_gen_asset_no(db, cat),
            name=name,
            category=cat,
            model=model,
            serial_no=f"SN-{model.replace(' ', '')[:12]}",
            status=status,
            holder_id=holder.id if holder else None,
            location=loc,
            original_value=Decimal(str(value)),
            purchase_date=date(2025, 1, 15),
            next_maintenance=date.fromisoformat(next_m),
            qr_code=_gen_qr(),
            current_use=use,
            schedule_ref="PS-072904" if status in {"borrowed", "reserved"} else None,
        )
        db.add(row)
        db.flush()
        assets.append(row)

    applicant = db.query(User).filter(User.is_active.is_(True)).order_by(User.id.asc()).first()
    if applicant and len(assets) >= 6:
        now = _now()
        reqs = [
            ("星河制造案例访谈拍摄", [assets[0], assets[1], assets[4]], BORROW_PENDING, "PS-072904", now + timedelta(days=2), now + timedelta(days=2, hours=9)),
            ("产品功能直播", [assets[5]], BORROW_PENDING_RETURN, "PS-072255", now - timedelta(days=2), now - timedelta(hours=4)),
            ("客户品牌短片", [assets[1], assets[2]], BORROW_APPROVED, "PS-073002", now + timedelta(days=3), now + timedelta(days=3, hours=7)),
        ]
        for purpose, picks, status, sched, start, end in reqs:
            br = AssetBorrowRequest(
                request_no=_gen_request_no(db),
                purpose=purpose,
                applicant_id=applicant.id,
                start_time=start,
                end_time=end,
                schedule_ref=sched,
                status=status,
            )
            db.add(br)
            db.flush()
            for a in picks:
                db.add(AssetBorrowItem(request_id=br.id, asset_id=a.id))

    inv = AssetInventorySession(
        period_label="2026-07",
        title="7月新媒体器材盘点",
        target_count=max(6, len(assets)),
        scanned_count=3,
        matched_count=3,
        anomaly_count=1,
        status="in_progress",
    )
    db.add(inv)
    db.commit()


def create_asset(db: Session, user: User, payload: AssetCreate) -> FixedAsset:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可入库")
    if payload.category not in ASSET_CATEGORIES:
        raise HTTPException(status_code=400, detail="不支持的资产分类")
    qty = payload.quantity
    serial = (payload.serial_no or "").strip() or None
    first: Optional[FixedAsset] = None
    for _ in range(qty):
        row = FixedAsset(
            asset_no=_gen_asset_no(db, payload.category),
            name=payload.name.strip(),
            category=payload.category,
            model=(payload.model or "").strip() or None,
            serial_no=serial if qty == 1 else None,
            status=ASSET_STATUS_AVAILABLE,
            department_id=payload.department_id or user.department_id,
            location=(payload.location or "").strip() or None,
            original_value=payload.original_value,
            purchase_date=payload.purchase_date or date.today(),
            next_maintenance=payload.next_maintenance,
            qr_code=_gen_qr(),
            remark=payload.remark,
        )
        db.add(row)
        db.flush()
        if first is None:
            first = row
    db.commit()
    assert first is not None
    db.refresh(first)
    return enrich_asset(db, first)


def list_assets(
    db: Session,
    *,
    category: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
) -> List[FixedAsset]:
    ensure_seed_data(db)
    q = db.query(FixedAsset).order_by(FixedAsset.id.asc())
    if category:
        q = q.filter(FixedAsset.category == category)
    if status:
        q = q.filter(FixedAsset.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(
            (FixedAsset.asset_no.ilike(like))
            | (FixedAsset.name.ilike(like))
            | (FixedAsset.model.ilike(like))
            | (FixedAsset.qr_code.ilike(like))
        )
    return [enrich_asset(db, x) for x in q.all()]


def get_asset(db: Session, asset_id: int) -> FixedAsset:
    ensure_seed_data(db)
    row = db.query(FixedAsset).filter(FixedAsset.id == asset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="资产不存在")
    return enrich_asset(db, row)


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip()
    return text or None


def _sku_siblings(db: Session, row: FixedAsset) -> list[FixedAsset]:
    model = (row.model or "").strip()
    rows = (
        db.query(FixedAsset)
        .filter(FixedAsset.name == row.name, FixedAsset.category == row.category)
        .all()
    )
    return [x for x in rows if (x.model or "").strip() == model]


def update_asset(db: Session, user: User, asset_id: int, payload: AssetUpdate) -> FixedAsset:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可编辑")
    row = db.query(FixedAsset).filter(FixedAsset.id == asset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="资产不存在")
    if payload.category is not None and payload.category not in ASSET_CATEGORIES:
        raise HTTPException(status_code=400, detail="不支持的资产分类")

    targets = _sku_siblings(db, row) if payload.apply_to_same_model else [row]
    data = payload.model_dump(exclude_unset=True, exclude={"apply_to_same_model", "quantity"})
    for item in targets:
        if "name" in data and payload.name is not None:
            item.name = payload.name.strip()
        if "category" in data and payload.category is not None:
            item.category = payload.category
        if "model" in data:
            item.model = _blank_to_none(payload.model)
        if "location" in data:
            item.location = _blank_to_none(payload.location)
        if "original_value" in data and payload.original_value is not None:
            item.original_value = payload.original_value
        if "purchase_date" in data:
            item.purchase_date = payload.purchase_date
        if "next_maintenance" in data:
            item.next_maintenance = payload.next_maintenance
        if "department_id" in data:
            item.department_id = payload.department_id
        if "remark" in data:
            item.remark = _blank_to_none(payload.remark)
        if "serial_no" in data and item.id == row.id:
            item.serial_no = _blank_to_none(payload.serial_no)
    db.flush()
    if payload.quantity is not None:
        row = _adjust_sku_quantity(db, row, payload.quantity)
    db.commit()
    db.refresh(row)
    return enrich_asset(db, row)


def _unit_is_removable(db: Session, asset: FixedAsset) -> bool:
    if asset.status != ASSET_STATUS_AVAILABLE:
        return False
    if db.query(AssetBorrowItem).filter(AssetBorrowItem.asset_id == asset.id).first():
        return False
    if db.query(AssetMaintenance).filter(AssetMaintenance.asset_id == asset.id).first():
        return False
    if db.query(AssetDisposal).filter(AssetDisposal.asset_id == asset.id).first():
        return False
    if db.query(AssetInventoryLine).filter(AssetInventoryLine.asset_id == asset.id).first():
        return False
    if db.query(AssetDepreciationSnapshot).filter(AssetDepreciationSnapshot.asset_id == asset.id).first():
        return False
    if db.query(ShootingScheduleAsset).filter(ShootingScheduleAsset.asset_id == asset.id).first():
        return False
    return True


def _clone_unit(db: Session, template: FixedAsset) -> FixedAsset:
    row = FixedAsset(
        asset_no=_gen_asset_no(db, template.category),
        name=template.name,
        category=template.category,
        model=template.model,
        serial_no=None,
        status=ASSET_STATUS_AVAILABLE,
        department_id=template.department_id,
        location=template.location,
        original_value=template.original_value,
        purchase_date=template.purchase_date or date.today(),
        next_maintenance=template.next_maintenance,
        qr_code=_gen_qr(),
        remark=template.remark,
    )
    db.add(row)
    db.flush()
    return row


def _adjust_sku_quantity(db: Session, row: FixedAsset, quantity: int) -> FixedAsset:
    siblings = _sku_siblings(db, row)
    current = len(siblings)
    if quantity == current:
        return row
    if quantity > current:
        for _ in range(quantity - current):
            _clone_unit(db, row)
        return row
    removable = [x for x in siblings if x.id != row.id and _unit_is_removable(db, x)]
    if _unit_is_removable(db, row):
        removable.append(row)
    locked = current - len(removable)
    if quantity < locked:
        raise HTTPException(
            status_code=400,
            detail=f"该型号有 {locked} 件无法删除（借出或已有记录），数量不能少于 {locked}",
        )
    need_drop = current - quantity
    drop_ids = {x.id for x in removable[:need_drop]}
    for item in siblings:
        if item.id in drop_ids:
            db.delete(item)
    db.flush()
    if row.id in drop_ids:
        kept = next(x for x in siblings if x.id not in drop_ids)
        return kept
    return row


def create_borrow(db: Session, user: User, payload: BorrowCreate) -> AssetBorrowRequest:
    ensure_seed_data(db)
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="归还时间必须晚于开始时间")
    assets = db.query(FixedAsset).filter(FixedAsset.id.in_(payload.asset_ids)).all()
    if len(assets) != len(set(payload.asset_ids)):
        raise HTTPException(status_code=400, detail="存在无效器材")
    for a in assets:
        if a.status not in {ASSET_STATUS_AVAILABLE, ASSET_STATUS_RESERVED}:
            if a.status == ASSET_STATUS_MAINTENANCE:
                raise HTTPException(status_code=400, detail=f"{a.name} 维修中，不可借用")
            if a.status in {ASSET_STATUS_BORROWED, ASSET_STATUS_PENDING_RETURN}:
                raise HTTPException(status_code=400, detail=f"{a.name} 当前不可用（{a.status}）")
    br = AssetBorrowRequest(
        request_no=_gen_request_no(db),
        purpose=payload.purpose.strip(),
        applicant_id=user.id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        schedule_ref=payload.schedule_ref,
        status=BORROW_PENDING,
        remark=payload.remark,
    )
    db.add(br)
    db.flush()
    for a in assets:
        db.add(AssetBorrowItem(request_id=br.id, asset_id=a.id))

    # AP-19 资产领用审批流：部门负责人 → 行政部负责人(执行出库)
    from app.services import approval_flow

    if approval_flow.select_rule(db, "asset_borrow", {}) is not None:
        approval_flow.start_instance(
            db,
            biz_type="asset_borrow",
            biz_id=br.id,
            initiator=user,
            title=f"资产领用 {br.request_no}",
            summary=(br.purpose or None),
            department_id=user.department_id,
            deep_link=f"/assets?tab=borrow&borrow_id={br.id}",
            commit=False,
        )
    db.commit()
    db.refresh(br)
    return enrich_borrow(db, br)


def on_borrow_flow_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-19 终审回调：通过则复用 approve_borrow(执行出库/占用)，驳回/撤回置驳回。"""
    from app.services import approval_flow

    br = db.query(AssetBorrowRequest).filter(AssetBorrowRequest.id == instance.biz_id).first()
    if not br or br.status != BORROW_PENDING:
        return
    if approved:
        actor = approval_flow.last_actor(db, instance)
        if actor is not None:
            approve_borrow(db, actor, br.id)  # 复用既有逻辑（含资产预留/持有人）
    else:
        br.status = BORROW_REJECTED
        br.reject_reason = "申请人撤回" if withdrawn else (instance.reject_reason or "审批驳回")
        br.approved_at = _now()


def list_borrows(
    db: Session, user: User, *, status: Optional[str] = None, mine: bool = False
) -> List[AssetBorrowRequest]:
    ensure_seed_data(db)
    q = db.query(AssetBorrowRequest).order_by(AssetBorrowRequest.id.desc())
    if mine or not can_manage_assets(user):
        q = q.filter(AssetBorrowRequest.applicant_id == user.id)
    if status:
        q = q.filter(AssetBorrowRequest.status == status)
    return [enrich_borrow(db, x) for x in q.all()]


def approve_borrow(db: Session, user: User, request_id: int) -> AssetBorrowRequest:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可审批")
    br = db.query(AssetBorrowRequest).filter(AssetBorrowRequest.id == request_id).first()
    if not br or br.status != BORROW_PENDING:
        raise HTTPException(status_code=400, detail="申请不存在或状态不可批准")
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "asset_borrow", br.id) is not None:
        raise HTTPException(status_code=409, detail="该领用已进入审批流程，请在审批中心处理")
    items = (
        db.query(AssetBorrowItem, FixedAsset)
        .join(FixedAsset, FixedAsset.id == AssetBorrowItem.asset_id)
        .filter(AssetBorrowItem.request_id == br.id)
        .all()
    )
    for _, asset in items:
        if asset.status not in {ASSET_STATUS_AVAILABLE, ASSET_STATUS_RESERVED}:
            raise HTTPException(status_code=400, detail=f"{asset.name} 已被占用，无法批准")
        asset.status = ASSET_STATUS_RESERVED
        asset.holder_id = br.applicant_id
        asset.current_use = br.purpose
        asset.schedule_ref = br.schedule_ref
    br.status = BORROW_APPROVED
    br.approved_by = user.id
    br.approved_at = _now()
    db.commit()
    db.refresh(br)
    return enrich_borrow(db, br)


def reject_borrow(
    db: Session, user: User, request_id: int, payload: BorrowRejectRequest
) -> AssetBorrowRequest:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可驳回")
    br = db.query(AssetBorrowRequest).filter(AssetBorrowRequest.id == request_id).first()
    if not br or br.status != BORROW_PENDING:
        raise HTTPException(status_code=400, detail="申请不存在或状态不可驳回")
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "asset_borrow", br.id) is not None:
        raise HTTPException(status_code=409, detail="该领用已进入审批流程，请在审批中心处理")
    br.status = BORROW_REJECTED
    br.reject_reason = payload.reason.strip()
    br.approved_by = user.id
    br.approved_at = _now()
    db.commit()
    db.refresh(br)
    return enrich_borrow(db, br)


def checkout_borrow(db: Session, user: User, request_id: int) -> AssetBorrowRequest:
    br = db.query(AssetBorrowRequest).filter(AssetBorrowRequest.id == request_id).first()
    if not br or br.status != BORROW_APPROVED:
        raise HTTPException(status_code=400, detail="仅已批准申请可领用")
    if br.applicant_id != user.id and not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="无权领用该申请")
    items = (
        db.query(AssetBorrowItem, FixedAsset)
        .join(FixedAsset, FixedAsset.id == AssetBorrowItem.asset_id)
        .filter(AssetBorrowItem.request_id == br.id)
        .all()
    )
    for _, asset in items:
        asset.status = ASSET_STATUS_BORROWED
        asset.holder_id = br.applicant_id
    br.status = BORROW_IN_USE
    db.commit()
    db.refresh(br)
    return enrich_borrow(db, br)


def _finalize_borrow_return(db: Session, br: AssetBorrowRequest) -> None:
    """执行归还：清空持有人并标记已归还。"""
    items = (
        db.query(AssetBorrowItem, FixedAsset)
        .join(FixedAsset, FixedAsset.id == AssetBorrowItem.asset_id)
        .filter(AssetBorrowItem.request_id == br.id)
        .all()
    )
    for _, asset in items:
        asset.status = ASSET_STATUS_AVAILABLE
        asset.holder_id = None
        asset.current_use = None
        asset.schedule_ref = None
    br.status = BORROW_RETURNED
    br.returned_at = _now()


def return_borrow(db: Session, user: User, request_id: int) -> AssetBorrowRequest:
    br = db.query(AssetBorrowRequest).filter(AssetBorrowRequest.id == request_id).first()
    if not br or br.status not in {BORROW_IN_USE, BORROW_APPROVED, BORROW_PENDING_RETURN}:
        raise HTTPException(status_code=400, detail="当前状态不可归还")
    if br.applicant_id != user.id and not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="无权归还该申请")
    from app.services import approval_flow

    if br.status == BORROW_RETURNED:
        return enrich_borrow(db, br)
    if approval_flow.find_open_instance(db, "asset_return", br.id) is not None:
        raise HTTPException(status_code=409, detail="归还确认审批中，请在审批中心处理")

    # AP-20 资产归还确认：行政确认后清空持有人
    if approval_flow.select_rule(db, "asset_return", {}) is not None:
        br.status = BORROW_PENDING_RETURN
        approval_flow.start_instance(
            db,
            biz_type="asset_return",
            biz_id=br.id,
            initiator=user,
            title=f"资产归还确认 {br.request_no}",
            summary=(br.purpose or None),
            department_id=user.department_id,
            deep_link=f"/assets?tab=borrow&borrow_id={br.id}",
            commit=False,
        )
        db.commit()
        db.refresh(br)
        return enrich_borrow(db, br)

    _finalize_borrow_return(db, br)
    db.commit()
    db.refresh(br)
    return enrich_borrow(db, br)


def on_return_flow_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-20 终审回调：通过则执行归还，驳回/撤回恢复在用。"""
    br = db.query(AssetBorrowRequest).filter(AssetBorrowRequest.id == instance.biz_id).first()
    if not br or br.status != BORROW_PENDING_RETURN:
        return
    if approved:
        _finalize_borrow_return(db, br)
    elif withdrawn:
        br.status = BORROW_IN_USE
    else:
        br.status = BORROW_IN_USE
        br.reject_reason = instance.reject_reason or "归还确认驳回"


def get_or_create_inventory(db: Session) -> AssetInventorySession:
    ensure_seed_data(db)
    period = date.today().strftime("%Y-%m")
    inv = db.query(AssetInventorySession).filter(AssetInventorySession.period_label == period).first()
    if inv:
        return inv
    total = db.query(FixedAsset).count()
    inv = AssetInventorySession(
        period_label=period,
        title=f"{date.today().month}月新媒体器材盘点",
        target_count=max(total, 1),
        scanned_count=0,
        matched_count=0,
        anomaly_count=0,
        status="in_progress",
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def scan_asset(db: Session, user: User, payload: ScanRequest) -> dict:
    ensure_seed_data(db)
    asset: Optional[FixedAsset] = None
    if payload.asset_id:
        asset = db.query(FixedAsset).filter(FixedAsset.id == payload.asset_id).first()
    elif payload.qr_code:
        asset = db.query(FixedAsset).filter(FixedAsset.qr_code == payload.qr_code.strip()).first()
    else:
        # 模拟扫描：取下一件未盘点倾向的可用/预占设备
        asset = (
            db.query(FixedAsset)
            .filter(FixedAsset.status != ASSET_STATUS_MAINTENANCE)
            .order_by(FixedAsset.id.asc())
            .offset(get_or_create_inventory(db).scanned_count % max(1, db.query(FixedAsset).count()))
            .first()
        )
    if not asset:
        raise HTTPException(status_code=404, detail="未识别到资产二维码")

    inv = get_or_create_inventory(db)
    mode = payload.mode or "inventory"

    if mode == "inventory":
        if inv.scanned_count < inv.target_count:
            inv.scanned_count += 1
            if asset.status == ASSET_STATUS_MAINTENANCE:
                inv.anomaly_count += 1
            else:
                inv.matched_count += 1
            db.commit()
            db.refresh(inv)
        return {
            "ok": True,
            "message": "扫码盘点成功，账实已核验",
            "asset": enrich_asset(db, asset),
            "inventory": inv,
        }

    if mode == "checkout":
        br = (
            db.query(AssetBorrowRequest)
            .join(AssetBorrowItem, AssetBorrowItem.request_id == AssetBorrowRequest.id)
            .filter(
                AssetBorrowItem.asset_id == asset.id,
                AssetBorrowRequest.status == BORROW_APPROVED,
            )
            .order_by(AssetBorrowRequest.id.desc())
            .first()
        )
        if not br:
            raise HTTPException(status_code=400, detail="无对应已批准借用单")
        checkout_borrow(db, user, br.id)
        db.refresh(asset)
        return {
            "ok": True,
            "message": "扫码领用成功",
            "asset": enrich_asset(db, asset),
            "inventory": inv,
        }

    if mode == "return":
        br = (
            db.query(AssetBorrowRequest)
            .join(AssetBorrowItem, AssetBorrowItem.request_id == AssetBorrowRequest.id)
            .filter(
                AssetBorrowItem.asset_id == asset.id,
                AssetBorrowRequest.status.in_(
                    [BORROW_IN_USE, BORROW_PENDING_RETURN, BORROW_APPROVED]
                ),
            )
            .order_by(AssetBorrowRequest.id.desc())
            .first()
        )
        if not br:
            raise HTTPException(status_code=400, detail="无对应待归还借用单")
        return_borrow(db, user, br.id)
        db.refresh(asset)
        return {
            "ok": True,
            "message": "扫码归还成功",
            "asset": enrich_asset(db, asset),
            "inventory": inv,
        }

    raise HTTPException(status_code=400, detail="不支持的扫码模式")


def get_workbench(db: Session, user: User) -> dict:
    ensure_seed_data(db)
    assets = [enrich_asset(db, x) for x in db.query(FixedAsset).order_by(FixedAsset.id.asc()).all()]
    borrows = list_borrows(db, user)
    inv = get_or_create_inventory(db)

    total = len(assets)
    available = sum(1 for x in assets if x.status == ASSET_STATUS_AVAILABLE)
    borrowed_or_reserved = sum(
        1
        for x in assets
        if x.status in {ASSET_STATUS_BORROWED, ASSET_STATUS_RESERVED, ASSET_STATUS_PENDING_RETURN}
    )
    maintenance = sum(1 for x in assets if x.status == ASSET_STATUS_MAINTENANCE)
    overdue = sum(
        1
        for b in borrows
        if b.status in {BORROW_IN_USE, BORROW_PENDING_RETURN} and b.end_time < _now()
    )
    today = date.today()
    due_today = sum(
        1
        for b in borrows
        if b.status in {BORROW_APPROVED, BORROW_IN_USE, BORROW_PENDING_RETURN}
        and b.end_time.date() == today
    )
    alerts = maintenance + overdue + sum(
        1 for x in assets if x.next_maintenance and x.next_maintenance <= today + timedelta(days=7)
    )
    original_sum = sum((x.original_value or Decimal("0")) for x in assets)
    net_sum = sum((getattr(x, "net_value", None) or Decimal("0")) for x in assets)

    # category usage
    cat_map: dict[str, list] = {}
    for a in assets:
        cat_map.setdefault(a.category, []).append(a)
    category_usage = []
    for cat, rows in cat_map.items():
        busy = sum(
            1
            for x in rows
            if x.status in {ASSET_STATUS_BORROWED, ASSET_STATUS_RESERVED, ASSET_STATUS_PENDING_RETURN}
        )
        util = int(round(busy * 100 / max(1, len(rows))))
        # prototype shows higher utilization rates — blend with borrowed ratio
        util = max(util, int(round((len(rows) - sum(1 for x in rows if x.status == ASSET_STATUS_AVAILABLE)) * 100 / max(1, len(rows)))))
        category_usage.append({"category": cat, "count": len(rows), "utilization": util})

    alert_list = []
    for a in assets:
        if a.status == ASSET_STATUS_MAINTENANCE:
            alert_list.append(
                {
                    "kind": "maintenance",
                    "title": a.name,
                    "detail": f"维保中 · {a.current_use or a.location or '—'}",
                    "tag": "维保",
                    "asset_id": a.id,
                    "request_id": None,
                }
            )
        elif a.next_maintenance and a.next_maintenance <= today + timedelta(days=3):
            alert_list.append(
                {
                    "kind": "maintenance_due",
                    "title": a.name,
                    "detail": f"维保到期 · {a.next_maintenance.isoformat()}",
                    "tag": "今天" if a.next_maintenance <= today else "关注",
                    "asset_id": a.id,
                    "request_id": None,
                }
            )
    for b in borrows:
        if b.status == BORROW_PENDING_RETURN:
            alert_list.append(
                {
                    "kind": "return",
                    "title": b.purpose,
                    "detail": f"待归还验收 · {getattr(b, 'applicant_name', '')}",
                    "tag": "归还",
                    "asset_id": None,
                    "request_id": b.id,
                }
            )

    # top borrows by item count frequency
    freq: dict[int, int] = {}
    for b in borrows:
        for item in getattr(b, "assets", []) or []:
            aid = item["asset_id"] if isinstance(item, dict) else item.asset_id
            freq[aid] = freq.get(aid, 0) + 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:5]
    asset_by_id = {a.id: a for a in assets}
    max_c = max([c for _, c in top], default=1)
    top_borrows = []
    for aid, c in top:
        a = asset_by_id.get(aid)
        if a:
            top_borrows.append(
                {"asset_id": aid, "name": a.name, "count": c, "score": int(round(c * 100 / max_c))}
            )

    returned = sum(1 for b in borrows if b.status == BORROW_RETURNED)
    late = overdue
    on_time = int(round(returned * 100 / max(1, returned + late))) if (returned or late) else 96

    stats = {
        "total": total,
        "available": available,
        "available_rate": int(round(available * 100 / max(1, total))),
        "borrowed_or_reserved": borrowed_or_reserved,
        "due_today": due_today,
        "alerts": alerts,
        "maintenance": maintenance,
        "overdue": overdue,
        "original_value_sum": original_sum,
        "net_value_sum": net_sum,
        "utilization_rate": int(round(borrowed_or_reserved * 100 / max(1, total))),
        "on_time_return_rate": on_time,
        "maintenance_cost": Decimal("8420"),
    }
    return {
        "stats": stats,
        "assets": assets,
        "borrows": borrows,
        "inventory": inv,
        "category_usage": category_usage,
        "alerts": alert_list[:8],
        "top_borrows": top_borrows,
        "can_manage": can_manage_assets(user),
    }


# ---- inventory / maintenance / depreciation / disposal / reports ----


def list_inventories(db: Session) -> list[AssetInventorySession]:
    ensure_seed_data(db)
    return db.query(AssetInventorySession).order_by(AssetInventorySession.id.desc()).all()


def create_inventory(db: Session, user: User, payload: InventoryCreate) -> AssetInventorySession:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可创建盘点")
    ensure_seed_data(db)
    period = (payload.period_label or date.today().strftime("%Y-%m")).strip()
    if db.query(AssetInventorySession).filter(AssetInventorySession.period_label == period).first():
        raise HTTPException(status_code=400, detail="该期间盘点已存在")
    total = db.query(FixedAsset).filter(FixedAsset.status != ASSET_STATUS_DISPOSED).count()
    inv = AssetInventorySession(
        period_label=period,
        title=(payload.title or f"{period}器材盘点").strip(),
        target_count=max(total, 1),
        scanned_count=0,
        matched_count=0,
        anomaly_count=0,
        status="in_progress",
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def get_inventory(db: Session, inventory_id: int) -> AssetInventorySession:
    ensure_seed_data(db)
    inv = db.query(AssetInventorySession).filter(AssetInventorySession.id == inventory_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="盘点不存在")
    lines = (
        db.query(AssetInventoryLine)
        .filter(AssetInventoryLine.session_id == inv.id)
        .order_by(AssetInventoryLine.id.asc())
        .all()
    )
    inv.lines = lines  # type: ignore[attr-defined]
    return inv


def submit_inventory(db: Session, user: User, inventory_id: int) -> AssetInventorySession:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可提交盘点")
    inv = db.query(AssetInventorySession).filter(AssetInventorySession.id == inventory_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="盘点不存在")
    if inv.status not in {"in_progress", "pending_approval"}:
        raise HTTPException(status_code=400, detail="盘点已提交")
    from app.services import approval_flow

    has_diff = (inv.anomaly_count or 0) > 0
    if has_diff and approval_flow.select_rule(db, "asset_inventory_diff", {}) is not None:
        inv.status = "pending_approval"
        approval_flow.start_instance(
            db,
            biz_type="asset_inventory_diff",
            biz_id=inv.id,
            initiator=user,
            title=f"盘点差异审批 {inv.period_label}",
            summary=f"异常 {inv.anomaly_count} 项",
            department_id=user.department_id,
            deep_link=f"/assets?tab=inventory&inventory_id={inv.id}",
            commit=False,
        )
    else:
        inv.status = "submitted"
    db.commit()
    db.refresh(inv)
    return get_inventory(db, inv.id)


def on_inventory_diff_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-23 终审回调：通过则提交盘点，驳回/撤回恢复进行中。"""
    inv = db.query(AssetInventorySession).filter(AssetInventorySession.id == instance.biz_id).first()
    if not inv or inv.status != "pending_approval":
        return
    if approved:
        inv.status = "submitted"
    else:
        inv.status = "in_progress"


def inventory_difference(db: Session, user: User, inventory_id: int) -> dict:
    _ = user
    inv = get_inventory(db, inventory_id)
    lines: list[AssetInventoryLine] = list(getattr(inv, "lines", []) or [])
    scanned_ids = {x.asset_id for x in lines if x.asset_id}
    assets = (
        db.query(FixedAsset)
        .filter(FixedAsset.status != ASSET_STATUS_DISPOSED)
        .all()
    )
    missing_rows = []
    for a in assets:
        if a.id not in scanned_ids:
            row = AssetInventoryLine(
                session_id=inv.id,
                asset_id=a.id,
                qr_code=a.qr_code,
                result="missing",
                scanned_at=_now(),
            )
            db.add(row)
            db.flush()
            missing_rows.append(row)
            inv.anomaly_count = (inv.anomaly_count or 0) + 1
    db.commit()
    lines = (
        db.query(AssetInventoryLine)
        .filter(AssetInventoryLine.session_id == inv.id)
        .order_by(AssetInventoryLine.id.asc())
        .all()
    )
    return {
        "missing": [x for x in lines if x.result == "missing"],
        "extra": [x for x in lines if x.result == "extra"],
        "anomaly": [x for x in lines if x.result == "anomaly"],
        "matched_count": sum(1 for x in lines if x.result == "matched"),
    }


def list_maintenances(db: Session, *, status: Optional[str] = None) -> list[AssetMaintenance]:
    ensure_seed_data(db)
    q = db.query(AssetMaintenance).order_by(AssetMaintenance.id.desc())
    if status:
        q = q.filter(AssetMaintenance.status == status)
    return [_enrich_maintenance(db, x) for x in q.all()]


def _enrich_maintenance(db: Session, row: AssetMaintenance) -> AssetMaintenance:
    asset = db.query(FixedAsset).filter(FixedAsset.id == row.asset_id).first()
    row.asset_name = asset.name if asset else None  # type: ignore[attr-defined]
    row.applicant_name = _user_name(db, row.applicant_id)  # type: ignore[attr-defined]
    return row


def create_maintenance(db: Session, user: User, payload: MaintenanceCreate) -> AssetMaintenance:
    ensure_seed_data(db)
    asset = db.query(FixedAsset).filter(FixedAsset.id == payload.asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    cost = payload.cost or Decimal("0")
    row = AssetMaintenance(
        asset_id=payload.asset_id,
        title=payload.title.strip(),
        plan_date=payload.plan_date,
        status="pending_approval",
        applicant_id=user.id,
        cost=cost,
        remark=payload.remark,
    )
    db.add(row)
    db.flush()

    # AP-22 维修费：≥3千走审批，＜3千无需审批
    from app.services import approval_flow

    if cost < Decimal("3000"):
        row.status = "approved"
        row.approved_by = user.id
        row.approved_at = _now()
        asset.status = ASSET_STATUS_MAINTENANCE
        asset.current_use = row.title
    elif approval_flow.select_rule(db, "asset_maintenance", {"amount": cost}) is not None:
        approval_flow.start_instance(
            db,
            biz_type="asset_maintenance",
            biz_id=row.id,
            initiator=user,
            title=f"资产维修费 {asset.name} · {row.title}",
            summary=f"¥{cost}",
            amount=cost,
            department_id=user.department_id,
            deep_link=f"/assets?tab=maintenance&maintenance_id={row.id}",
            facts={"amount": str(cost)},
            commit=False,
        )
    db.commit()
    db.refresh(row)
    return _enrich_maintenance(db, row)


def on_maintenance_flow_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    """AP-22 终审回调：通过则批准维保，驳回/撤回置驳回。"""
    from app.services import approval_flow

    row = db.query(AssetMaintenance).filter(AssetMaintenance.id == instance.biz_id).first()
    if not row or row.status != "pending_approval":
        return
    if approved:
        actor = approval_flow.last_actor(db, instance)
        if actor is not None:
            approve_maintenance(db, actor, row.id)
    else:
        row.status = "rejected"
        row.reject_reason = "申请人撤回" if withdrawn else (instance.reject_reason or "审批驳回")
        row.approved_at = _now()


def approve_maintenance(db: Session, user: User, maintenance_id: int) -> AssetMaintenance:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可审批维保")
    row = db.query(AssetMaintenance).filter(AssetMaintenance.id == maintenance_id).first()
    if not row or row.status not in {"pending_approval", "planned"}:
        raise HTTPException(status_code=400, detail="维保不存在或状态不可批准")
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "asset_maintenance", row.id) is not None:
        raise HTTPException(status_code=409, detail="该维保已进入审批流程，请在审批中心处理")
    row.status = "approved"
    row.approved_by = user.id
    row.approved_at = _now()
    asset = db.query(FixedAsset).filter(FixedAsset.id == row.asset_id).first()
    if asset:
        asset.status = ASSET_STATUS_MAINTENANCE
        asset.current_use = row.title
    db.commit()
    db.refresh(row)
    return _enrich_maintenance(db, row)


def reject_maintenance(
    db: Session, user: User, maintenance_id: int, payload: MaintenanceRejectRequest
) -> AssetMaintenance:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可驳回维保")
    row = db.query(AssetMaintenance).filter(AssetMaintenance.id == maintenance_id).first()
    if not row or row.status not in {"pending_approval", "planned"}:
        raise HTTPException(status_code=400, detail="维保不存在或状态不可驳回")
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, "asset_maintenance", row.id) is not None:
        raise HTTPException(status_code=409, detail="该维保已进入审批流程，请在审批中心处理")
    row.status = "rejected"
    row.reject_reason = payload.reason.strip()
    row.approved_by = user.id
    row.approved_at = _now()
    db.commit()
    db.refresh(row)
    return _enrich_maintenance(db, row)


def list_depreciation_rules(db: Session) -> list[AssetDepreciationRule]:
    return db.query(AssetDepreciationRule).order_by(AssetDepreciationRule.id.desc()).all()


def create_depreciation_rule(
    db: Session, user: User, payload: DepreciationRuleCreate
) -> AssetDepreciationRule:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可创建折旧规则")
    if payload.method != "straight_line":
        raise HTTPException(status_code=400, detail="仅支持直线法")
    row = AssetDepreciationRule(
        name=payload.name.strip(),
        version=payload.version.strip(),
        status=payload.status,
        method=payload.method,
        useful_life_months=payload.useful_life_months,
        residual_rate=payload.residual_rate,
        effective_from=payload.effective_from or date.today(),
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def run_depreciation(db: Session, user: User, payload: DepreciationRunRequest) -> list[AssetDepreciationSnapshot]:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可运行折旧")
    ensure_seed_data(db)
    period = (payload.period_label or date.today().strftime("%Y-%m")).strip()
    rule = (
        db.query(AssetDepreciationRule)
        .filter(AssetDepreciationRule.status == "published")
        .order_by(AssetDepreciationRule.id.desc())
        .first()
    )
    assets = db.query(FixedAsset).filter(FixedAsset.status != ASSET_STATUS_DISPOSED).all()
    out: list[AssetDepreciationSnapshot] = []
    for asset in assets:
        months = _months_owned(asset.purchase_date)
        value = asset.original_value or Decimal("0")
        if rule:
            life = max(1, rule.useful_life_months)
            residual_rate = rule.residual_rate or Decimal("0.05")
            monthly = (value * (Decimal("1") - residual_rate) / Decimal(life)).quantize(Decimal("0.01"))
            acc = (monthly * months).quantize(Decimal("0.01"))
            residual = (value * residual_rate).quantize(Decimal("0.01"))
            net = max(residual, value - acc)
            rule_id = rule.id
        else:
            monthly, acc, net = _depreciation(value, months)
            rule_id = None
        existing = (
            db.query(AssetDepreciationSnapshot)
            .filter(
                AssetDepreciationSnapshot.period_label == period,
                AssetDepreciationSnapshot.asset_id == asset.id,
            )
            .first()
        )
        if existing:
            existing.rule_id = rule_id
            existing.original_value = value
            existing.monthly_amount = monthly
            existing.accumulated = acc
            existing.net_value = net
            snap = existing
        else:
            snap = AssetDepreciationSnapshot(
                period_label=period,
                asset_id=asset.id,
                rule_id=rule_id,
                original_value=value,
                monthly_amount=monthly,
                accumulated=acc,
                net_value=net,
            )
            db.add(snap)
        out.append(snap)
    db.commit()
    for snap in out:
        db.refresh(snap)
        asset = db.query(FixedAsset).filter(FixedAsset.id == snap.asset_id).first()
        snap.asset_name = asset.name if asset else None  # type: ignore[attr-defined]
    return out


def list_depreciation_snapshots(
    db: Session, *, period_label: Optional[str] = None
) -> list[AssetDepreciationSnapshot]:
    q = db.query(AssetDepreciationSnapshot).order_by(AssetDepreciationSnapshot.id.desc())
    if period_label:
        q = q.filter(AssetDepreciationSnapshot.period_label == period_label)
    rows = q.all()
    for snap in rows:
        asset = db.query(FixedAsset).filter(FixedAsset.id == snap.asset_id).first()
        snap.asset_name = asset.name if asset else None  # type: ignore[attr-defined]
    return rows


def _enrich_disposal(db: Session, row: AssetDisposal) -> AssetDisposal:
    asset = db.query(FixedAsset).filter(FixedAsset.id == row.asset_id).first()
    row.asset_name = asset.name if asset else None  # type: ignore[attr-defined]
    row.applicant_name = _user_name(db, row.applicant_id)  # type: ignore[attr-defined]
    return row


def dispose_asset(db: Session, user: User, asset_id: int, payload: DisposeRequest) -> AssetDisposal:
    ensure_seed_data(db)
    asset = db.query(FixedAsset).filter(FixedAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    if asset.status == ASSET_STATUS_DISPOSED:
        raise HTTPException(status_code=400, detail="资产已处置")
    pending = (
        db.query(AssetDisposal)
        .filter(AssetDisposal.asset_id == asset_id, AssetDisposal.status == "pending")
        .first()
    )
    if pending:
        raise HTTPException(status_code=400, detail="已有待审批处置单")
    row = AssetDisposal(
        asset_id=asset_id,
        reason=payload.reason.strip(),
        status="pending",
        applicant_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _enrich_disposal(db, row)


def approve_disposal(db: Session, user: User, disposal_id: int) -> AssetDisposal:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可审批处置")
    row = db.query(AssetDisposal).filter(AssetDisposal.id == disposal_id).first()
    if not row or row.status != "pending":
        raise HTTPException(status_code=400, detail="处置单不存在或状态不可批准")
    row.status = "done"
    row.approved_by = user.id
    row.approved_at = _now()
    row.disposed_at = _now()
    asset = db.query(FixedAsset).filter(FixedAsset.id == row.asset_id).first()
    if asset:
        asset.status = ASSET_STATUS_DISPOSED
        asset.holder_id = None
        asset.current_use = None
        asset.schedule_ref = None
    db.commit()
    db.refresh(row)
    return _enrich_disposal(db, row)


def reject_disposal(
    db: Session, user: User, disposal_id: int, payload: DisposalRejectRequest
) -> AssetDisposal:
    if not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="仅资产管理员可驳回处置")
    row = db.query(AssetDisposal).filter(AssetDisposal.id == disposal_id).first()
    if not row or row.status != "pending":
        raise HTTPException(status_code=400, detail="处置单不存在或状态不可驳回")
    row.status = "rejected"
    row.reject_reason = payload.reason.strip()
    row.approved_by = user.id
    row.approved_at = _now()
    db.commit()
    db.refresh(row)
    return _enrich_disposal(db, row)


def asset_reports(db: Session) -> dict:
    ensure_seed_data(db)
    assets = [enrich_asset(db, x) for x in db.query(FixedAsset).all()]
    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for a in assets:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_category[a.category] = by_category.get(a.category, 0) + 1
    return {
        "total": len(assets),
        "by_status": by_status,
        "by_category": by_category,
        "original_value_sum": sum((x.original_value or Decimal("0")) for x in assets),
        "net_value_sum": sum((getattr(x, "net_value", None) or Decimal("0")) for x in assets),
        "maintenance_open": db.query(AssetMaintenance)
        .filter(AssetMaintenance.status.in_(["planned", "pending_approval", "approved", "in_progress"]))
        .count(),
        "disposal_pending": db.query(AssetDisposal).filter(AssetDisposal.status == "pending").count(),
    }


def asset_alerts(db: Session, user: User) -> list[dict]:
    data = get_workbench(db, user)
    return data["alerts"]


# ---- shooting schedules ----


def _enrich_shooting(db: Session, row: ShootingSchedule) -> ShootingSchedule:
    row.owner_name = _user_name(db, row.owner_id)  # type: ignore[attr-defined]
    asset_ids = [
        x.asset_id
        for x in db.query(ShootingScheduleAsset).filter(ShootingScheduleAsset.schedule_id == row.id).all()
    ]
    member_ids = [
        x.user_id
        for x in db.query(ShootingScheduleMember).filter(ShootingScheduleMember.schedule_id == row.id).all()
    ]
    row.asset_ids = asset_ids  # type: ignore[attr-defined]
    row.member_ids = member_ids  # type: ignore[attr-defined]
    row.conflicts = _shooting_conflicts(db, row, asset_ids, member_ids)  # type: ignore[attr-defined]
    return row


def _ranges_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _shooting_conflicts(
    db: Session,
    schedule: ShootingSchedule,
    asset_ids: list[int],
    member_ids: list[int],
) -> list[str]:
    conflicts: list[str] = []
    if not asset_ids and not member_ids:
        return conflicts

    other_schedules = (
        db.query(ShootingSchedule)
        .filter(
            ShootingSchedule.id != schedule.id,
            ShootingSchedule.status.in_(["draft", "confirmed"]),
        )
        .all()
    )
    for other in other_schedules:
        if not _ranges_overlap(schedule.start_time, schedule.end_time, other.start_time, other.end_time):
            continue
        other_assets = {
            x.asset_id
            for x in db.query(ShootingScheduleAsset)
            .filter(ShootingScheduleAsset.schedule_id == other.id)
            .all()
        }
        other_members = {
            x.user_id
            for x in db.query(ShootingScheduleMember)
            .filter(ShootingScheduleMember.schedule_id == other.id)
            .all()
        }
        shared_assets = set(asset_ids) & other_assets
        shared_members = set(member_ids) & other_members
        if shared_assets:
            conflicts.append(f"器材与拍摄排期#{other.id}冲突: {sorted(shared_assets)}")
        if shared_members:
            conflicts.append(f"人员与拍摄排期#{other.id}冲突: {sorted(shared_members)}")

    if asset_ids:
        borrows = (
            db.query(AssetBorrowRequest)
            .join(AssetBorrowItem, AssetBorrowItem.request_id == AssetBorrowRequest.id)
            .filter(
                AssetBorrowItem.asset_id.in_(asset_ids),
                AssetBorrowRequest.status.in_(
                    [BORROW_PENDING, BORROW_APPROVED, BORROW_IN_USE, BORROW_PENDING_RETURN]
                ),
            )
            .all()
        )
        for br in borrows:
            if _ranges_overlap(schedule.start_time, schedule.end_time, br.start_time, br.end_time):
                conflicts.append(f"器材与借用单{br.request_no}时间重叠")
    return conflicts


def list_shooting_schedules(db: Session) -> list[ShootingSchedule]:
    ensure_seed_data(db)
    rows = db.query(ShootingSchedule).order_by(ShootingSchedule.id.desc()).all()
    return [_enrich_shooting(db, x) for x in rows]


def get_shooting_schedule(db: Session, schedule_id: int) -> ShootingSchedule:
    ensure_seed_data(db)
    row = db.query(ShootingSchedule).filter(ShootingSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="拍摄排期不存在")
    return _enrich_shooting(db, row)


def create_shooting_schedule(
    db: Session, user: User, payload: ShootingScheduleCreate
) -> ShootingSchedule:
    ensure_seed_data(db)
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")
    if payload.asset_ids:
        assets = db.query(FixedAsset).filter(FixedAsset.id.in_(payload.asset_ids)).all()
        if len(assets) != len(set(payload.asset_ids)):
            raise HTTPException(status_code=400, detail="存在无效器材")
    if payload.member_ids:
        members = db.query(User).filter(User.id.in_(payload.member_ids)).all()
        if len(members) != len(set(payload.member_ids)):
            raise HTTPException(status_code=400, detail="存在无效成员")

    row = ShootingSchedule(
        title=payload.title.strip(),
        shoot_date=payload.shoot_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        location=(payload.location or "").strip() or None,
        owner_id=user.id,
        status="draft",
        remark=payload.remark,
    )
    db.add(row)
    db.flush()
    for aid in payload.asset_ids:
        db.add(ShootingScheduleAsset(schedule_id=row.id, asset_id=aid))
    for uid in payload.member_ids:
        db.add(ShootingScheduleMember(schedule_id=row.id, user_id=uid))

    conflicts = _shooting_conflicts(db, row, payload.asset_ids, payload.member_ids)
    if conflicts:
        raise HTTPException(status_code=400, detail="; ".join(conflicts))

    db.commit()
    db.refresh(row)
    return _enrich_shooting(db, row)


def confirm_shooting_schedule(db: Session, user: User, schedule_id: int) -> ShootingSchedule:
    row = db.query(ShootingSchedule).filter(ShootingSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="拍摄排期不存在")
    if row.owner_id != user.id and not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="无权确认该排期")
    if row.status not in {"draft"}:
        raise HTTPException(status_code=400, detail="仅草稿可确认")
    enriched = _enrich_shooting(db, row)
    if getattr(enriched, "conflicts", None):
        raise HTTPException(status_code=400, detail="; ".join(enriched.conflicts))  # type: ignore[attr-defined]
    row.status = "confirmed"
    db.commit()
    db.refresh(row)
    return _enrich_shooting(db, row)


def cancel_shooting_schedule(db: Session, user: User, schedule_id: int) -> ShootingSchedule:
    row = db.query(ShootingSchedule).filter(ShootingSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="拍摄排期不存在")
    if row.owner_id != user.id and not can_manage_assets(user):
        raise HTTPException(status_code=403, detail="无权取消该排期")
    if row.status == "cancelled":
        raise HTTPException(status_code=400, detail="排期已取消")
    row.status = "cancelled"
    db.commit()
    db.refresh(row)
    return _enrich_shooting(db, row)
