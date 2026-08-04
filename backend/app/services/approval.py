"""审批中心聚合：合同 / 资产借用 / 工时 / 到款复核 / 收款核销 / 项目验收 / 绩效申诉。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.rbac import user_can
from app.models.asset import BORROW_PENDING, AssetBorrowRequest
from app.models.contract import CONTRACT_STATUS_PENDING_APPROVAL, Contract
from app.models.department import Department
from app.models.finance import (
    ALLOCATION_STATUS_ACTIVE,
    ALLOCATION_STATUS_PENDING,
    ALLOCATION_STATUS_REJECTED,
    RECEIPT_STATUS_PENDING_REVIEW,
    Receipt,
    ReceiptAllocation,
    ReceivablePlan,
)
from app.models.performance import APPEAL_PENDING, PerformanceAppeal, PerformanceAssessment
from app.models.project import (
    ACCEPTANCE_APPROVAL_APPROVED,
    ACCEPTANCE_APPROVAL_PENDING,
    ACCEPTANCE_APPROVAL_REJECTED,
    FINANCE_CHECK_APPROVED,
    FINANCE_CHECK_PENDING,
    FINANCE_CHECK_REJECTED,
    PROJECT_STATUS_ACCEPTING,
    Project,
)
from app.models.timesheet import TIMESHEET_STATUS_SUBMITTED, Timesheet
from app.models.user import User
from app.schemas.approval import ApprovalFact, ApprovalItemOut, ApprovalListOut, ApprovalStatsOut
from app.services.asset import can_manage_assets
from app.services.project import can_approve_acceptance, can_review_finance_check
from app.services.timesheet import can_approve as can_approve_timesheet


def _user_name(db: Session, user_id: Optional[int]) -> str:
    if not user_id:
        return "—"
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return "—"
    return u.real_name or u.username


def _dept_name(db: Session, department_id: Optional[int]) -> str:
    if not department_id:
        return "—"
    d = db.query(Department).filter(Department.id == department_id).first()
    return d.name if d else "—"


def _can_approve_contract(user: User) -> bool:
    role_codes = {r.code for r in user.roles}
    return (
        user_can(user, "contract:manage")
        or "admin" in role_codes
        or "finance" in role_codes
        or "executive" in role_codes
    )


def _can_review_receipt(user: User) -> bool:
    return (
        user_can(user, "payment:confirm")
        or user_can(user, "payment:manage")
        or "admin" in {r.code for r in user.roles}
    )


def _can_resolve_appeal(user: User) -> bool:
    role_codes = {r.code for r in user.roles}
    return bool(role_codes & {"admin", "executive", "middle_manager", "hr", "hr_supervisor"})


def _item(
    *,
    id: str,
    type: str,
    category: str,
    source: str,
    source_id: str,
    title: str,
    applicant_name: str,
    department_name: str,
    submitted_at: Optional[datetime],
    status: str,
    status_label: str,
    node: str,
    summary: str,
    facts: list[ApprovalFact],
    deep_link: str,
    can_act: bool,
    actions: list[str],
    meta: Optional[dict[str, Any]] = None,
) -> ApprovalItemOut:
    return ApprovalItemOut(
        id=id,
        type=type,
        category=category,
        source=source,
        source_id=source_id,
        title=title,
        applicant_name=applicant_name,
        department_name=department_name,
        submitted_at=submitted_at,
        status=status,
        status_label=status_label,
        node=node,
        summary=summary,
        facts=facts,
        deep_link=deep_link,
        can_act=can_act,
        actions=actions,
        meta=meta or {},
    )


def _collect_pending_for_actor(db: Session, user: User) -> list[ApprovalItemOut]:
    items: list[ApprovalItemOut] = []

    if _can_approve_contract(user):
        rows = (
            db.query(Contract)
            .filter(Contract.status == CONTRACT_STATUS_PENDING_APPROVAL)
            .order_by(Contract.updated_at.desc())
            .limit(100)
            .all()
        )
        for c in rows:
            items.append(
                _item(
                    id=f"contract:{c.id}",
                    type="contract",
                    category="销售合同",
                    source="客户合同",
                    source_id=c.contract_no or str(c.id),
                    title=c.title or f"合同 #{c.id}",
                    applicant_name=_user_name(db, c.creator_id or c.owner_id),
                    department_name=_dept_name(db, c.department_id),
                    submitted_at=c.updated_at or c.created_at,
                    status=c.status,
                    status_label="待审批",
                    node="财务 / 管理层审批",
                    summary=f"金额 {c.amount or 0} {c.currency or 'CNY'}",
                    facts=[
                        ApprovalFact(label="合同编号", value=c.contract_no or "—"),
                        ApprovalFact(label="金额", value=f"{c.amount or 0} {c.currency or 'CNY'}"),
                    ],
                    deep_link=f"/contracts/{c.id}",
                    can_act=True,
                    actions=["approve", "reject", "open"],
                    meta={"entity_id": c.id},
                )
            )

    if can_manage_assets(user):
        rows = (
            db.query(AssetBorrowRequest)
            .filter(AssetBorrowRequest.status == BORROW_PENDING)
            .order_by(AssetBorrowRequest.id.desc())
            .limit(100)
            .all()
        )
        for b in rows:
            items.append(
                _item(
                    id=f"asset_borrow:{b.id}",
                    type="asset_borrow",
                    category="固定资产",
                    source="资产借用",
                    source_id=b.request_no or str(b.id),
                    title=b.purpose or f"借用申请 #{b.id}",
                    applicant_name=_user_name(db, b.applicant_id),
                    department_name="—",
                    submitted_at=b.created_at,
                    status=b.status,
                    status_label="待审批",
                    node="资产管理员审批",
                    summary=b.schedule_ref or "资产借用申请",
                    facts=[
                        ApprovalFact(label="用途", value=b.purpose or "—"),
                        ApprovalFact(label="档期", value=b.schedule_ref or "—"),
                    ],
                    deep_link="/assets",
                    can_act=True,
                    actions=["approve", "reject", "open"],
                    meta={"entity_id": b.id},
                )
            )

    if can_approve_timesheet(user):
        rows = (
            db.query(Timesheet)
            .filter(Timesheet.status == TIMESHEET_STATUS_SUBMITTED)
            .order_by(Timesheet.updated_at.desc())
            .limit(100)
            .all()
        )
        for t in rows:
            items.append(
                _item(
                    id=f"timesheet:{t.id}",
                    type="timesheet",
                    category="项目交付",
                    source="工时审批",
                    source_id=str(t.id),
                    title=f"{_user_name(db, t.user_id)} · {t.work_date}",
                    applicant_name=_user_name(db, t.user_id),
                    department_name=_dept_name(db, t.department_id),
                    submitted_at=t.updated_at or t.created_at,
                    status=t.status,
                    status_label="待审批",
                    node="主管审批工时",
                    summary=f"{t.hours}h · {(t.content or '')[:40]}",
                    facts=[
                        ApprovalFact(label="工时", value=f"{t.hours}h"),
                        ApprovalFact(label="日期", value=str(t.work_date)),
                    ],
                    deep_link=f"/timesheets/{t.id}",
                    can_act=True,
                    actions=["approve", "reject", "open"],
                    meta={"entity_id": t.id},
                )
            )

    if can_approve_acceptance(user):
        rows = (
            db.query(Project)
            .filter(
                Project.status == PROJECT_STATUS_ACCEPTING,
                Project.acceptance_approval_status == ACCEPTANCE_APPROVAL_PENDING,
            )
            .order_by(Project.acceptance_submitted_at.desc().nullslast(), Project.id.desc())
            .limit(100)
            .all()
        )
        for p in rows:
            items.append(
                _item(
                    id=f"project_acceptance:{p.id}",
                    type="project_acceptance",
                    category="项目交付",
                    source="内部验收",
                    source_id=p.project_no or str(p.id),
                    title=f"验收 {p.name}",
                    applicant_name=_user_name(db, p.acceptance_submitted_by or p.manager_id),
                    department_name=_dept_name(db, p.department_id),
                    submitted_at=p.acceptance_submitted_at or p.updated_at,
                    status=p.acceptance_approval_status,
                    status_label="待审批",
                    node="管理层 / 交付负责人审批",
                    summary=f"{p.acceptance_result or '—'} · {(p.acceptance_conclusion or '')[:40]}",
                    facts=[
                        ApprovalFact(label="验收结果", value=p.acceptance_result or "—"),
                        ApprovalFact(label="验收方式", value=p.acceptance_method or "—"),
                        ApprovalFact(label="附件", value=p.acceptance_attachment or "—"),
                    ],
                    deep_link=f"/projects/{p.id}",
                    can_act=True,
                    actions=["approve", "reject", "open"],
                    meta={"entity_id": p.id},
                )
            )

    if can_review_finance_check(user):
        rows = (
            db.query(Project)
            .filter(Project.finance_check_status == FINANCE_CHECK_PENDING)
            .order_by(Project.finance_check_submitted_at.desc().nullslast(), Project.id.desc())
            .limit(100)
            .all()
        )
        for p in rows:
            items.append(
                _item(
                    id=f"project_finance:{p.id}",
                    type="project_finance",
                    category="项目交付",
                    source="财务核对",
                    source_id=p.project_no or str(p.id),
                    title=f"财务核对 {p.name}",
                    applicant_name=_user_name(db, p.finance_check_submitted_by or p.manager_id),
                    department_name=_dept_name(db, p.department_id),
                    submitted_at=p.finance_check_submitted_at or p.updated_at,
                    status=p.finance_check_status,
                    status_label="待审批",
                    node="财务审批核对",
                    summary="结项前财务核对",
                    facts=[
                        ApprovalFact(label="项目编号", value=p.project_no or "—"),
                        ApprovalFact(label="验收结果", value=p.acceptance_result or "—"),
                    ],
                    deep_link=f"/projects/{p.id}",
                    can_act=True,
                    actions=["approve", "reject", "open"],
                    meta={"entity_id": p.id},
                )
            )

    if _can_review_receipt(user):
        rows = (
            db.query(Receipt)
            .filter(Receipt.status == RECEIPT_STATUS_PENDING_REVIEW)
            .order_by(Receipt.id.desc())
            .limit(100)
            .all()
        )
        for r in rows:
            items.append(
                _item(
                    id=f"receipt:{r.id}",
                    type="receipt",
                    category="销售合同",
                    source="到款认领",
                    source_id=r.receipt_no or str(r.id),
                    title=f"到款认领 {r.receipt_no or r.id}",
                    applicant_name=_user_name(db, r.submitted_by),
                    department_name=_dept_name(db, r.department_id),
                    submitted_at=r.created_at,
                    status=r.status,
                    status_label="待复核",
                    node="财务复核到账",
                    summary=f"¥{r.amount} · {r.payer_name or '—'}",
                    facts=[
                        ApprovalFact(label="金额", value=str(r.amount)),
                        ApprovalFact(label="付款方", value=r.payer_name or "—"),
                    ],
                    deep_link="/sales?tab=contracts",
                    can_act=True,
                    actions=["approve", "reject", "open"],
                    meta={"entity_id": r.id, "version": r.version, "contract_id": r.contract_id},
                )
            )

        alloc_rows = (
            db.query(ReceiptAllocation, Receipt, ReceivablePlan)
            .join(Receipt, Receipt.id == ReceiptAllocation.receipt_id)
            .join(ReceivablePlan, ReceivablePlan.id == ReceiptAllocation.receivable_plan_id)
            .filter(ReceiptAllocation.status == ALLOCATION_STATUS_PENDING)
            .order_by(ReceiptAllocation.id.desc())
            .limit(100)
            .all()
        )
        for a, r, plan in alloc_rows:
            items.append(
                _item(
                    id=f"allocation:{a.id}",
                    type="allocation",
                    category="销售合同",
                    source="收款核销",
                    source_id=r.receipt_no or str(a.id),
                    title=f"核销 {r.receipt_no or r.id} → {plan.title}",
                    applicant_name=_user_name(db, a.allocated_by),
                    department_name=_dept_name(db, r.department_id),
                    submitted_at=a.created_at or a.allocated_at,
                    status=a.status,
                    status_label="待审批",
                    node="财务审批核销",
                    summary=f"¥{a.amount} · {plan.title}",
                    facts=[
                        ApprovalFact(label="核销金额", value=str(a.amount)),
                        ApprovalFact(label="应收计划", value=plan.title),
                        ApprovalFact(label="收款单号", value=r.receipt_no or "—"),
                    ],
                    deep_link="/sales?tab=contracts",
                    can_act=True,
                    actions=["approve", "reject", "open"],
                    meta={
                        "entity_id": a.id,
                        "version": a.version,
                        "receipt_id": r.id,
                        "contract_id": r.contract_id,
                        "receivable_plan_id": plan.id,
                    },
                )
            )

    if _can_resolve_appeal(user):
        rows = (
            db.query(PerformanceAppeal, PerformanceAssessment)
            .join(
                PerformanceAssessment,
                PerformanceAssessment.id == PerformanceAppeal.assessment_id,
            )
            .filter(PerformanceAppeal.status == APPEAL_PENDING)
            .order_by(PerformanceAppeal.id.desc())
            .limit(100)
            .all()
        )
        for a, assess in rows:
            items.append(
                _item(
                    id=f"appeal:{a.id}",
                    type="appeal",
                    category="目标绩效",
                    source="绩效申诉",
                    source_id=str(a.id),
                    title=f"绩效申诉 #{a.id}",
                    applicant_name=_user_name(db, assess.user_id),
                    department_name=_dept_name(db, assess.department_id),
                    submitted_at=a.created_at,
                    status=a.status,
                    status_label="待处理",
                    node="综合管理复核",
                    summary=(a.reason or "")[:80] or "绩效申诉待处理",
                    facts=[
                        ApprovalFact(label="申诉分", value=str(a.request_score)),
                        ApprovalFact(label="原因", value=(a.reason or "—")[:40]),
                    ],
                    deep_link="/okrs",
                    can_act=True,
                    actions=["open"],
                    meta={"entity_id": a.id},
                )
            )

    items.sort(key=lambda x: x.submitted_at or datetime.min, reverse=True)
    return items


def _collect_initiated(db: Session, user: User) -> list[ApprovalItemOut]:
    items: list[ApprovalItemOut] = []

    rows = (
        db.query(Contract)
        .filter(
            Contract.status == CONTRACT_STATUS_PENDING_APPROVAL,
            Contract.creator_id == user.id,
        )
        .order_by(Contract.updated_at.desc())
        .limit(50)
        .all()
    )
    for c in rows:
        items.append(
            _item(
                id=f"contract:{c.id}",
                type="contract",
                category="销售合同",
                source="客户合同",
                source_id=c.contract_no or str(c.id),
                title=c.title or f"合同 #{c.id}",
                applicant_name=_user_name(db, user.id),
                department_name=_dept_name(db, c.department_id),
                submitted_at=c.updated_at or c.created_at,
                status=c.status,
                status_label="待审批",
                node="等待审批人处理",
                summary=f"金额 {c.amount or 0}",
                facts=[],
                deep_link=f"/contracts/{c.id}",
                can_act=False,
                actions=["open"],
                meta={"entity_id": c.id},
            )
        )

    rows = (
        db.query(AssetBorrowRequest)
        .filter(
            AssetBorrowRequest.status == BORROW_PENDING,
            AssetBorrowRequest.applicant_id == user.id,
        )
        .order_by(AssetBorrowRequest.id.desc())
        .limit(50)
        .all()
    )
    for b in rows:
        items.append(
            _item(
                id=f"asset_borrow:{b.id}",
                type="asset_borrow",
                category="固定资产",
                source="资产借用",
                source_id=b.request_no or str(b.id),
                title=b.purpose or f"借用申请 #{b.id}",
                applicant_name=_user_name(db, user.id),
                department_name="—",
                submitted_at=b.created_at,
                status=b.status,
                status_label="待审批",
                node="等待资产管理员",
                summary=b.schedule_ref or "",
                facts=[],
                deep_link="/assets",
                can_act=False,
                actions=["open"],
                meta={"entity_id": b.id},
            )
        )

    rows = (
        db.query(Timesheet)
        .filter(
            Timesheet.status == TIMESHEET_STATUS_SUBMITTED,
            Timesheet.user_id == user.id,
        )
        .order_by(Timesheet.updated_at.desc())
        .limit(50)
        .all()
    )
    for t in rows:
        items.append(
            _item(
                id=f"timesheet:{t.id}",
                type="timesheet",
                category="项目交付",
                source="工时审批",
                source_id=str(t.id),
                title=f"工时 {t.work_date}",
                applicant_name=_user_name(db, user.id),
                department_name=_dept_name(db, t.department_id),
                submitted_at=t.updated_at or t.created_at,
                status=t.status,
                status_label="待审批",
                node="等待主管审批",
                summary=f"{t.hours}h",
                facts=[],
                deep_link=f"/timesheets/{t.id}",
                can_act=False,
                actions=["open"],
                meta={"entity_id": t.id},
            )
        )

    rows = (
        db.query(Project)
        .filter(
            Project.acceptance_approval_status == ACCEPTANCE_APPROVAL_PENDING,
            Project.acceptance_submitted_by == user.id,
        )
        .order_by(Project.acceptance_submitted_at.desc().nullslast(), Project.id.desc())
        .limit(50)
        .all()
    )
    for p in rows:
        items.append(
            _item(
                id=f"project_acceptance:{p.id}",
                type="project_acceptance",
                category="项目交付",
                source="内部验收",
                source_id=p.project_no or str(p.id),
                title=f"验收 {p.name}",
                applicant_name=_user_name(db, user.id),
                department_name=_dept_name(db, p.department_id),
                submitted_at=p.acceptance_submitted_at or p.updated_at,
                status=p.acceptance_approval_status,
                status_label="待审批",
                node="等待验收审批",
                summary=p.acceptance_result or "",
                facts=[],
                deep_link=f"/projects/{p.id}",
                can_act=False,
                actions=["open"],
                meta={"entity_id": p.id},
            )
        )

    rows = (
        db.query(Project)
        .filter(
            Project.finance_check_status == FINANCE_CHECK_PENDING,
            Project.finance_check_submitted_by == user.id,
        )
        .order_by(Project.finance_check_submitted_at.desc().nullslast(), Project.id.desc())
        .limit(50)
        .all()
    )
    for p in rows:
        items.append(
            _item(
                id=f"project_finance:{p.id}",
                type="project_finance",
                category="项目交付",
                source="财务核对",
                source_id=p.project_no or str(p.id),
                title=f"财务核对 {p.name}",
                applicant_name=_user_name(db, user.id),
                department_name=_dept_name(db, p.department_id),
                submitted_at=p.finance_check_submitted_at or p.updated_at,
                status=p.finance_check_status,
                status_label="待审批",
                node="等待财务审批",
                summary="结项前财务核对",
                facts=[],
                deep_link=f"/projects/{p.id}",
                can_act=False,
                actions=["open"],
                meta={"entity_id": p.id},
            )
        )

    rows = (
        db.query(Receipt)
        .filter(
            Receipt.status == RECEIPT_STATUS_PENDING_REVIEW,
            Receipt.submitted_by == user.id,
        )
        .order_by(Receipt.id.desc())
        .limit(50)
        .all()
    )
    for r in rows:
        items.append(
            _item(
                id=f"receipt:{r.id}",
                type="receipt",
                category="销售合同",
                source="到款认领",
                source_id=r.receipt_no or str(r.id),
                title=f"到款认领 {r.receipt_no or r.id}",
                applicant_name=_user_name(db, user.id),
                department_name=_dept_name(db, r.department_id),
                submitted_at=r.created_at,
                status=r.status,
                status_label="待复核",
                node="等待财务复核",
                summary=f"¥{r.amount}",
                facts=[],
                deep_link="/sales?tab=contracts",
                can_act=False,
                actions=["open"],
                meta={"entity_id": r.id, "version": r.version},
            )
        )

    alloc_rows = (
        db.query(ReceiptAllocation, Receipt, ReceivablePlan)
        .join(Receipt, Receipt.id == ReceiptAllocation.receipt_id)
        .join(ReceivablePlan, ReceivablePlan.id == ReceiptAllocation.receivable_plan_id)
        .filter(
            ReceiptAllocation.status == ALLOCATION_STATUS_PENDING,
            ReceiptAllocation.allocated_by == user.id,
        )
        .order_by(ReceiptAllocation.id.desc())
        .limit(50)
        .all()
    )
    for a, r, plan in alloc_rows:
        items.append(
            _item(
                id=f"allocation:{a.id}",
                type="allocation",
                category="销售合同",
                source="收款核销",
                source_id=r.receipt_no or str(a.id),
                title=f"核销 {r.receipt_no or r.id} → {plan.title}",
                applicant_name=_user_name(db, user.id),
                department_name=_dept_name(db, r.department_id),
                submitted_at=a.created_at or a.allocated_at,
                status=a.status,
                status_label="待审批",
                node="等待财务审批",
                summary=f"¥{a.amount} · {plan.title}",
                facts=[],
                deep_link="/sales?tab=contracts",
                can_act=False,
                actions=["open"],
                meta={"entity_id": a.id, "version": a.version},
            )
        )

    rows = (
        db.query(PerformanceAppeal, PerformanceAssessment)
        .join(
            PerformanceAssessment,
            PerformanceAssessment.id == PerformanceAppeal.assessment_id,
        )
        .filter(
            PerformanceAppeal.status == APPEAL_PENDING,
            PerformanceAssessment.user_id == user.id,
        )
        .order_by(PerformanceAppeal.id.desc())
        .limit(50)
        .all()
    )
    for a, assess in rows:
        items.append(
            _item(
                id=f"appeal:{a.id}",
                type="appeal",
                category="目标绩效",
                source="绩效申诉",
                source_id=str(a.id),
                title=f"绩效申诉 #{a.id}",
                applicant_name=_user_name(db, user.id),
                department_name=_dept_name(db, assess.department_id),
                submitted_at=a.created_at,
                status=a.status,
                status_label="待处理",
                node="等待综合管理复核",
                summary=(a.reason or "")[:80],
                facts=[],
                deep_link="/okrs",
                can_act=False,
                actions=["open"],
                meta={"entity_id": a.id},
            )
        )

    items.sort(key=lambda x: x.submitted_at or datetime.min, reverse=True)
    return items


def _collect_processed(db: Session, user: User) -> list[ApprovalItemOut]:
    items: list[ApprovalItemOut] = []

    rows = (
        db.query(Contract)
        .filter(Contract.approved_by == user.id)
        .order_by(Contract.approved_at.desc())
        .limit(50)
        .all()
    )
    for c in rows:
        items.append(
            _item(
                id=f"contract:{c.id}:done",
                type="contract",
                category="销售合同",
                source="客户合同",
                source_id=c.contract_no or str(c.id),
                title=c.title or f"合同 #{c.id}",
                applicant_name=_user_name(db, c.creator_id or c.owner_id),
                department_name=_dept_name(db, c.department_id),
                submitted_at=c.approved_at or c.updated_at,
                status=c.status,
                status_label="已处理",
                node="审批完成",
                summary=f"状态 {c.status}",
                facts=[],
                deep_link=f"/contracts/{c.id}",
                can_act=False,
                actions=["open"],
                meta={"entity_id": c.id},
            )
        )

    rows = (
        db.query(AssetBorrowRequest)
        .filter(AssetBorrowRequest.approved_by == user.id)
        .order_by(AssetBorrowRequest.approved_at.desc())
        .limit(50)
        .all()
    )
    for b in rows:
        items.append(
            _item(
                id=f"asset_borrow:{b.id}:done",
                type="asset_borrow",
                category="固定资产",
                source="资产借用",
                source_id=b.request_no or str(b.id),
                title=b.purpose or f"借用申请 #{b.id}",
                applicant_name=_user_name(db, b.applicant_id),
                department_name="—",
                submitted_at=b.approved_at or b.created_at,
                status=b.status,
                status_label="已处理",
                node="借用审批完成",
                summary=b.status,
                facts=[],
                deep_link="/assets",
                can_act=False,
                actions=["open"],
                meta={"entity_id": b.id},
            )
        )

    rows = (
        db.query(Timesheet)
        .filter(Timesheet.approver_id == user.id)
        .order_by(Timesheet.approved_at.desc())
        .limit(50)
        .all()
    )
    for t in rows:
        items.append(
            _item(
                id=f"timesheet:{t.id}:done",
                type="timesheet",
                category="项目交付",
                source="工时审批",
                source_id=str(t.id),
                title=f"{_user_name(db, t.user_id)} · {t.work_date}",
                applicant_name=_user_name(db, t.user_id),
                department_name=_dept_name(db, t.department_id),
                submitted_at=t.approved_at or t.updated_at,
                status=t.status,
                status_label="已处理",
                node="工时审批完成",
                summary=f"{t.hours}h · {t.status}",
                facts=[],
                deep_link=f"/timesheets/{t.id}",
                can_act=False,
                actions=["open"],
                meta={"entity_id": t.id},
            )
        )

    rows = (
        db.query(Project)
        .filter(
            Project.acceptance_approved_by == user.id,
            Project.acceptance_approval_status.in_(
                [ACCEPTANCE_APPROVAL_APPROVED, ACCEPTANCE_APPROVAL_REJECTED]
            ),
        )
        .order_by(Project.acceptance_approved_at.desc().nullslast())
        .limit(50)
        .all()
    )
    for p in rows:
        label = (
            "已通过"
            if p.acceptance_approval_status == ACCEPTANCE_APPROVAL_APPROVED
            else "已驳回"
        )
        items.append(
            _item(
                id=f"project_acceptance:{p.id}:done",
                type="project_acceptance",
                category="项目交付",
                source="内部验收",
                source_id=p.project_no or str(p.id),
                title=f"验收 {p.name}",
                applicant_name=_user_name(db, p.acceptance_submitted_by or p.manager_id),
                department_name=_dept_name(db, p.department_id),
                submitted_at=p.acceptance_approved_at or p.updated_at,
                status=p.acceptance_approval_status,
                status_label=label,
                node="验收审批完成",
                summary=f"{p.acceptance_result or '—'} · {label}",
                facts=[],
                deep_link=f"/projects/{p.id}",
                can_act=False,
                actions=["open"],
                meta={"entity_id": p.id},
            )
        )

    rows = (
        db.query(Project)
        .filter(
            Project.finance_check_approved_by == user.id,
            Project.finance_check_status.in_(
                [FINANCE_CHECK_APPROVED, FINANCE_CHECK_REJECTED]
            ),
        )
        .order_by(Project.finance_check_approved_at.desc().nullslast())
        .limit(50)
        .all()
    )
    for p in rows:
        label = (
            "已通过" if p.finance_check_status == FINANCE_CHECK_APPROVED else "已驳回"
        )
        items.append(
            _item(
                id=f"project_finance:{p.id}:done",
                type="project_finance",
                category="项目交付",
                source="财务核对",
                source_id=p.project_no or str(p.id),
                title=f"财务核对 {p.name}",
                applicant_name=_user_name(db, p.finance_check_submitted_by or p.manager_id),
                department_name=_dept_name(db, p.department_id),
                submitted_at=p.finance_check_approved_at or p.updated_at,
                status=p.finance_check_status,
                status_label=label,
                node="财务核对完成",
                summary=label,
                facts=[],
                deep_link=f"/projects/{p.id}",
                can_act=False,
                actions=["open"],
                meta={"entity_id": p.id},
            )
        )

    rows = (
        db.query(Receipt)
        .filter(Receipt.confirmed_by == user.id)
        .order_by(Receipt.confirmed_at.desc())
        .limit(50)
        .all()
    )
    for r in rows:
        items.append(
            _item(
                id=f"receipt:{r.id}:done",
                type="receipt",
                category="销售合同",
                source="到款认领",
                source_id=r.receipt_no or str(r.id),
                title=f"到款认领 {r.receipt_no or r.id}",
                applicant_name=_user_name(db, r.submitted_by),
                department_name=_dept_name(db, r.department_id),
                submitted_at=r.confirmed_at or r.updated_at,
                status=r.status,
                status_label="已处理",
                node="到款复核完成",
                summary=f"¥{r.amount} · {r.status}",
                facts=[],
                deep_link="/sales?tab=contracts",
                can_act=False,
                actions=["open"],
                meta={"entity_id": r.id},
            )
        )

    alloc_rows = (
        db.query(ReceiptAllocation, Receipt, ReceivablePlan)
        .join(Receipt, Receipt.id == ReceiptAllocation.receipt_id)
        .join(ReceivablePlan, ReceivablePlan.id == ReceiptAllocation.receivable_plan_id)
        .filter(
            ReceiptAllocation.approved_by == user.id,
            ReceiptAllocation.status.in_(
                [ALLOCATION_STATUS_ACTIVE, ALLOCATION_STATUS_REJECTED]
            ),
        )
        .order_by(ReceiptAllocation.approved_at.desc())
        .limit(50)
        .all()
    )
    for a, r, plan in alloc_rows:
        label = "已通过" if a.status == ALLOCATION_STATUS_ACTIVE else "已驳回"
        items.append(
            _item(
                id=f"allocation:{a.id}:done",
                type="allocation",
                category="销售合同",
                source="收款核销",
                source_id=r.receipt_no or str(a.id),
                title=f"核销 {r.receipt_no or r.id} → {plan.title}",
                applicant_name=_user_name(db, a.allocated_by),
                department_name=_dept_name(db, r.department_id),
                submitted_at=a.approved_at or a.updated_at,
                status=a.status,
                status_label=label,
                node="核销审批完成",
                summary=f"¥{a.amount} · {label}",
                facts=[],
                deep_link="/sales?tab=contracts",
                can_act=False,
                actions=["open"],
                meta={"entity_id": a.id},
            )
        )

    items.sort(key=lambda x: x.submitted_at or datetime.min, reverse=True)
    return items


def list_approvals(
    db: Session,
    user: User,
    *,
    tab: str = "pending",
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> ApprovalListOut:
    if tab == "initiated":
        items = _collect_initiated(db, user)
    elif tab == "processed":
        items = _collect_processed(db, user)
    elif tab == "cc":
        items = []
    else:
        items = _collect_pending_for_actor(db, user)

    if category and category != "全部业务":
        items = [x for x in items if x.category == category]
    if keyword:
        kw = keyword.strip().lower()
        items = [
            x
            for x in items
            if kw in x.title.lower()
            or kw in x.source_id.lower()
            or kw in (x.applicant_name or "").lower()
            or kw in (x.summary or "").lower()
        ]

    total = len(items)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return ApprovalListOut(total=total, items=items[start:end])


def approval_stats(db: Session, user: User) -> ApprovalStatsOut:
    return ApprovalStatsOut(
        pending=len(_collect_pending_for_actor(db, user)),
        initiated=len(_collect_initiated(db, user)),
        processed=len(_collect_processed(db, user)),
        cc=0,
    )
