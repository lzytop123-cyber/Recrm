"""人事闭环：合同台账、转岗离职、假勤、工资条、看板。"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import user_can
from app.models.approval_flow import TASK_ACTIVE, ApprovalTask
from app.models.asset import FixedAsset
from app.models.customer import Customer
from app.models.department import Department
from app.models.employee_hr import EmployeeHistoryEvent
from app.models.hr import (
    CONTRACT_CANCELLED,
    CONTRACT_PENDING,
    CONTRACT_RENEWED,
    CONTRACT_SIGNED,
    CONTRACT_TERMINATED,
    HANDOVER_DONE,
    HANDOVER_OPEN,
    ITEM_ASSIGNED,
    ITEM_CONFIRMED,
    LEAVE_APPROVED,
    LEAVE_PENDING,
    LEAVE_REJECTED,
    PAYSLIP_CORRECTED,
    PAYSLIP_PUBLISHED,
    RESIGN_COMPLETED,
    RESIGN_HANDING,
    RESIGN_PENDING,
    RESIGN_REJECTED,
    TRANSFER_APPLIED,
    TRANSFER_APPROVED,
    TRANSFER_PENDING,
    TRANSFER_REJECTED,
    HrHandover,
    HrHandoverItem,
    HrLeaveBalance,
    HrLeaveRequest,
    HrPayslip,
    HrResignation,
    HrTransfer,
    LaborContract,
)
from app.models.lead import LEAD_STATUS_CONVERTED, LEAD_STATUS_LOST, LEAD_STATUS_RETURNED, Lead
from app.models.opportunity import OPP_STAGE_LOST, OPP_STAGE_WON, Opportunity
from app.models.performance import PerformanceAssessment, PerformanceCycle
from app.models.platform import Delegation
from app.models.project import TASK_STATUS_DONE, ProjectTask
from app.models.schedule import SCHEDULE_ACTIVE_STATUSES, Schedule
from app.models.ticket import TICKET_STATUS_CLOSED, TICKET_STATUS_COMPLETED, Ticket
from app.models.timesheet import Timesheet
from app.models.user import User
from app.schemas.hr import (
    HandoverAssignIn,
    LaborContractCreate,
    LaborContractRenew,
    LaborContractUpdate,
    LeaveBalancePatch,
    LeaveRequestCreate,
    PayslipCorrectIn,
    ResignationCreate,
    TransferCreate,
)

BALANCE_TYPES = {"annual", "sick", "personal"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_hr(user: User) -> bool:
    return user_can(user, "org:manage")


def _is_finance(user: User) -> bool:
    return user_can(user, "payment:view") or user_can(user, "kpi:cycle:manage") or _is_hr(user)


def _name(user: Optional[User]) -> Optional[str]:
    if user is None:
        return None
    return user.real_name or user.username


def _dept_name(db: Session, dept_id: Optional[int]) -> Optional[str]:
    if not dept_id:
        return None
    dept = db.query(Department).filter(Department.id == dept_id).first()
    return dept.name if dept else None


def _user(db: Session, user_id: int) -> User:
    row = db.query(User).filter(User.id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="员工不存在")
    return row


def _maybe_start(db: Session, actor: User, *, biz_type: str, biz_id: int, title: str, summary: str, department_id: Optional[int], deep_link: str, facts: Optional[dict] = None):
    from app.services import approval_flow

    if approval_flow.find_open_instance(db, biz_type, biz_id) is not None:
        raise HTTPException(status_code=409, detail="该单据审批进行中")
    if approval_flow.select_rule(db, biz_type, facts or {}) is None:
        return None
    return approval_flow.start_instance(
        db,
        biz_type=biz_type,
        biz_id=biz_id,
        initiator=actor,
        title=title,
        summary=summary,
        department_id=department_id,
        deep_link=deep_link,
        facts=facts or {},
        commit=False,
    )


def _enrich_contract(
    db: Session,
    row: LaborContract,
    *,
    attachment_name: Optional[str] = None,
    renew_pending_ids: Optional[set[int]] = None,
) -> LaborContract:
    emp = db.query(User).filter(User.id == row.employee_id).first()
    row.employee_name = _name(emp)  # type: ignore[attr-defined]
    row.department_id = emp.department_id if emp else None  # type: ignore[attr-defined]
    row.department_name = _dept_name(db, row.department_id)  # type: ignore[attr-defined]
    today = date.today()
    row.warn_kind = None  # type: ignore[attr-defined]
    row.days_left = None  # type: ignore[attr-defined]
    if row.status in (CONTRACT_SIGNED,) and row.end_date:
        left = (row.end_date - today).days
        row.days_left = left  # type: ignore[attr-defined]
        if 0 <= left <= 90:
            row.warn_kind = "contract"  # type: ignore[attr-defined]
    if row.trial_end:
        left = (row.trial_end - today).days
        if 0 <= left <= 30:
            row.warn_kind = row.warn_kind or "trial"  # type: ignore[attr-defined]
            if row.days_left is None:
                row.days_left = left  # type: ignore[attr-defined]
    path = (row.file_path or "").strip() or None
    row.attachment_path = path  # type: ignore[attr-defined]
    name = (attachment_name or "").strip() or None
    if not name and path:
        name = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or None
    row.attachment = name  # type: ignore[attr-defined]
    if renew_pending_ids is not None:
        row.renew_pending = row.id in renew_pending_ids  # type: ignore[attr-defined]
    else:
        child = (
            db.query(LaborContract.id)
            .filter(
                LaborContract.supersedes_id == row.id,
                LaborContract.status == CONTRACT_PENDING,
            )
            .first()
        )
        row.renew_pending = child is not None  # type: ignore[attr-defined]
    return row


def _pending_renew_supersede_ids(db: Session, contract_ids: list[int]) -> set[int]:
    if not contract_ids:
        return set()
    rows = (
        db.query(LaborContract.supersedes_id)
        .filter(
            LaborContract.supersedes_id.in_(contract_ids),
            LaborContract.status == CONTRACT_PENDING,
        )
        .all()
    )
    return {sid for (sid,) in rows if sid is not None}


def _sync_user_contract(user: User, row: LaborContract) -> None:
    if row.status not in (CONTRACT_SIGNED, CONTRACT_RENEWED):
        return
    user.contract_type = row.contract_type
    user.contract_start = row.start_date
    user.contract_end = row.end_date
    user.contract_status = "生效中" if (not row.end_date or row.end_date >= date.today()) else "已到期"


def list_contracts(
    db: Session,
    user: User,
    *,
    department_id: Optional[int] = None,
    status: Optional[str] = None,
    employee_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    q = db.query(LaborContract)
    if not _is_hr(user) and not user_can(user, "org:view"):
        q = q.filter(LaborContract.employee_id == user.id)
    if employee_id:
        q = q.filter(LaborContract.employee_id == employee_id)
    if status:
        q = q.filter(LaborContract.status == status)
    if department_id:
        q = q.join(User, User.id == LaborContract.employee_id).filter(User.department_id == department_id)
    total = q.count()
    rows = (
        q.order_by(LaborContract.end_date.is_(None), LaborContract.end_date.asc(), LaborContract.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pending_ids = _pending_renew_supersede_ids(db, [r.id for r in rows])
    return {
        "total": total,
        "items": [_enrich_contract(db, r, renew_pending_ids=pending_ids) for r in rows],
    }


def get_contract(db: Session, user: User, contract_id: int) -> LaborContract:
    row = db.query(LaborContract).filter(LaborContract.id == contract_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="合同不存在")
    if row.employee_id != user.id and not _is_hr(user) and not user_can(user, "org:view"):
        raise HTTPException(status_code=403, detail="无权查看该合同")
    return _enrich_contract(db, row)


def _resolve_contract_file_path(raw: dict) -> Optional[str]:
    """写入 file_path：优先 attachment_path，其次 file_path。"""
    if "attachment_path" in raw:
        return (raw.get("attachment_path") or "").strip() or None
    if "file_path" in raw:
        return (raw.get("file_path") or "").strip() or None
    return None


def create_contract(db: Session, user: User, payload: LaborContractCreate) -> LaborContract:
    if not _is_hr(user):
        raise HTTPException(status_code=403, detail="无权维护劳动合同")
    emp = _user(db, payload.employee_id)
    raw = payload.model_dump(exclude_unset=True)
    file_path = _resolve_contract_file_path(raw)
    if file_path is None and "attachment_path" not in raw and "file_path" not in raw:
        file_path = None
    row = LaborContract(
        employee_id=payload.employee_id,
        contract_type=payload.contract_type,
        signed_on=payload.signed_on,
        start_date=payload.start_date,
        end_date=payload.end_date,
        trial_start=payload.trial_start,
        trial_end=payload.trial_end,
        status=payload.status,
        file_path=file_path,
        remark=payload.remark,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    _sync_user_contract(emp, row)
    db.commit()
    db.refresh(row)
    return _enrich_contract(db, row, attachment_name=payload.attachment)


def _mark_superseded_renewed(db: Session, row: LaborContract) -> None:
    """新合同已生效时，把被替代的旧合同标为 renewed。"""
    if row.status != CONTRACT_SIGNED or not row.supersedes_id:
        return
    old = db.query(LaborContract).filter(LaborContract.id == row.supersedes_id).first()
    if old and old.status != CONTRACT_RENEWED:
        old.status = CONTRACT_RENEWED


def update_contract(db: Session, user: User, contract_id: int, payload: LaborContractUpdate) -> LaborContract:
    if not _is_hr(user):
        raise HTTPException(status_code=403, detail="无权维护劳动合同")
    row = db.query(LaborContract).filter(LaborContract.id == contract_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="合同不存在")
    data = payload.model_dump(exclude_unset=True)
    attachment_name = data.pop("attachment", None)
    if "attachment_path" in data or "file_path" in data:
        row.file_path = _resolve_contract_file_path(data)
    data.pop("attachment_path", None)
    data.pop("file_path", None)
    for k, v in data.items():
        setattr(row, k, v)
    _mark_superseded_renewed(db, row)
    emp = _user(db, row.employee_id)
    _sync_user_contract(emp, row)
    db.commit()
    db.refresh(row)
    return _enrich_contract(db, row, attachment_name=attachment_name)


def renew_contract(db: Session, user: User, contract_id: int, payload: LaborContractRenew) -> LaborContract:
    if not _is_hr(user):
        raise HTTPException(status_code=403, detail="无权发起续签")
    old = db.query(LaborContract).filter(LaborContract.id == contract_id).first()
    if not old:
        raise HTTPException(status_code=404, detail="合同不存在")
    if old.status != CONTRACT_SIGNED:
        raise HTTPException(status_code=409, detail="仅已签合同可续签")
    pending = (
        db.query(LaborContract)
        .filter(
            LaborContract.supersedes_id == old.id,
            LaborContract.status == CONTRACT_PENDING,
        )
        .first()
    )
    if pending:
        raise HTTPException(status_code=409, detail="该合同续签审批进行中")
    from app.services import approval_flow

    needs_approval = approval_flow.select_rule(db, "labor_contract_renew", {}) is not None
    emp = _user(db, old.employee_id)
    raw = payload.model_dump(exclude_unset=True)
    new = LaborContract(
        employee_id=old.employee_id,
        contract_type=payload.contract_type or old.contract_type,
        signed_on=payload.signed_on,
        start_date=payload.start_date,
        end_date=payload.end_date,
        trial_start=None,
        trial_end=None,
        status=CONTRACT_PENDING if needs_approval else CONTRACT_SIGNED,
        file_path=_resolve_contract_file_path(raw) if ("attachment_path" in raw or "file_path" in raw) else payload.file_path,
        version=old.version + 1,
        supersedes_id=old.id,
        remark=payload.remark,
        created_by=user.id,
    )
    db.add(new)
    db.flush()
    if needs_approval:
        _maybe_start(
            db,
            user,
            biz_type="labor_contract_renew",
            biz_id=new.id,
            title=f"劳动合同续签 · {_name(emp)}",
            summary=f"续签至 {payload.end_date or '无固定期限'}",
            department_id=emp.department_id,
            deep_link=f"/hr/contracts/{new.id}",
        )
    else:
        old.status = CONTRACT_RENEWED
        _sync_user_contract(emp, new)
    _mark_superseded_renewed(db, new)
    db.commit()
    db.refresh(new)
    return _enrich_contract(db, new)


def list_expiring(db: Session, user: User, *, days: int = 90) -> dict:
    if not _is_hr(user) and not user_can(user, "org:view"):
        raise HTTPException(status_code=403, detail="无权查看到期预警")
    today = date.today()
    until = today + timedelta(days=days)
    rows = (
        db.query(LaborContract)
        .filter(
            LaborContract.status == CONTRACT_SIGNED,
            LaborContract.end_date.isnot(None),
            LaborContract.end_date >= today,
            LaborContract.end_date <= until,
        )
        .order_by(LaborContract.end_date.asc())
        .all()
    )
    trial = (
        db.query(LaborContract)
        .filter(
            LaborContract.status == CONTRACT_SIGNED,
            LaborContract.trial_end.isnot(None),
            LaborContract.trial_end >= today,
            LaborContract.trial_end <= today + timedelta(days=30),
        )
        .all()
    )
    seen = {r.id for r in rows}
    items_rows = list(rows)
    for r in trial:
        if r.id not in seen:
            items_rows.append(r)
    pending_ids = _pending_renew_supersede_ids(db, [r.id for r in items_rows])
    items = [_enrich_contract(db, r, renew_pending_ids=pending_ids) for r in items_rows]
    items.sort(key=lambda x: x.days_left if x.days_left is not None else 9999)
    return {"total": len(items), "items": items}


def contract_file_path(db: Session, user: User, contract_id: int) -> str:
    row = get_contract(db, user, contract_id)
    if not row.file_path:
        raise HTTPException(status_code=404, detail="未上传扫描件")
    return row.file_path


def on_contract_renew_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    row = db.query(LaborContract).filter(LaborContract.id == instance.biz_id).first()
    if not row:
        return
    if not approved:
        row.status = CONTRACT_CANCELLED
        tag = "续签撤回" if withdrawn else "续签驳回"
        note = (row.remark or "").strip()
        row.remark = f"{note}｜{tag}".lstrip("｜") if note else tag
        return
    row.status = CONTRACT_SIGNED
    _mark_superseded_renewed(db, row)
    emp = db.query(User).filter(User.id == row.employee_id).first()
    if emp:
        _sync_user_contract(emp, row)


def _enrich_transfer(db: Session, row: HrTransfer) -> HrTransfer:
    emp = db.query(User).filter(User.id == row.employee_id).first()
    row.employee_name = _name(emp)  # type: ignore[attr-defined]
    return row


def list_transfers(db: Session, user: User, *, status: Optional[str] = None, page: int = 1, page_size: int = 20) -> dict:
    q = db.query(HrTransfer)
    if not _is_hr(user) and not user_can(user, "org:view"):
        q = q.filter(HrTransfer.employee_id == user.id)
    if status:
        q = q.filter(HrTransfer.status == status)
    total = q.count()
    rows = q.order_by(HrTransfer.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [_enrich_transfer(db, r) for r in rows]}


def get_transfer(db: Session, user: User, transfer_id: int) -> HrTransfer:
    row = db.query(HrTransfer).filter(HrTransfer.id == transfer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="转岗单不存在")
    if row.employee_id != user.id and not _is_hr(user) and not user_can(user, "org:view"):
        raise HTTPException(status_code=403, detail="无权查看")
    return _enrich_transfer(db, row)


def _apply_transfer(db: Session, row: HrTransfer) -> None:
    emp = _user(db, row.employee_id)
    prev_title = emp.job_title
    emp.department_id = row.to_department_id
    if row.job_title:
        emp.job_title = row.job_title
    db.add(
        EmployeeHistoryEvent(
            user_id=emp.id,
            event_type="transfer",
            title=f"转岗 · {emp.job_title or '岗位调整'}",
            detail=f"原岗位 {prev_title or '—'} → {emp.job_title or '—'}",
            occurred_at=_now(),
        )
    )
    row.status = TRANSFER_APPLIED


def create_transfer(db: Session, user: User, payload: TransferCreate) -> HrTransfer:
    if not _is_hr(user) and payload.employee_id != user.id:
        raise HTTPException(status_code=403, detail="只能给本人或由人事发起转岗")
    emp = _user(db, payload.employee_id)
    row = HrTransfer(
        employee_id=emp.id,
        from_department_id=emp.department_id,
        to_department_id=payload.to_department_id,
        effective_on=payload.effective_on,
        reason=payload.reason,
        job_title=payload.job_title,
        status=TRANSFER_PENDING,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    inst = _maybe_start(
        db,
        user,
        biz_type="hr_transfer",
        biz_id=row.id,
        title=f"转岗申请 · {_name(emp)}",
        summary=payload.reason,
        department_id=emp.department_id,
        deep_link=f"/hr/transfers/{row.id}",
    )
    if inst is None:
        _apply_transfer(db, row)
    else:
        row.approval_instance_id = inst.id
    db.commit()
    db.refresh(row)
    return _enrich_transfer(db, row)


def on_transfer_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    row = db.query(HrTransfer).filter(HrTransfer.id == instance.biz_id).first()
    if not row:
        return
    if not approved:
        row.status = TRANSFER_REJECTED
        return
    row.status = TRANSFER_APPROVED
    _apply_transfer(db, row)


def _scan_open_items(db: Session, employee_id: int) -> list[dict]:
    items: list[dict] = []
    leads = (
        db.query(Lead)
        .filter(
            Lead.owner_id == employee_id,
            Lead.status.notin_([LEAD_STATUS_CONVERTED, LEAD_STATUS_LOST, LEAD_STATUS_RETURNED]),
        )
        .all()
    )
    items.extend({"kind": "lead", "ref_id": x.id, "title": f"线索 {x.name}"} for x in leads)
    customers = db.query(Customer).filter(Customer.owner_id == employee_id).all()
    items.extend({"kind": "customer", "ref_id": x.id, "title": f"客户 {x.name}"} for x in customers)
    opps = (
        db.query(Opportunity)
        .filter(
            Opportunity.owner_id == employee_id,
            Opportunity.stage.notin_([OPP_STAGE_WON, OPP_STAGE_LOST]),
        )
        .all()
    )
    items.extend({"kind": "opportunity", "ref_id": x.id, "title": f"商机 {x.title}"} for x in opps)
    tasks = (
        db.query(ProjectTask)
        .filter(ProjectTask.assignee_id == employee_id, ProjectTask.status != TASK_STATUS_DONE)
        .all()
    )
    items.extend({"kind": "task", "ref_id": x.id, "title": f"任务 {x.title}"} for x in tasks)
    tickets = (
        db.query(Ticket)
        .filter(
            Ticket.assignee_id == employee_id,
            Ticket.status.notin_([TICKET_STATUS_COMPLETED, TICKET_STATUS_CLOSED]),
        )
        .all()
    )
    items.extend({"kind": "ticket", "ref_id": x.id, "title": f"工单 {x.title}"} for x in tickets)
    assets = db.query(FixedAsset).filter(FixedAsset.holder_id == employee_id).all()
    items.extend({"kind": "asset", "ref_id": x.id, "title": f"资产 {x.name}"} for x in assets)
    approvals = (
        db.query(ApprovalTask)
        .filter(ApprovalTask.assignee_id == employee_id, ApprovalTask.status == TASK_ACTIVE)
        .all()
    )
    items.extend({"kind": "approval", "ref_id": x.id, "title": f"审批 {x.name}"} for x in approvals)
    schedules = (
        db.query(Schedule)
        .filter(Schedule.employee_id == employee_id, Schedule.status.in_(SCHEDULE_ACTIVE_STATUSES))
        .all()
    )
    items.extend({"kind": "schedule", "ref_id": x.id, "title": f"排期 {x.title}"} for x in schedules)
    return items


def _enrich_resignation(db: Session, row: HrResignation) -> HrResignation:
    emp = db.query(User).filter(User.id == row.employee_id).first()
    row.employee_name = _name(emp)  # type: ignore[attr-defined]
    ho = db.query(HrHandover).filter(HrHandover.resignation_id == row.id).first()
    row.handover_id = ho.id if ho else None  # type: ignore[attr-defined]
    return row


def _snapshot_handover(db: Session, resignation: HrResignation) -> HrHandover:
    ho = HrHandover(resignation_id=resignation.id, employee_id=resignation.employee_id, status=HANDOVER_OPEN)
    db.add(ho)
    db.flush()
    for it in _scan_open_items(db, resignation.employee_id):
        db.add(HrHandoverItem(handover_id=ho.id, kind=it["kind"], ref_id=it["ref_id"], title=it["title"]))
    return ho


def create_resignation(db: Session, user: User, payload: ResignationCreate) -> HrResignation:
    if not _is_hr(user) and payload.employee_id != user.id:
        raise HTTPException(status_code=403, detail="只能给本人或由人事发起离职")
    emp = _user(db, payload.employee_id)
    row = HrResignation(
        employee_id=emp.id,
        last_working_day=payload.last_working_day,
        reason=payload.reason,
        status=RESIGN_PENDING,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    inst = _maybe_start(
        db,
        user,
        biz_type="hr_resignation",
        biz_id=row.id,
        title=f"离职申请 · {_name(emp)}",
        summary=payload.reason,
        department_id=emp.department_id,
        deep_link=f"/hr/resignations/{row.id}",
    )
    if inst is None:
        row.status = RESIGN_HANDING
        _snapshot_handover(db, row)
    else:
        row.approval_instance_id = inst.id
    db.commit()
    db.refresh(row)
    return _enrich_resignation(db, row)


def list_resignations(db: Session, user: User, *, status: Optional[str] = None, page: int = 1, page_size: int = 20) -> dict:
    q = db.query(HrResignation)
    if not _is_hr(user) and not user_can(user, "org:view"):
        q = q.filter(HrResignation.employee_id == user.id)
    if status:
        q = q.filter(HrResignation.status == status)
    total = q.count()
    rows = q.order_by(HrResignation.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [_enrich_resignation(db, r) for r in rows]}


def get_resignation(db: Session, user: User, resignation_id: int) -> HrResignation:
    row = db.query(HrResignation).filter(HrResignation.id == resignation_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="离职单不存在")
    if row.employee_id != user.id and not _is_hr(user) and not user_can(user, "org:view"):
        raise HTTPException(status_code=403, detail="无权查看")
    return _enrich_resignation(db, row)


def on_resignation_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    row = db.query(HrResignation).filter(HrResignation.id == instance.biz_id).first()
    if not row:
        return
    if not approved:
        row.status = RESIGN_REJECTED
        return
    row.status = RESIGN_HANDING
    if db.query(HrHandover).filter(HrHandover.resignation_id == row.id).first() is None:
        _snapshot_handover(db, row)


def get_handover(db: Session, user: User, handover_id: int) -> HrHandover:
    ho = (
        db.query(HrHandover)
        .options(joinedload(HrHandover.items))
        .filter(HrHandover.id == handover_id)
        .first()
    )
    if not ho:
        raise HTTPException(status_code=404, detail="交接单不存在")
    if ho.employee_id != user.id and not _is_hr(user) and not user_can(user, "org:view"):
        item_assignee = any(it.assignee_id == user.id for it in ho.items)
        if not item_assignee:
            raise HTTPException(status_code=403, detail="无权查看")
    open_now = _scan_open_items(db, ho.employee_id)
    ho.open_items = open_now  # type: ignore[attr-defined]
    all_confirmed = bool(ho.items) and all(it.kind == "asset" or it.status == ITEM_CONFIRMED for it in ho.items)
    leftover = [x for x in open_now if not any(it.kind == x["kind"] and it.ref_id == x["ref_id"] and it.status == ITEM_CONFIRMED for it in ho.items)]
    ho.can_complete = ho.status == HANDOVER_OPEN and all_confirmed and not leftover and not any(x["kind"] == "asset" for x in open_now)  # type: ignore[attr-defined]
    if not ho.items and not open_now:
        ho.can_complete = ho.status == HANDOVER_OPEN  # type: ignore[attr-defined]
    return ho


def assign_handover_item(db: Session, user: User, handover_id: int, item_id: int, payload: HandoverAssignIn) -> HrHandover:
    ho = get_handover(db, user, handover_id)
    if ho.status != HANDOVER_OPEN:
        raise HTTPException(status_code=400, detail="交接单已完成，不能修改")
    if not _is_hr(user) and ho.employee_id != user.id:
        raise HTTPException(status_code=403, detail="无权指定接收人")
    item = next((x for x in ho.items if x.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="交接项不存在")
    if item.kind == "asset":
        raise HTTPException(status_code=400, detail="资产请走归还，不能转交")
    recipient = _user(db, payload.assignee_id)
    if recipient.id == ho.employee_id or not recipient.is_active or recipient.employment_status == "离职":
        raise HTTPException(status_code=400, detail="接收人必须是其他在职且账号启用的员工")
    item.assignee_id = payload.assignee_id
    item.status = ITEM_ASSIGNED
    db.commit()
    return get_handover(db, user, handover_id)


def confirm_handover_item(db: Session, user: User, handover_id: int, item_id: int) -> HrHandover:
    ho = get_handover(db, user, handover_id)
    if ho.status != HANDOVER_OPEN:
        raise HTTPException(status_code=400, detail="交接单已完成，不能修改")
    item = next((x for x in ho.items if x.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="交接项不存在")
    if item.assignee_id != user.id and not _is_hr(user):
        raise HTTPException(status_code=403, detail="仅接收人可确认")
    if item.status != ITEM_ASSIGNED and item.kind != "asset":
        raise HTTPException(status_code=400, detail="请先指定接收人")
    item.status = ITEM_CONFIRMED
    item.confirmed_at = _now()
    db.commit()
    return get_handover(db, user, handover_id)


def _apply_item(db: Session, item: HrHandoverItem) -> None:
    aid = item.assignee_id
    if not aid:
        return
    if item.kind == "lead":
        row = db.query(Lead).filter(Lead.id == item.ref_id).first()
        if row:
            row.owner_id = aid
    elif item.kind == "customer":
        row = db.query(Customer).filter(Customer.id == item.ref_id).first()
        if row:
            row.owner_id = aid
    elif item.kind == "opportunity":
        row = db.query(Opportunity).filter(Opportunity.id == item.ref_id).first()
        if row:
            row.owner_id = aid
    elif item.kind == "task":
        row = db.query(ProjectTask).filter(ProjectTask.id == item.ref_id).first()
        if row:
            row.assignee_id = aid
    elif item.kind == "ticket":
        row = db.query(Ticket).filter(Ticket.id == item.ref_id).first()
        if row:
            row.assignee_id = aid
    elif item.kind == "schedule":
        row = db.query(Schedule).filter(Schedule.id == item.ref_id).first()
        if row:
            row.employee_id = aid


def complete_handover(db: Session, user: User, handover_id: int) -> HrHandover:
    ho = get_handover(db, user, handover_id)
    if not ho.can_complete:  # type: ignore[attr-defined]
        raise HTTPException(status_code=400, detail="未完结事项未清完，不能完成交接")
    if not _is_hr(user):
        raise HTTPException(status_code=403, detail="需部门负责人/人事签字完成")
    for item in ho.items:
        _apply_item(db, item)
    emp = _user(db, ho.employee_id)
    emp.is_active = False
    emp.employment_status = "离职"
    db.query(Delegation).filter(Delegation.granter_id == emp.id, Delegation.status == "active").update(
        {"status": "revoked"}, synchronize_session=False
    )
    db.add(
        EmployeeHistoryEvent(
            user_id=emp.id,
            event_type="resign",
            title="办理离职",
            detail="交接完成，账号已禁用",
            occurred_at=_now(),
        )
    )
    ho.status = HANDOVER_DONE
    ho.signed_by = user.id
    ho.signed_at = _now()
    resign = db.query(HrResignation).filter(HrResignation.id == ho.resignation_id).first()
    if resign:
        resign.status = RESIGN_COMPLETED
    db.commit()
    return get_handover(db, user, handover_id)


def _enrich_leave(db: Session, row: HrLeaveRequest) -> HrLeaveRequest:
    emp = db.query(User).filter(User.id == row.employee_id).first()
    row.employee_name = _name(emp)  # type: ignore[attr-defined]
    return row


def _get_balance(db: Session, employee_id: int, leave_type: str, year: int) -> Optional[HrLeaveBalance]:
    return (
        db.query(HrLeaveBalance)
        .filter(
            HrLeaveBalance.employee_id == employee_id,
            HrLeaveBalance.leave_type == leave_type,
            HrLeaveBalance.year == year,
        )
        .first()
    )


def _deduct_balance(db: Session, req: HrLeaveRequest, *, restore: bool = False) -> None:
    if req.leave_type not in BALANCE_TYPES:
        return
    year = req.start_date.year
    bal = _get_balance(db, req.employee_id, req.leave_type, year)
    if bal is None:
        if restore:
            return
        raise HTTPException(status_code=400, detail="请先配置假期余额")
    delta = req.days if not restore else -req.days
    if not restore and bal.remaining < req.days:
        raise HTTPException(status_code=400, detail="假期余额不足")
    bal.used = (bal.used or Decimal("0")) + delta
    bal.remaining = (bal.quota or Decimal("0")) - bal.used


def create_leave_request(db: Session, user: User, payload: LeaveRequestCreate) -> HrLeaveRequest:
    employee_id = payload.employee_id or user.id
    if employee_id != user.id and not _is_hr(user):
        raise HTTPException(status_code=403, detail="只能给本人请假")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始")
    emp = _user(db, employee_id)
    row = HrLeaveRequest(
        employee_id=employee_id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        days=payload.days,
        reason=payload.reason,
        status=LEAVE_PENDING,
    )
    db.add(row)
    db.flush()
    inst = _maybe_start(
        db,
        user,
        biz_type="hr_leave",
        biz_id=row.id,
        title=f"假勤申请 · {_name(emp)} · {payload.leave_type}",
        summary=payload.reason or "",
        department_id=emp.department_id,
        deep_link=f"/hr/leave-requests/{row.id}",
    )
    if inst is None:
        _deduct_balance(db, row)
        row.status = LEAVE_APPROVED
    else:
        row.approval_instance_id = inst.id
    db.commit()
    db.refresh(row)
    return _enrich_leave(db, row)


def list_leave_requests(
    db: Session, user: User, *, status: Optional[str] = None, employee_id: Optional[int] = None, page: int = 1, page_size: int = 20
) -> dict:
    q = db.query(HrLeaveRequest)
    if not _is_hr(user) and not user_can(user, "org:view"):
        q = q.filter(HrLeaveRequest.employee_id == user.id)
    elif employee_id:
        q = q.filter(HrLeaveRequest.employee_id == employee_id)
    if status:
        q = q.filter(HrLeaveRequest.status == status)
    total = q.count()
    rows = q.order_by(HrLeaveRequest.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [_enrich_leave(db, r) for r in rows]}


def get_leave_request(db: Session, user: User, request_id: int) -> HrLeaveRequest:
    row = db.query(HrLeaveRequest).filter(HrLeaveRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="假勤申请不存在")
    if row.employee_id != user.id and not _is_hr(user) and not user_can(user, "org:view"):
        raise HTTPException(status_code=403, detail="无权查看")
    return _enrich_leave(db, row)


def on_leave_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    row = db.query(HrLeaveRequest).filter(HrLeaveRequest.id == instance.biz_id).first()
    if not row:
        return
    if not approved:
        if row.status == LEAVE_APPROVED:
            _deduct_balance(db, row, restore=True)
        row.status = LEAVE_REJECTED
        return
    if row.status != LEAVE_APPROVED:
        _deduct_balance(db, row)
        row.status = LEAVE_APPROVED


def list_leave_balances(db: Session, user: User, *, employee_id: Optional[int] = None, year: Optional[int] = None) -> list[HrLeaveBalance]:
    can_see_others = _is_hr(user) or user_can(user, "org:view")
    if employee_id is None and can_see_others:
        q = db.query(HrLeaveBalance)
        if year:
            q = q.filter(HrLeaveBalance.year == year)
        rows = q.order_by(HrLeaveBalance.employee_id.asc(), HrLeaveBalance.leave_type.asc()).all()
        ids = {r.employee_id for r in rows}
        names = {u.id: _name(u) for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}
        for r in rows:
            r.employee_name = names.get(r.employee_id)  # type: ignore[attr-defined]
        return rows
    target = employee_id or user.id
    if target != user.id and not can_see_others:
        raise HTTPException(status_code=403, detail="无权查看他人余额")
    q = db.query(HrLeaveBalance).filter(HrLeaveBalance.employee_id == target)
    if year:
        q = q.filter(HrLeaveBalance.year == year)
    rows = q.order_by(HrLeaveBalance.leave_type.asc()).all()
    emp = db.query(User).filter(User.id == target).first()
    for r in rows:
        r.employee_name = _name(emp)  # type: ignore[attr-defined]
    return rows


def patch_leave_balance(db: Session, user: User, balance_id: int, payload: LeaveBalancePatch) -> HrLeaveBalance:
    if not _is_hr(user):
        raise HTTPException(status_code=403, detail="无权调整假期余额")
    row = db.query(HrLeaveBalance).filter(HrLeaveBalance.id == balance_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="余额记录不存在")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    if "quota" in data or "used" in data:
        quota = row.quota if row.quota is not None else Decimal("0")
        used = row.used if row.used is not None else Decimal("0")
        row.remaining = quota - used
    db.commit()
    db.refresh(row)
    emp = db.query(User).filter(User.id == row.employee_id).first()
    row.employee_name = _name(emp)  # type: ignore[attr-defined]
    return row


def ensure_leave_balance(db: Session, user: User, employee_id: int, leave_type: str, year: int, quota: Decimal) -> HrLeaveBalance:
    if not _is_hr(user):
        raise HTTPException(status_code=403, detail="无权配置假期余额")
    row = _get_balance(db, employee_id, leave_type, year)
    if row is None:
        row = HrLeaveBalance(
            employee_id=employee_id,
            leave_type=leave_type,
            year=year,
            quota=quota,
            used=Decimal("0"),
            remaining=quota,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def attendance_monthly(db: Session, user: User, *, user_id: Optional[int] = None, month: Optional[str] = None) -> dict:
    from app.services.feishu_attendance import get_attendance_summary

    target = user_id or user.id
    if target != user.id and not _is_hr(user) and not user_can(user, "org:view"):
        raise HTTPException(status_code=403, detail="无权查看他人考勤")
    summary = get_attendance_summary(db, target, month)
    period = summary["month"]
    year, mon = [int(x) for x in period.split("-")]
    start = date(year, mon, 1)
    end = date(year + (1 if mon == 12 else 0), 1 if mon == 12 else mon + 1, 1) - timedelta(days=1)
    leaves = (
        db.query(HrLeaveRequest)
        .filter(
            HrLeaveRequest.employee_id == target,
            HrLeaveRequest.status == LEAVE_APPROVED,
            HrLeaveRequest.start_date <= end,
            HrLeaveRequest.end_date >= start,
        )
        .all()
    )
    overtime = sum((x.days for x in leaves if x.leave_type == "overtime"), Decimal("0"))
    field_days = sum(1 for x in leaves if x.leave_type == "field")
    makeup_days = sum(1 for x in leaves if x.leave_type == "makeup")
    return {
        "month": period,
        "user_id": target,
        "expected_days": summary["expected_days"],
        "actual_days": summary["actual_days"],
        "leave_days": summary["leave_days"],
        "overtime_days": overtime,
        "field_days": field_days,
        "makeup_days": makeup_days,
        "exception_pending": summary["exception_pending"],
        "approved_leaves": [_enrich_leave(db, x) for x in leaves],
    }


def _payslip_items(row: HrPayslip) -> list[dict]:
    if not row.items_json:
        return []
    try:
        data = json.loads(row.items_json)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _enrich_payslip(db: Session, row: HrPayslip) -> HrPayslip:
    emp = db.query(User).filter(User.id == row.employee_id).first()
    row.employee_name = _name(emp)  # type: ignore[attr-defined]
    row.items = _payslip_items(row)  # type: ignore[attr-defined]
    return row


def _can_see_payslip(user: User, row: HrPayslip) -> bool:
    return row.employee_id == user.id or _is_finance(user)


def list_my_payslips(db: Session, user: User) -> dict:
    rows = (
        db.query(HrPayslip)
        .filter(HrPayslip.employee_id == user.id, HrPayslip.status == PAYSLIP_PUBLISHED)
        .order_by(HrPayslip.period_label.desc(), HrPayslip.version.desc())
        .all()
    )
    return {"total": len(rows), "items": [_enrich_payslip(db, r) for r in rows]}


def list_payslips(db: Session, user: User, *, period_label: Optional[str] = None, page: int = 1, page_size: int = 20) -> dict:
    if not _is_finance(user):
        raise HTTPException(status_code=403, detail="无权查看全量工资条")
    q = db.query(HrPayslip).filter(HrPayslip.status == PAYSLIP_PUBLISHED)
    if period_label:
        q = q.filter(HrPayslip.period_label == period_label)
    total = q.count()
    rows = q.order_by(HrPayslip.period_label.desc(), HrPayslip.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [_enrich_payslip(db, r) for r in rows]}


def get_payslip(db: Session, user: User, payslip_id: int) -> HrPayslip:
    row = db.query(HrPayslip).filter(HrPayslip.id == payslip_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="工资条不存在")
    if not _can_see_payslip(user, row):
        raise HTTPException(status_code=403, detail="无权查看该工资条")
    return _enrich_payslip(db, row)


def download_payslip(db: Session, user: User, payslip_id: int) -> dict:
    row = get_payslip(db, user, payslip_id)
    lines = [
        f"工资条 {row.period_label}  v{row.version}",
        f"员工：{row.employee_name}",
        f"固定工资：{row.base_amount}",
        f"绩效工资：{row.performance_amount}",
        f"加减项：{row.adjustment_amount}",
        f"实发：{row.total_amount}",
    ]
    for it in row.items:  # type: ignore[attr-defined]
        lines.append(f"- {it.get('name')}: {it.get('amount')}")
    return {
        "expires_in": 300,
        "filename": f"payslip-{row.period_label}-v{row.version}.txt",
        "content": "\n".join(lines),
    }


def correct_payslip(db: Session, user: User, payslip_id: int, payload: PayslipCorrectIn) -> HrPayslip:
    if not _is_finance(user):
        raise HTTPException(status_code=403, detail="无权更正工资条")
    old = db.query(HrPayslip).filter(HrPayslip.id == payslip_id).first()
    if not old:
        raise HTTPException(status_code=404, detail="工资条不存在")
    base = payload.base_amount if payload.base_amount is not None else old.base_amount
    perf = payload.performance_amount if payload.performance_amount is not None else old.performance_amount
    adj = payload.adjustment_amount if payload.adjustment_amount is not None else old.adjustment_amount
    items = [x.model_dump() for x in payload.items] if payload.items is not None else _payslip_items(old)
    if payload.remark:
        items.append({"name": "更正说明", "amount": Decimal("0")})
    new = HrPayslip(
        employee_id=old.employee_id,
        cycle_id=old.cycle_id,
        period_label=old.period_label,
        version=old.version + 1,
        status=PAYSLIP_PUBLISHED,
        base_amount=base,
        performance_amount=perf,
        adjustment_amount=adj,
        total_amount=base + perf + adj,
        items_json=json.dumps(items, ensure_ascii=False, default=str),
        supersedes_id=old.id,
        published_at=_now(),
    )
    old.status = PAYSLIP_CORRECTED
    db.add(new)
    db.commit()
    db.refresh(new)
    return _enrich_payslip(db, new)


def generate_payslips_for_cycle(db: Session, cycle: PerformanceCycle) -> int:
    assessments = db.query(PerformanceAssessment).filter(PerformanceAssessment.cycle_id == cycle.id).all()
    created = 0
    for a in assessments:
        exists = (
            db.query(HrPayslip)
            .filter(HrPayslip.cycle_id == cycle.id, HrPayslip.employee_id == a.user_id, HrPayslip.status == PAYSLIP_PUBLISHED)
            .first()
        )
        if exists:
            continue
        perf = a.bonus_amount or Decimal("0")
        items = [{"name": "绩效工资", "amount": str(perf)}]
        if a.coefficient is not None:
            items.append({"name": "发放系数", "amount": str(a.coefficient)})
        db.add(
            HrPayslip(
                employee_id=a.user_id,
                cycle_id=cycle.id,
                period_label=cycle.period_label,
                version=1,
                status=PAYSLIP_PUBLISHED,
                base_amount=Decimal("0"),
                performance_amount=perf,
                adjustment_amount=Decimal("0"),
                total_amount=perf,
                items_json=json.dumps(items, ensure_ascii=False),
                published_at=_now(),
            )
        )
        created += 1
    return created


def dashboard(db: Session, user: User) -> dict:
    if not _is_hr(user) and not user_can(user, "org:view"):
        raise HTTPException(status_code=403, detail="无权查看人事看板")
    today = date.today()
    month_start = today.replace(day=1)
    headcount = db.query(User).filter(User.is_active.is_(True)).count()
    hired = (
        db.query(EmployeeHistoryEvent)
        .filter(EmployeeHistoryEvent.event_type == "hire", EmployeeHistoryEvent.occurred_at >= datetime.combine(month_start, datetime.min.time()).replace(tzinfo=timezone.utc))
        .count()
    )
    resigned = (
        db.query(EmployeeHistoryEvent)
        .filter(EmployeeHistoryEvent.event_type == "resign", EmployeeHistoryEvent.occurred_at >= datetime.combine(month_start, datetime.min.time()).replace(tzinfo=timezone.utc))
        .count()
    )

    def _expiring(days: int) -> int:
        until = today + timedelta(days=days)
        return (
            db.query(LaborContract)
            .filter(
                LaborContract.status == CONTRACT_SIGNED,
                LaborContract.end_date.isnot(None),
                LaborContract.end_date >= today,
                LaborContract.end_date <= until,
            )
            .count()
        )

    hours = db.query(Timesheet).filter(Timesheet.work_date >= month_start).all()
    total_hours = sum((x.hours or Decimal("0")) for x in hours)
    open_ho = db.query(HrHandover).filter(HrHandover.status == HANDOVER_OPEN).count()
    pays = db.query(HrPayslip).filter(HrPayslip.status == PAYSLIP_PUBLISHED, HrPayslip.period_label == today.strftime("%Y-%m")).all()
    payslip_total = sum((x.total_amount or Decimal("0")) for x in pays)
    return {
        "headcount": headcount,
        "hired_this_month": hired,
        "resigned_this_month": resigned,
        "contracts_expiring_90": _expiring(90),
        "contracts_expiring_30": _expiring(30),
        "contracts_expiring_7": _expiring(7),
        "timesheet_hours": total_hours,
        "open_handovers": open_ho,
        "payslip_total": payslip_total,
    }
