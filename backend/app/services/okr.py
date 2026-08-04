"""
OKR 业务逻辑：制定、确认、更新关键结果进度、完成/终止。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import collect_data_scopes, widest_data_scope
from app.models.okr import (
    OKR_LEVELS,
    OKR_PERIODS,
    OKR_STATUS_ACTIVE,
    OKR_STATUS_COMPLETED,
    OKR_STATUS_PENDING,
    OKR_STATUS_TERMINATED,
    KeyResult,
    Okr,
)
from app.models.user import User
from app.schemas.okr import KeyResultCreate, KeyResultUpdate, OkrCreate, OkrUpdate


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return None
    return u.real_name or u.username


def _kr_progress(kr: KeyResult) -> int:
    if not kr.target_value or kr.target_value <= 0:
        return 0
    pct = float(kr.current_value or 0) * 100 / float(kr.target_value)
    return max(0, min(100, int(round(pct))))


def _recalc_okr_progress(okr: Okr) -> None:
    krs = list(okr.key_results or [])
    if not krs:
        okr.progress = 0
        return
    total_w = sum(max(1, kr.weight or 1) for kr in krs)
    score = sum(_kr_progress(kr) * max(1, kr.weight or 1) for kr in krs)
    okr.progress = int(round(score / total_w)) if total_w else 0


def enrich_okr(db: Session, okr: Okr) -> Okr:
    okr.owner_name = _user_name(db, okr.owner_id)  # type: ignore[attr-defined]
    okr.creator_name = _user_name(db, okr.creator_id)  # type: ignore[attr-defined]
    if okr.parent_id:
        parent = db.query(Okr).filter(Okr.id == okr.parent_id).first()
        okr.parent_title = parent.title if parent else None  # type: ignore[attr-defined]
    else:
        okr.parent_title = None  # type: ignore[attr-defined]
    okr.kr_count = len(okr.key_results or [])  # type: ignore[attr-defined]
    return okr


def enrich_kr(kr: KeyResult) -> KeyResult:
    kr.progress = _kr_progress(kr)  # type: ignore[attr-defined]
    return kr


def assert_can_view(user: User, okr: Okr) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes:
        return
    scope = widest_data_scope(collect_data_scopes(user))
    if scope == "company":
        return
    if okr.owner_id == user.id or okr.creator_id == user.id:
        return
    if scope == "department" and user.department_id and okr.department_id == user.department_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该 OKR")


def assert_can_operate(user: User, okr: Okr) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes:
        return
    if okr.owner_id == user.id or okr.creator_id == user.id:
        return
    if "middle_manager" in role_codes or "executive" in role_codes:
        return
    raise HTTPException(status_code=403, detail="无权操作该 OKR")


def create_okr(db: Session, user: User, payload: OkrCreate) -> Okr:
    if payload.level not in OKR_LEVELS:
        raise HTTPException(status_code=400, detail="无效的目标层级")
    if payload.period_type not in OKR_PERIODS:
        raise HTTPException(status_code=400, detail="无效的周期类型")

    parent = None
    if payload.level in {"department", "personal"} and not payload.parent_id:
        raise HTTPException(status_code=400, detail="部门/个人目标必须对齐上级目标")
    if payload.parent_id:
        parent = db.query(Okr).filter(Okr.id == payload.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="对齐目标不存在")
        if payload.level == "department" and parent.level != "company":
            raise HTTPException(status_code=400, detail="部门目标须对齐公司级目标")
        if payload.level == "personal" and parent.level not in {"department", "company"}:
            raise HTTPException(status_code=400, detail="个人目标须对齐部门或公司目标")
    elif payload.level == "company" and payload.parent_id:
        raise HTTPException(status_code=400, detail="公司级目标不能对齐上级")

    okr = Okr(
        title=payload.title.strip(),
        level=payload.level,
        period_type=payload.period_type,
        period_label=payload.period_label.strip(),
        status=OKR_STATUS_PENDING,
        owner_id=user.id,
        creator_id=user.id,
        department_id=user.department_id,
        parent_id=payload.parent_id,
        description=payload.description,
        remark=payload.remark,
        progress=0,
    )
    db.add(okr)
    db.flush()

    for i, kr_payload in enumerate(payload.key_results):
        db.add(
            KeyResult(
                okr_id=okr.id,
                title=kr_payload.title.strip(),
                target_value=kr_payload.target_value,
                current_value=kr_payload.current_value,
                unit=kr_payload.unit,
                weight=kr_payload.weight,
                sort_order=kr_payload.sort_order or i + 1,
                remark=kr_payload.remark,
            )
        )
    db.flush()
    db.refresh(okr)
    _recalc_okr_progress(okr)
    db.commit()
    db.refresh(okr)
    return enrich_okr(db, okr)


def update_okr(db: Session, user: User, okr_id: int, payload: OkrUpdate) -> Okr:
    okr = db.query(Okr).filter(Okr.id == okr_id).first()
    if not okr:
        raise HTTPException(status_code=404, detail="OKR 不存在")
    assert_can_view(user, okr)
    assert_can_operate(user, okr)
    if okr.status in {OKR_STATUS_COMPLETED, OKR_STATUS_TERMINATED}:
        raise HTTPException(status_code=400, detail="已结束目标不可编辑")

    data = payload.model_dump(exclude_unset=True)
    if "level" in data and data["level"] not in OKR_LEVELS:
        raise HTTPException(status_code=400, detail="无效的目标层级")
    if "period_type" in data and data["period_type"] not in OKR_PERIODS:
        raise HTTPException(status_code=400, detail="无效的周期类型")
    if "parent_id" in data and data["parent_id"]:
        if data["parent_id"] == okr.id:
            raise HTTPException(status_code=400, detail="不能对齐自己")
        parent = db.query(Okr).filter(Okr.id == data["parent_id"]).first()
        if not parent:
            raise HTTPException(status_code=400, detail="对齐目标不存在")

    for k, v in data.items():
        setattr(okr, k, v)
    db.commit()
    db.refresh(okr)
    return enrich_okr(db, okr)


def list_okrs(
    db: Session,
    user: User,
    *,
    status: Optional[str] = None,
    level: Optional[str] = None,
    period_label: Optional[str] = None,
    keyword: Optional[str] = None,
    scope_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    enrich: bool = True,
) -> tuple[int, list[Okr]]:
    q = db.query(Okr).options(joinedload(Okr.key_results))
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    scope = widest_data_scope(collect_data_scopes(user)) if not is_admin else "company"

    if scope_filter == "mine":
        q = q.filter(or_(Okr.owner_id == user.id, Okr.creator_id == user.id))
    elif not is_admin:
        if scope == "personal":
            q = q.filter(or_(Okr.owner_id == user.id, Okr.creator_id == user.id))
        elif scope == "department" and user.department_id:
            q = q.filter(
                or_(
                    Okr.department_id == user.department_id,
                    Okr.owner_id == user.id,
                    Okr.creator_id == user.id,
                )
            )

    if status:
        q = q.filter(Okr.status == status)
    if level:
        q = q.filter(Okr.level == level)
    if period_label:
        q = q.filter(Okr.period_label == period_label)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(Okr.title.ilike(like))

    total = q.count()
    items = (
        q.order_by(Okr.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    if not enrich:
        return total, items
    return total, [enrich_okr(db, x) for x in items]


def get_okr_detail(db: Session, user: User, okr_id: int) -> Okr:
    okr = (
        db.query(Okr)
        .options(joinedload(Okr.key_results))
        .filter(Okr.id == okr_id)
        .first()
    )
    if not okr:
        raise HTTPException(status_code=404, detail="OKR 不存在")
    assert_can_view(user, okr)
    okr.key_results = sorted(okr.key_results or [], key=lambda x: (x.sort_order, x.id))
    for kr in okr.key_results:
        enrich_kr(kr)
    return enrich_okr(db, okr)


def confirm_okr(db: Session, user: User, okr_id: int) -> Okr:
    okr = db.query(Okr).options(joinedload(Okr.key_results)).filter(Okr.id == okr_id).first()
    if not okr:
        raise HTTPException(status_code=404, detail="OKR 不存在")
    assert_can_operate(user, okr)
    if okr.status != OKR_STATUS_PENDING:
        raise HTTPException(status_code=400, detail="仅待确认目标可确认")
    if not (okr.key_results or []):
        raise HTTPException(status_code=400, detail="请先添加关键结果")
    okr.status = OKR_STATUS_ACTIVE
    db.commit()
    db.refresh(okr)
    return enrich_okr(db, okr)


def complete_okr(db: Session, user: User, okr_id: int) -> Okr:
    okr = db.query(Okr).options(joinedload(Okr.key_results)).filter(Okr.id == okr_id).first()
    if not okr:
        raise HTTPException(status_code=404, detail="OKR 不存在")
    assert_can_operate(user, okr)
    if okr.status not in {OKR_STATUS_ACTIVE, OKR_STATUS_PENDING}:
        raise HTTPException(status_code=400, detail="当前状态不可完成")
    _recalc_okr_progress(okr)
    okr.status = OKR_STATUS_COMPLETED
    db.commit()
    db.refresh(okr)
    return enrich_okr(db, okr)


def terminate_okr(db: Session, user: User, okr_id: int, reason: Optional[str] = None) -> Okr:
    okr = db.query(Okr).filter(Okr.id == okr_id).first()
    if not okr:
        raise HTTPException(status_code=404, detail="OKR 不存在")
    assert_can_operate(user, okr)
    if okr.status in {OKR_STATUS_COMPLETED, OKR_STATUS_TERMINATED}:
        raise HTTPException(status_code=400, detail="当前状态不可终止")
    okr.status = OKR_STATUS_TERMINATED
    if reason:
        okr.remark = ((okr.remark or "") + f"\n[终止] {reason}").strip()
    db.commit()
    db.refresh(okr)
    return enrich_okr(db, okr)


def add_key_result(db: Session, user: User, okr_id: int, payload: KeyResultCreate) -> KeyResult:
    okr = db.query(Okr).options(joinedload(Okr.key_results)).filter(Okr.id == okr_id).first()
    if not okr:
        raise HTTPException(status_code=404, detail="OKR 不存在")
    assert_can_operate(user, okr)
    if okr.status in {OKR_STATUS_COMPLETED, OKR_STATUS_TERMINATED}:
        raise HTTPException(status_code=400, detail="已结束目标不可添加关键结果")

    kr = KeyResult(
        okr_id=okr.id,
        title=payload.title.strip(),
        target_value=payload.target_value,
        current_value=payload.current_value,
        unit=payload.unit,
        weight=payload.weight,
        sort_order=payload.sort_order or len(okr.key_results or []) + 1,
        remark=payload.remark,
    )
    db.add(kr)
    db.flush()
    db.refresh(okr)
    _recalc_okr_progress(okr)
    db.commit()
    db.refresh(kr)
    return enrich_kr(kr)


def update_key_result(
    db: Session, user: User, okr_id: int, kr_id: int, payload: KeyResultUpdate
) -> KeyResult:
    okr = db.query(Okr).options(joinedload(Okr.key_results)).filter(Okr.id == okr_id).first()
    if not okr:
        raise HTTPException(status_code=404, detail="OKR 不存在")
    assert_can_operate(user, okr)
    if okr.status in {OKR_STATUS_COMPLETED, OKR_STATUS_TERMINATED}:
        raise HTTPException(status_code=400, detail="已结束目标不可更新")

    kr = (
        db.query(KeyResult)
        .filter(KeyResult.id == kr_id, KeyResult.okr_id == okr_id)
        .first()
    )
    if not kr:
        raise HTTPException(status_code=404, detail="关键结果不存在")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(kr, k, v)

    db.flush()
    db.refresh(okr)
    _recalc_okr_progress(okr)
    db.commit()
    db.refresh(kr)
    return enrich_kr(kr)


def okr_stats(db: Session, user: User, period_label: Optional[str] = None) -> dict:
    _, items = list_okrs(
        db, user, period_label=period_label, page=1, page_size=10000
    )
    _, mine_items = list_okrs(
        db, user, period_label=period_label, scope_filter="mine", page=1, page_size=10000
    )
    active_like = [x for x in items if x.status in {OKR_STATUS_PENDING, OKR_STATUS_ACTIVE}]
    avg = (
        int(round(sum(x.progress or 0 for x in active_like) / len(active_like)))
        if active_like
        else 0
    )
    unaligned = sum(
        1
        for x in items
        if x.level in {"department", "personal"} and not x.parent_id
    )
    risk_kr = sum(1 for x in items if (x.progress or 0) < 70 and x.status == OKR_STATUS_ACTIVE)
    return {
        "total": len(items),
        "pending": sum(1 for x in items if x.status == OKR_STATUS_PENDING),
        "active": sum(1 for x in items if x.status == OKR_STATUS_ACTIVE),
        "completed": sum(1 for x in items if x.status == OKR_STATUS_COMPLETED),
        "terminated": sum(1 for x in items if x.status == OKR_STATUS_TERMINATED),
        "mine": len(mine_items),
        "avg_progress": avg,
        "unaligned": unaligned,
        "company_count": sum(1 for x in items if x.level == "company"),
        "department_count": sum(1 for x in items if x.level == "department"),
        "personal_count": sum(1 for x in items if x.level == "personal"),
        "risk_count": risk_kr,
    }
