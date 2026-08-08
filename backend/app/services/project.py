"""
项目管理业务逻辑：立项、状态流转、进度、里程碑、任务、验收。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import collect_data_scopes, user_can, widest_data_scope
from app.models.contract import (
    CONTRACT_STATUS_ACTIVE,
    CONTRACT_STATUS_COMPLETED,
    CONTRACT_STATUS_SIGNED,
    Contract,
)
from app.models.customer import Customer
from app.models.department import Department
from app.models.finance import RECEIPT_STATUS_CONFIRMED, Receipt
from app.models.project import (
    ACCEPTANCE_APPROVAL_APPROVED,
    ACCEPTANCE_APPROVAL_NONE,
    ACCEPTANCE_APPROVAL_PENDING,
    ACCEPTANCE_APPROVAL_REJECTED,
    ACCEPTANCE_RESULTS,
    EVIDENCE_STATUS_CONFIRMED,
    EVIDENCE_STATUS_NONE,
    EVIDENCE_STATUS_PENDING,
    EVIDENCE_STATUS_REJECTED,
    EVIDENCE_STATUSES,
    FINANCE_CHECK_APPROVED,
    FINANCE_CHECK_NONE,
    FINANCE_CHECK_PENDING,
    FINANCE_CHECK_REJECTED,
    MILESTONE_STATUS_DONE,
    MILESTONE_STATUS_DOING,
    MILESTONE_STATUS_PENDING,
    MILESTONE_STATUSES,
    PAYMENT_DEFER_APPROVED,
    PAYMENT_DEFER_NONE,
    PAYMENT_DEFER_PENDING,
    PAYMENT_DEFER_REJECTED,
    PROJECT_STATUS_ACCEPTED,
    PROJECT_STATUS_ACCEPTING,
    PROJECT_STATUS_COMPLETED,
    PROJECT_STATUS_EXECUTING,
    PROJECT_STATUS_INITIATING,
    PROJECT_STATUS_PLANNING,
    PROJECT_STATUS_TERMINATED,
    PROJECT_TYPES,
    TASK_STATUS_DONE,
    TASK_STATUS_DOING,
    TASK_STATUS_PENDING,
    TASK_STATUSES,
    Project,
    ProjectMilestone,
    ProjectTask,
)
from app.models.user import User
from app.schemas.project import (
    MilestoneCreate,
    MilestoneUpdate,
    ProjectAcceptRequest,
    ProjectAcceptanceReviewRequest,
    ProjectCreate,
    ProjectFinanceCheckRequest,
    ProjectFinanceCheckReviewRequest,
    ProjectLeftoverCloseRequest,
    ProjectPaymentDeferReviewRequest,
    ProjectTaskCreate,
    ProjectTaskUpdate,
    ProjectTerminateRequest,
    ProjectUpdate,
)

_NEXT_NODE = {
    PROJECT_STATUS_INITIATING: "完成立项前确认并进入计划",
    PROJECT_STATUS_PLANNING: "制定基线并进入执行",
    PROJECT_STATUS_EXECUTING: "推进任务与计划节点",
    PROJECT_STATUS_ACCEPTING: "组织内部验收",
    PROJECT_STATUS_ACCEPTED: "财务核对后结项",
    PROJECT_STATUS_COMPLETED: "—",
    PROJECT_STATUS_TERMINATED: "—",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return None
    return u.real_name or u.username


def _gen_project_no(db: Session) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"XM{today}"
    count = db.query(Project).filter(Project.project_no.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def _gen_task_no(db: Session) -> str:
    today = date.today().strftime("%m%d")
    prefix = f"RW-{today}"
    count = db.query(ProjectTask).filter(ProjectTask.task_no.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:02d}"


def compute_health(project: Project) -> str:
    if project.status == PROJECT_STATUS_TERMINATED:
        return "risk"
    today = date.today()
    if project.end_date and project.end_date < today and project.status not in {
        PROJECT_STATUS_COMPLETED,
        PROJECT_STATUS_ACCEPTED,
    }:
        return "risk"
    if project.status == PROJECT_STATUS_ACCEPTING:
        return "attention"
    if project.progress < 30 and project.status == PROJECT_STATUS_EXECUTING:
        return "attention"
    if project.leftover_summary:
        return "attention"
    return "normal"


_INITIATION_CONTRACT_STATUSES = {
    CONTRACT_STATUS_SIGNED,
    CONTRACT_STATUS_ACTIVE,
    CONTRACT_STATUS_COMPLETED,
}


def _contract_confirmed_paid(db: Session, contract_id: int) -> Decimal:
    """已确认到账金额（财务复核通过即视为已收款）。"""
    total = (
        db.query(func.coalesce(func.sum(Receipt.amount), 0))
        .filter(
            Receipt.contract_id == contract_id,
            Receipt.status == RECEIPT_STATUS_CONFIRMED,
        )
        .scalar()
    )
    return Decimal(str(total or 0))


def assert_contract_ready_for_initiation(
    db: Session,
    contract: Contract,
    *,
    allow_unpaid: bool = False,
) -> None:
    """立项硬门槛：合同已签署；默认还须至少一笔确认到账（无到款例外可跳过）。"""
    if contract.status not in _INITIATION_CONTRACT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="合同须已签署（或执行中/已完成）后才能立项",
        )
    if allow_unpaid:
        return
    if _contract_confirmed_paid(db, contract.id) <= 0:
        raise HTTPException(
            status_code=400,
            detail="合同须有确认到账后才能立项（请先完成到款认领并经财务复核；或勾选无到款立项）",
        )


def _project_contract_settlement(
    db: Session, project: Project
) -> tuple[Optional[Contract], Decimal, Decimal, bool]:
    """项目关联合同的回款结清情况：(合同, 合同金额, 已确认到账, 是否收齐)。"""
    from app.services.contract import enrich_contract, is_collection_complete

    if not project.contract_id:
        return None, Decimal("0"), Decimal("0"), False
    contract = db.query(Contract).filter(Contract.id == project.contract_id).first()
    if not contract:
        return None, Decimal("0"), Decimal("0"), False
    enrich_contract(db, contract)
    amount = Decimal(str(contract.amount or 0))
    paid = Decimal(str(getattr(contract, "paid_amount", 0) or 0))
    return contract, amount, paid, is_collection_complete(db, contract)


def enrich_project(db: Session, project: Project) -> Project:
    contract = None
    if project.contract_id:
        contract = db.query(Contract).filter(Contract.id == project.contract_id).first()
        project.contract_no = contract.contract_no if contract else None  # type: ignore[attr-defined]
        project.contract_title = contract.title if contract else None  # type: ignore[attr-defined]
    else:
        project.contract_no = None  # type: ignore[attr-defined]
        project.contract_title = None  # type: ignore[attr-defined]

    if project.customer_id:
        customer = db.query(Customer).filter(Customer.id == project.customer_id).first()
        project.customer_name = customer.name if customer else None  # type: ignore[attr-defined]
    else:
        project.customer_name = None  # type: ignore[attr-defined]

    project.manager_name = _user_name(db, project.manager_id)  # type: ignore[attr-defined]
    project.creator_name = _user_name(db, project.creator_id)  # type: ignore[attr-defined]
    project.business_owner_name = _user_name(db, project.business_owner_id)  # type: ignore[attr-defined]
    project.acceptance_owner_name = _user_name(db, project.acceptance_owner_id)  # type: ignore[attr-defined]
    project.acceptance_submitted_by_name = _user_name(  # type: ignore[attr-defined]
        db, project.acceptance_submitted_by
    )
    project.acceptance_approved_by_name = _user_name(  # type: ignore[attr-defined]
        db, project.acceptance_approved_by
    )

    project.contract_active_ok = bool(  # type: ignore[attr-defined]
        contract and contract.status in _INITIATION_CONTRACT_STATUSES
    )
    paid = (
        _contract_confirmed_paid(db, contract.id) if contract else Decimal("0")
    )
    payment_ok = paid > 0
    project.payment_received_ok = payment_ok  # type: ignore[attr-defined]
    _, contract_amount, contract_paid, collection_complete = _project_contract_settlement(
        db, project
    )
    project.contract_amount = contract_amount  # type: ignore[attr-defined]
    project.contract_paid_amount = contract_paid  # type: ignore[attr-defined]
    project.contract_collection_complete = collection_complete  # type: ignore[attr-defined]
    project.health = compute_health(project)  # type: ignore[attr-defined]
    if (
        project.status == PROJECT_STATUS_INITIATING
        and project.payment_deferred
        and project.payment_defer_status == PAYMENT_DEFER_PENDING
        and not payment_ok
    ):
        project.next_node = "等待无到款立项审批"  # type: ignore[attr-defined]
    elif (
        project.status == PROJECT_STATUS_INITIATING
        and project.payment_deferred
        and project.payment_defer_status == PAYMENT_DEFER_REJECTED
        and not payment_ok
    ):
        project.next_node = "无到款立项已驳回，请先到款"  # type: ignore[attr-defined]
    elif (
        project.status == PROJECT_STATUS_ACCEPTING
        and project.acceptance_approval_status == ACCEPTANCE_APPROVAL_PENDING
    ):
        project.next_node = "等待验收审批"  # type: ignore[attr-defined]
    else:
        project.next_node = _NEXT_NODE.get(project.status, "—")  # type: ignore[attr-defined]
    if not project.baseline_version:
        project.baseline_version = "V1"

    milestones = (
        db.query(ProjectMilestone).filter(ProjectMilestone.project_id == project.id).all()
    )
    project.milestone_total = len(milestones)  # type: ignore[attr-defined]
    project.milestone_done = sum(1 for m in milestones if m.status == "done")  # type: ignore[attr-defined]
    return project


def assert_can_view(user: User, project: Project) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes:
        return
    scope = widest_data_scope(collect_data_scopes(user))
    if scope == "company":
        return
    if project.manager_id == user.id or project.creator_id == user.id:
        return
    if scope == "department" and user.department_id and project.department_id == user.department_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该项目")


def assert_can_operate(user: User, project: Project) -> None:
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes:
        return
    if project.manager_id == user.id or project.creator_id == user.id:
        return
    if user_can(user, "project:manage"):
        return
    if "delivery_lead" in role_codes or "middle_manager" in role_codes or "executive" in role_codes:
        return
    raise HTTPException(status_code=403, detail="无权操作该项目")


def _require_project_action(user: User, *codes: str) -> None:
    """动作权限：任一码或 project:manage / admin。"""
    if user_can(user, "project:manage"):
        return
    if any(user_can(user, c) for c in codes):
        return
    if "admin" in {r.code for r in user.roles}:
        return
    raise HTTPException(status_code=403, detail="无权执行该项目操作")


def assert_can_update_task(
    user: User, project: Project, task: ProjectTask, data: dict
) -> None:
    """项目操作人可改任务；责任人仅可完成自己的任务（status=done + 实际工时）。"""
    try:
        assert_can_operate(user, project)
        return
    except HTTPException:
        pass
    if (
        task.assignee_id == user.id
        and data.get("status") == TASK_STATUS_DONE
        and set(data.keys()) <= {"status", "actual_hours", "remark"}
    ):
        return
    raise HTTPException(status_code=403, detail="无权操作该任务（责任人仅可完成自己的任务）")


def can_manage_plan(user: User, project: Project) -> bool:
    """计划基线管理（加里程碑/审证据/锁基线等）：本部门负责人或系统管理员。"""
    role_codes = {r.code for r in user.roles}
    if "admin" in role_codes:
        return True
    if "dept_head" not in role_codes:
        return False
    if project.department_id and user.department_id and project.department_id != user.department_id:
        return False
    return True


def assert_can_manage_plan(user: User, project: Project) -> None:
    if can_manage_plan(user, project):
        return
    raise HTTPException(status_code=403, detail="仅本项目所属部门负责人或系统管理员可操作计划基线")


def create_project(db: Session, user: User, payload: ProjectCreate) -> Project:
    if payload.project_type not in PROJECT_TYPES:
        raise HTTPException(status_code=400, detail="无效的项目类型")

    customer_id = payload.customer_id
    contract_id = payload.contract_id
    project_type = payload.project_type
    manager_id = payload.manager_id or user.id

    if not contract_id:
        raise HTTPException(status_code=400, detail="请关联合同后再立项")

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=400, detail="合同不存在")

    payment_deferred = bool(payload.payment_deferred)
    deferred_reason = (payload.payment_deferred_reason or "").strip() or None
    if payment_deferred:
        if not deferred_reason:
            raise HTTPException(
                status_code=400,
                detail="无到款立项须填写原因（如客户约定先干活后付款）",
            )
        if _contract_confirmed_paid(db, contract.id) > 0:
            # 已有到款则不必走例外
            payment_deferred = False
            deferred_reason = None
    assert_contract_ready_for_initiation(
        db, contract, allow_unpaid=payment_deferred
    )
    existing = (
        db.query(Project)
        .filter(
            Project.contract_id == contract_id,
            Project.status != PROJECT_STATUS_TERMINATED,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"该合同已有交付项目 {existing.project_no}，不可重复立项（终止后才可再立）",
        )
    customer_id = customer_id or contract.customer_id
    if project_type == "other" and contract.contract_type in PROJECT_TYPES:
        project_type = contract.contract_type

    if customer_id:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise HTTPException(status_code=400, detail="客户不存在")

    manager = db.query(User).filter(User.id == manager_id).first()
    if not manager:
        raise HTTPException(status_code=400, detail="负责人不存在")

    remark = payload.remark
    if payment_deferred and deferred_reason:
        tag = f"[无到款立项待审] {deferred_reason}"
        remark = f"{tag}\n{remark}" if remark else tag

    now = datetime.now(timezone.utc)
    project = Project(
        project_no=_gen_project_no(db),
        name=payload.name.strip(),
        contract_id=contract_id,
        customer_id=customer_id,
        project_type=project_type,
        status=PROJECT_STATUS_INITIATING,
        progress=5,
        manager_id=manager_id,
        creator_id=user.id,
        department_id=manager.department_id or user.department_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        scope_desc=payload.scope_desc,
        remark=remark,
        payment_verified=not payment_deferred,
        payment_deferred=payment_deferred,
        payment_deferred_reason=deferred_reason,
        payment_defer_status=PAYMENT_DEFER_PENDING if payment_deferred else PAYMENT_DEFER_NONE,
        payment_defer_submitted_by=user.id if payment_deferred else None,
        payment_defer_submitted_at=now if payment_deferred else None,
        handoff_complete=payload.handoff_complete,
        contact_confirmed=payload.contact_confirmed,
        business_owner_id=payload.business_owner_id or user.id,
        baseline_version="V1",
    )
    db.add(project)
    db.flush()
    from app.services import project_resource as resource_service

    resource_service.seed_resource_needs(
        db,
        project,
        role_assignments=payload.resource_roles,
        commit=False,
    )
    db.commit()
    db.refresh(project)
    return enrich_project(db, project)


def update_project(db: Session, user: User, project_id: int, payload: ProjectUpdate) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_operate(user, project)
    if project.status in {PROJECT_STATUS_COMPLETED, PROJECT_STATUS_TERMINATED}:
        raise HTTPException(status_code=400, detail="已结束项目不可编辑")

    data = payload.model_dump(exclude_unset=True)
    if "project_type" in data and data["project_type"] not in PROJECT_TYPES:
        raise HTTPException(status_code=400, detail="无效的项目类型")
    if "manager_id" in data and data["manager_id"] is not None:
        manager = db.query(User).filter(User.id == data["manager_id"]).first()
        if not manager:
            raise HTTPException(status_code=400, detail="负责人不存在")
        project.department_id = manager.department_id or project.department_id
    if "contract_id" in data and data["contract_id"] is not None:
        contract = db.query(Contract).filter(Contract.id == data["contract_id"]).first()
        if not contract:
            raise HTTPException(status_code=400, detail="合同不存在")
        if "customer_id" not in data:
            data["customer_id"] = contract.customer_id
    if "customer_id" in data and data["customer_id"] is not None:
        customer = db.query(Customer).filter(Customer.id == data["customer_id"]).first()
        if not customer:
            raise HTTPException(status_code=400, detail="客户不存在")

    for k, v in data.items():
        setattr(project, k, v)

    db.commit()
    db.refresh(project)
    return enrich_project(db, project)


def list_projects(
    db: Session,
    user: User,
    *,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    contract_id: Optional[int] = None,
    scope_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    enrich: bool = True,
) -> tuple[int, list[Project]]:
    q = db.query(Project)
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    scope = widest_data_scope(collect_data_scopes(user)) if not is_admin else "company"

    if scope_filter == "mine":
        q = q.filter(or_(Project.manager_id == user.id, Project.creator_id == user.id))
    elif not is_admin:
        if scope == "personal":
            q = q.filter(or_(Project.manager_id == user.id, Project.creator_id == user.id))
        elif scope == "department" and user.department_id:
            q = q.filter(
                or_(
                    Project.department_id == user.department_id,
                    Project.manager_id == user.id,
                    Project.creator_id == user.id,
                )
            )

    if status:
        q = q.filter(Project.status == status)
    if contract_id:
        q = q.filter(Project.contract_id == contract_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(or_(Project.name.ilike(like), Project.project_no.ilike(like)))

    total = q.count()
    items = (
        q.order_by(Project.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    if not enrich:
        return total, items
    return total, [enrich_project(db, x) for x in items]


def get_project_detail(db: Session, user: User, project_id: int) -> Project:
    project = (
        db.query(Project)
        .options(joinedload(Project.milestones))
        .filter(Project.id == project_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    project.milestones = sorted(project.milestones or [], key=lambda x: (x.sort_order, x.id))
    for ms in project.milestones:
        enrich_milestone(db, ms)
    return enrich_project(db, project)


def _transition(
    db: Session, user: User, project_id: int, allowed_from: set[str], to_status: str
) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_operate(user, project)
    if project.status not in allowed_from:
        raise HTTPException(status_code=400, detail="当前状态不可流转到目标状态")
    project.status = to_status
    if to_status == PROJECT_STATUS_COMPLETED:
        project.actual_end_date = date.today()
    recalculate_project_progress(db, project)
    db.commit()
    db.refresh(project)
    return enrich_project(db, project)


def is_payment_defer_approved(project: Project) -> bool:
    return bool(project.payment_deferred) and project.payment_defer_status == PAYMENT_DEFER_APPROVED


def can_review_payment_defer(user: User) -> bool:
    if user_can(user, "project:manage"):
        return True
    return bool({"admin", "dept_head"} & {r.code for r in user.roles})


def review_payment_defer(
    db: Session,
    user: User,
    project_id: int,
    payload: ProjectPaymentDeferReviewRequest,
    *,
    approve: bool,
) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    if not can_review_payment_defer(user):
        raise HTTPException(status_code=403, detail="无权审批无到款立项")
    if not project.payment_deferred:
        raise HTTPException(status_code=400, detail="该项目未申请无到款立项")
    if project.payment_defer_status != PAYMENT_DEFER_PENDING:
        raise HTTPException(status_code=409, detail="仅待审批的无到款立项可以处理")

    project.payment_defer_approved_by = user.id
    project.payment_defer_approved_at = datetime.now(timezone.utc)
    if approve:
        project.payment_defer_status = PAYMENT_DEFER_APPROVED
        project.payment_defer_reject_reason = None
        if payload.remark:
            note = f"[无到款立项通过] {payload.remark.strip()}"
            project.remark = f"{(project.remark or '').strip()}\n{note}".strip()
    else:
        reason = (payload.remark or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="驳回请填写原因")
        project.payment_defer_status = PAYMENT_DEFER_REJECTED
        project.payment_defer_reject_reason = reason
        note = f"[无到款立项驳回] {reason}"
        project.remark = f"{(project.remark or '').strip()}\n{note}".strip()
    db.commit()
    db.refresh(project)
    return enrich_project(db, project)


def start_planning(db: Session, user: User, project_id: int) -> Project:
    from app.services import project_resource as resource_service

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.contract_id:
        raise HTTPException(status_code=400, detail="请关联合同后再进入计划")
    contract = db.query(Contract).filter(Contract.id == project.contract_id).first()
    if not contract:
        raise HTTPException(status_code=400, detail="关联合同不存在")
    paid = _contract_confirmed_paid(db, contract.id) > 0
    if not paid and project.payment_deferred:
        if project.payment_defer_status == PAYMENT_DEFER_PENDING:
            raise HTTPException(
                status_code=400,
                detail="无到款立项审批中，通过后方可进入计划（或先完成到款认领）",
            )
        if project.payment_defer_status == PAYMENT_DEFER_REJECTED:
            raise HTTPException(
                status_code=400,
                detail="无到款立项已驳回，请先完成到款认领后再进入计划",
            )
        if project.payment_defer_status != PAYMENT_DEFER_APPROVED:
            raise HTTPException(status_code=400, detail="无到款立项尚未审批通过")
    allow_unpaid = (not paid) and is_payment_defer_approved(project)
    assert_contract_ready_for_initiation(db, contract, allow_unpaid=allow_unpaid)
    # 无到款例外：进计划时仍标记已核验「可开工条件」，真实到账看 payment_received_ok
    project.payment_verified = True
    resource_service.seed_resource_needs(db, project)
    resource_service.assert_resources_ready(db, project_id)
    return _transition(db, user, project_id, {PROJECT_STATUS_INITIATING}, PROJECT_STATUS_PLANNING)


def start_executing(db: Session, user: User, project_id: int) -> Project:
    return _transition(
        db,
        user,
        project_id,
        {PROJECT_STATUS_PLANNING, PROJECT_STATUS_INITIATING},
        PROJECT_STATUS_EXECUTING,
    )


def start_acceptance(db: Session, user: User, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_ready_for_acceptance(db, project)
    return _transition(db, user, project_id, {PROJECT_STATUS_EXECUTING}, PROJECT_STATUS_ACCEPTING)


def accept_project(
    db: Session, user: User, project_id: int, payload: Optional[ProjectAcceptRequest] = None
) -> Project:
    """提交内部验收申请，进入审批中心；通过后才变为已验收。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_operate(user, project)
    _require_project_action(user, "project:accept_submit")
    if project.status not in {PROJECT_STATUS_ACCEPTING, PROJECT_STATUS_EXECUTING}:
        raise HTTPException(status_code=400, detail="当前状态不可验收")
    if project.acceptance_approval_status == ACCEPTANCE_APPROVAL_PENDING:
        raise HTTPException(status_code=409, detail="验收申请已在审批中，请勿重复提交")
    assert_ready_for_acceptance(db, project)

    if not payload:
        raise HTTPException(status_code=400, detail="请填写验收结论并上传验收附件")
    if payload.result not in ACCEPTANCE_RESULTS:
        raise HTTPException(status_code=400, detail="无效的验收结果")
    if payload.result == "fail":
        raise HTTPException(status_code=400, detail="验收不通过时不可提交审批")
    if payload.result == "conditional" and not (payload.leftover_summary or "").strip():
        raise HTTPException(status_code=400, detail="有条件通过须填写遗留问题摘要")
    if not (payload.conclusion or "").strip():
        raise HTTPException(status_code=400, detail="请填写验收结论")
    if not (payload.attachment or "").strip():
        raise HTTPException(status_code=400, detail="请上传内部验收附件")
    if not (payload.method or "").strip():
        raise HTTPException(status_code=400, detail="请选择验收方式")

    project.acceptance_result = payload.result
    project.accepted_at = payload.accepted_at or date.today()
    project.acceptance_method = payload.method.strip()
    project.acceptance_owner_id = payload.owner_id or user.id
    project.acceptance_conclusion = payload.conclusion.strip()
    project.leftover_summary = (payload.leftover_summary or "").strip() or None
    project.acceptance_attachment = payload.attachment.strip()
    project.acceptance_attachment_path = payload.attachment_path
    project.acceptance_approval_status = ACCEPTANCE_APPROVAL_PENDING
    project.acceptance_submitted_by = user.id
    project.acceptance_submitted_at = datetime.now(timezone.utc)
    project.acceptance_approved_by = None
    project.acceptance_approved_at = None
    project.acceptance_reject_reason = None
    project.status = PROJECT_STATUS_ACCEPTING
    if project.leftover_summary:
        project.leftover_closed = False
    else:
        project.leftover_closed = True
    db.commit()
    db.refresh(project)
    return enrich_project(db, project)


def can_approve_acceptance(user: User) -> bool:
    if user_can(user, "project:accept_approve") or user_can(user, "project:manage"):
        return True
    return "admin" in {r.code for r in user.roles}


def review_acceptance(
    db: Session,
    user: User,
    project_id: int,
    payload: ProjectAcceptanceReviewRequest,
    *,
    approve: bool,
) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    if not can_approve_acceptance(user):
        raise HTTPException(status_code=403, detail="无权审批项目验收")
    if project.acceptance_approval_status != ACCEPTANCE_APPROVAL_PENDING:
        raise HTTPException(status_code=409, detail="仅待审批的验收申请可以处理")
    if project.status != PROJECT_STATUS_ACCEPTING:
        raise HTTPException(status_code=409, detail="项目不在验收中")

    project.acceptance_approved_by = user.id
    project.acceptance_approved_at = datetime.now(timezone.utc)
    if approve:
        project.acceptance_approval_status = ACCEPTANCE_APPROVAL_APPROVED
        project.status = PROJECT_STATUS_ACCEPTED
        if project.progress < 90:
            project.progress = max(project.progress, 90)
    else:
        reason = (payload.remark or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="驳回请填写原因")
        project.acceptance_approval_status = ACCEPTANCE_APPROVAL_REJECTED
        project.acceptance_reject_reason = reason
    db.commit()
    db.refresh(project)
    return enrich_project(db, project)


def can_review_finance_check(user: User) -> bool:
    if user_can(user, "project:finance_approve"):
        return True
    if user_can(user, "payment:confirm") or user_can(user, "payment:manage"):
        return True
    return "admin" in {r.code for r in user.roles}


def submit_finance_check(
    db: Session, user: User, project_id: int, payload: ProjectFinanceCheckRequest
) -> Project:
    """提交财务核对申请，进入审批中心。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_operate(user, project)
    _require_project_action(user, "project:finance_submit")
    if project.status != PROJECT_STATUS_ACCEPTED:
        raise HTTPException(status_code=400, detail="仅已验收项目可提交财务核对")
    if project.acceptance_approval_status != ACCEPTANCE_APPROVAL_APPROVED:
        raise HTTPException(status_code=400, detail="验收尚未审批通过")
    if project.finance_check_status == FINANCE_CHECK_PENDING:
        raise HTTPException(status_code=409, detail="财务核对已在审批中")
    if project.finance_check_passed or project.finance_check_status == FINANCE_CHECK_APPROVED:
        raise HTTPException(status_code=409, detail="财务核对已通过")

    project.finance_check_status = FINANCE_CHECK_PENDING
    project.finance_check_passed = False
    project.finance_check_submitted_by = user.id
    project.finance_check_submitted_at = datetime.now(timezone.utc)
    project.finance_check_approved_by = None
    project.finance_check_approved_at = None
    project.finance_check_reject_reason = None
    if payload.remark:
        project.remark = ((project.remark or "") + f"\n[财务核对申请] {payload.remark}").strip()
    db.commit()
    db.refresh(project)
    return enrich_project(db, project)


def review_finance_check(
    db: Session,
    user: User,
    project_id: int,
    payload: ProjectFinanceCheckReviewRequest,
    *,
    approve: bool,
) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    if not can_review_finance_check(user):
        raise HTTPException(status_code=403, detail="无权审批财务核对")
    if project.finance_check_status != FINANCE_CHECK_PENDING:
        raise HTTPException(status_code=409, detail="仅待审批的财务核对可以处理")

    if approve:
        _, amount, paid, complete = _project_contract_settlement(db, project)
        if not project.contract_id:
            raise HTTPException(status_code=400, detail="项目未关联合同，无法核对回款，不能通过")
        if not complete:
            outstanding = amount - paid
            if outstanding < 0:
                outstanding = Decimal("0")
            raise HTTPException(
                status_code=400,
                detail=(
                    f"合同回款尚未收齐，不能通过财务核对"
                    f"（已到账 {paid} / 合同金额 {amount}，差额 {outstanding}）"
                ),
            )
        project.finance_check_status = FINANCE_CHECK_APPROVED
        project.finance_check_passed = True
    else:
        reason = (payload.remark or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="驳回请填写原因")
        project.finance_check_status = FINANCE_CHECK_REJECTED
        project.finance_check_passed = False
        project.finance_check_reject_reason = reason
    project.finance_check_approved_by = user.id
    project.finance_check_approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    return enrich_project(db, project)


def set_leftover_closed(
    db: Session, user: User, project_id: int, payload: ProjectLeftoverCloseRequest
) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_operate(user, project)
    if project.status not in {PROJECT_STATUS_ACCEPTED, PROJECT_STATUS_ACCEPTING}:
        raise HTTPException(status_code=400, detail="当前状态不可关闭遗留")
    project.leftover_closed = bool(payload.closed)
    db.commit()
    db.refresh(project)
    return enrich_project(db, project)


def complete_project(db: Session, user: User, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_operate(user, project)
    _require_project_action(user, "project:complete")
    if project.status != PROJECT_STATUS_ACCEPTED:
        raise HTTPException(status_code=400, detail="未内部验收通过不可结项")
    if project.acceptance_approval_status != ACCEPTANCE_APPROVAL_APPROVED:
        raise HTTPException(status_code=400, detail="验收尚未审批通过，不可结项")
    if not project.finance_check_passed or project.finance_check_status != FINANCE_CHECK_APPROVED:
        raise HTTPException(status_code=400, detail="财务核对未通过，不可结项")
    if project.leftover_summary and not project.leftover_closed:
        raise HTTPException(status_code=400, detail="遗留问题未关闭，不可结项")
    # 双保险：结项时再核一次回款，避免财务核对误通过后欠款仍能结项
    _, amount, paid, complete = _project_contract_settlement(db, project)
    if not project.contract_id:
        raise HTTPException(status_code=400, detail="项目未关联合同，不可结项")
    if not complete:
        outstanding = amount - paid
        if outstanding < 0:
            outstanding = Decimal("0")
        raise HTTPException(
            status_code=400,
            detail=(
                f"合同回款尚未收齐，不可结项"
                f"（已到账 {paid} / 合同金额 {amount}，差额 {outstanding}）"
            ),
        )
    return _transition(db, user, project_id, {PROJECT_STATUS_ACCEPTED}, PROJECT_STATUS_COMPLETED)


def terminate_project(
    db: Session, user: User, project_id: int, payload: ProjectTerminateRequest
) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_operate(user, project)
    if project.status in {PROJECT_STATUS_COMPLETED, PROJECT_STATUS_TERMINATED}:
        raise HTTPException(status_code=400, detail="当前状态不可终止")
    project.status = PROJECT_STATUS_TERMINATED
    project.terminate_reason = payload.reason
    project.actual_end_date = date.today()
    db.commit()
    db.refresh(project)
    return enrich_project(db, project)


def _milestone_fully_done(ms: ProjectMilestone) -> bool:
    """节点真正完成：状态 done 且完成证据已确认。"""
    return (
        ms.status == MILESTONE_STATUS_DONE
        and (ms.evidence_status or EVIDENCE_STATUS_NONE) == EVIDENCE_STATUS_CONFIRMED
        and bool((ms.evidence or "").strip())
    )


def recalculate_project_progress(db: Session, project: Project) -> None:
    """按生命周期计算进度：规划期不算节点完成度，执行期封顶 80%，留验收/结项空间。"""
    status = project.status
    if status == PROJECT_STATUS_TERMINATED:
        return
    if status == PROJECT_STATUS_COMPLETED:
        project.progress = 100
        return
    if status == PROJECT_STATUS_ACCEPTED:
        project.progress = max(int(project.progress or 0), 90)
        return
    if status == PROJECT_STATUS_ACCEPTING:
        project.progress = max(int(project.progress or 0), 85)
        return
    if status == PROJECT_STATUS_INITIATING:
        project.progress = 5
        return
    if status == PROJECT_STATUS_PLANNING:
        # 规划期只表示筹备，节点定义/误标完成都不抬到执行进度
        project.progress = 10
        return

    # executing
    milestones = (
        db.query(ProjectMilestone).filter(ProjectMilestone.project_id == project.id).all()
    )
    if milestones:
        done = sum(1 for m in milestones if _milestone_fully_done(m))
        # 进入执行至少 15%；全部节点闭环到 80%
        project.progress = 15 + int(done * 65 / len(milestones))
        return

    tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project.id).all()
    if not tasks:
        project.progress = 15
        return
    done = sum(1 for t in tasks if t.status == TASK_STATUS_DONE)
    project.progress = 15 + int(done * 65 / len(tasks))


def _sync_project_progress_from_milestones(db: Session, project: Project) -> None:
    """兼容旧调用点：统一走生命周期进度计算。"""
    recalculate_project_progress(db, project)


def enrich_milestone(db: Session, ms: ProjectMilestone) -> ProjectMilestone:
    tasks = db.query(ProjectTask).filter(ProjectTask.milestone_id == ms.id).all()
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == TASK_STATUS_DONE)
    ms.task_total = total  # type: ignore[attr-defined]
    ms.task_done = done  # type: ignore[attr-defined]
    evidence_status = getattr(ms, "evidence_status", None) or EVIDENCE_STATUS_NONE
    if not (ms.evidence or "").strip():
        evidence_status = EVIDENCE_STATUS_NONE
    ms.evidence_status = evidence_status
    ms.evidence_confirmed_by_name = _user_name(db, ms.evidence_confirmed_by)  # type: ignore[attr-defined]
    tasks_ready = total == 0 or done == total
    evidence_ready = evidence_status == EVIDENCE_STATUS_CONFIRMED
    project = db.query(Project).filter(Project.id == ms.project_id).first()
    in_execution = bool(
        project
        and project.status
        in {
            PROJECT_STATUS_EXECUTING,
            PROJECT_STATUS_ACCEPTING,
            PROJECT_STATUS_ACCEPTED,
            PROJECT_STATUS_COMPLETED,
        }
    )
    ms.can_complete = bool(in_execution and evidence_ready and tasks_ready)  # type: ignore[attr-defined]
    if not in_execution:
        ms.next_action = "先确认计划基线，进入执行后再推进"  # type: ignore[attr-defined]
    elif ms.status == MILESTONE_STATUS_DONE and evidence_ready:
        ms.next_action = "已完成"  # type: ignore[attr-defined]
    elif ms.status == MILESTONE_STATUS_DONE and evidence_status == EVIDENCE_STATUS_PENDING:
        ms.next_action = "节点状态异常，请先确认证据"  # type: ignore[attr-defined]
    elif ms.status == MILESTONE_STATUS_DONE and not (ms.evidence or "").strip():
        ms.next_action = "节点状态异常，请补交证据"  # type: ignore[attr-defined]
    elif total == 0 and not (ms.evidence or "").strip():
        # 常规路径：先拆任务；无任务的验收节点也可直接交证据
        ms.next_action = "建议先挂任务；纯验收节点也可直接交证据"  # type: ignore[attr-defined]
    elif total > 0 and not tasks_ready:
        ms.next_action = f"先完成剩余 {total - done} 个关联任务"  # type: ignore[attr-defined]
    elif not (ms.evidence or "").strip():
        ms.next_action = "任务已齐，提交完成证据"  # type: ignore[attr-defined]
    elif evidence_status == EVIDENCE_STATUS_REJECTED:
        ms.next_action = "按驳回意见重提证据"  # type: ignore[attr-defined]
    elif evidence_status == EVIDENCE_STATUS_PENDING:
        ms.next_action = "等待部门负责人确认证据"  # type: ignore[attr-defined]
    else:
        ms.next_action = "可标记节点完成"  # type: ignore[attr-defined]
    return ms


def _try_auto_complete_milestone(db: Session, ms: ProjectMilestone) -> bool:
    """证据已确认且任务齐（或无任务）时自动完成。返回是否本次完成。"""
    if ms.status == MILESTONE_STATUS_DONE:
        return False
    project = db.query(Project).filter(Project.id == ms.project_id).first()
    if not project or project.status not in {
        PROJECT_STATUS_EXECUTING,
        PROJECT_STATUS_ACCEPTING,
    }:
        return False
    if (ms.evidence_status or EVIDENCE_STATUS_NONE) != EVIDENCE_STATUS_CONFIRMED:
        return False
    if not (ms.evidence or "").strip():
        return False
    open_tasks = (
        db.query(ProjectTask)
        .filter(
            ProjectTask.milestone_id == ms.id,
            ProjectTask.status != TASK_STATUS_DONE,
        )
        .count()
    )
    if open_tasks:
        return False
    ms.status = MILESTONE_STATUS_DONE
    if not ms.actual_date:
        ms.actual_date = date.today()
    recalculate_project_progress(db, project)
    return True


def assert_milestone_completable(db: Session, ms: ProjectMilestone) -> None:
    project = db.query(Project).filter(Project.id == ms.project_id).first()
    if not project or project.status not in {
        PROJECT_STATUS_EXECUTING,
        PROJECT_STATUS_ACCEPTING,
    }:
        raise HTTPException(status_code=400, detail="项目未进入执行，不可完成计划节点")
    missing: list[str] = []
    if not (ms.evidence or "").strip():
        missing.append("完成证据未填写")
    elif (ms.evidence_status or EVIDENCE_STATUS_NONE) != EVIDENCE_STATUS_CONFIRMED:
        missing.append("完成证据待部门负责人确认")
    open_tasks = (
        db.query(ProjectTask)
        .filter(
            ProjectTask.milestone_id == ms.id,
            ProjectTask.status != TASK_STATUS_DONE,
        )
        .count()
    )
    if open_tasks:
        missing.append(f"还有 {open_tasks} 个关联任务未完成")
    if missing:
        raise HTTPException(status_code=400, detail="计划节点不可完成：" + "；".join(missing))


def assert_ready_for_acceptance(db: Session, project: Project) -> None:
    milestones = (
        db.query(ProjectMilestone).filter(ProjectMilestone.project_id == project.id).all()
    )
    # 无里程碑时允许直接验收（小项目可用任务+验收单）；有则必须全部完成且证据确认
    if not milestones:
        return
    incomplete = [m for m in milestones if m.status != "done"]
    if incomplete:
        raise HTTPException(
            status_code=400,
            detail=f"还有 {len(incomplete)} 个里程碑未完成，不可发起验收",
        )
    unconfirmed = [
        m
        for m in milestones
        if (m.evidence_status or EVIDENCE_STATUS_NONE) != EVIDENCE_STATUS_CONFIRMED
    ]
    if unconfirmed:
        raise HTTPException(status_code=400, detail="存在里程碑证据未确认，不可验收")


def assert_can_confirm_evidence(user: User, project: Project) -> None:
    assert_can_manage_plan(user, project)


def review_milestone_evidence(
    db: Session,
    user: User,
    project_id: int,
    milestone_id: int,
    action: str,
    reason: Optional[str] = None,
) -> ProjectMilestone:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_confirm_evidence(user, project)

    ms = (
        db.query(ProjectMilestone)
        .filter(ProjectMilestone.id == milestone_id, ProjectMilestone.project_id == project_id)
        .first()
    )
    if not ms:
        raise HTTPException(status_code=404, detail="里程碑不存在")
    if project.status in {PROJECT_STATUS_INITIATING, PROJECT_STATUS_PLANNING}:
        raise HTTPException(status_code=400, detail="项目未进入执行，暂不可审核完成证据")
    if not (ms.evidence or "").strip():
        raise HTTPException(status_code=400, detail="尚无完成证据可确认")
    if action not in {"confirm", "reject"}:
        raise HTTPException(status_code=400, detail="无效操作")

    if action == "reject":
        if not (reason or "").strip():
            raise HTTPException(status_code=400, detail="驳回请填写原因")
        ms.evidence_status = EVIDENCE_STATUS_REJECTED
        ms.evidence_reject_reason = reason.strip()
        ms.evidence_confirmed_by = user.id
        ms.evidence_confirmed_at = datetime.now(timezone.utc)
        if ms.status == MILESTONE_STATUS_DONE:
            ms.status = MILESTONE_STATUS_DOING
        recalculate_project_progress(db, project)
        db.commit()
        db.refresh(ms)
        return enrich_milestone(db, ms)

    ms.evidence_status = EVIDENCE_STATUS_CONFIRMED
    ms.evidence_reject_reason = None
    ms.evidence_confirmed_by = user.id
    ms.evidence_confirmed_at = datetime.now(timezone.utc)
    _try_auto_complete_milestone(db, ms)
    recalculate_project_progress(db, project)

    db.commit()
    db.refresh(ms)
    return enrich_milestone(db, ms)


def add_milestone(db: Session, user: User, project_id: int, payload: MilestoneCreate) -> ProjectMilestone:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_manage_plan(user, project)
    if project.status in {PROJECT_STATUS_COMPLETED, PROJECT_STATUS_TERMINATED}:
        raise HTTPException(status_code=400, detail="已结束项目不可添加里程碑")

    # 创建时 evidence/remark 都视为「证据要求」，真正完成证据待执行阶段提交
    requirement = (payload.remark or payload.evidence or "").strip() or None
    ms = ProjectMilestone(
        project_id=project.id,
        name=payload.name.strip(),
        deadline=payload.deadline,
        actual_date=payload.actual_date,
        role=payload.role,
        deliverable=payload.deliverable,
        evidence=None,
        evidence_status=EVIDENCE_STATUS_NONE,
        sort_order=payload.sort_order,
        remark=requirement,
        status=MILESTONE_STATUS_PENDING,
    )
    db.add(ms)
    db.flush()
    recalculate_project_progress(db, project)
    db.commit()
    db.refresh(ms)
    return enrich_milestone(db, ms)


def delete_milestone(db: Session, user: User, project_id: int, milestone_id: int) -> None:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_manage_plan(user, project)
    if project.status in {PROJECT_STATUS_COMPLETED, PROJECT_STATUS_TERMINATED}:
        raise HTTPException(status_code=400, detail="已结束项目不可删除计划节点")

    ms = (
        db.query(ProjectMilestone)
        .filter(ProjectMilestone.id == milestone_id, ProjectMilestone.project_id == project_id)
        .first()
    )
    if not ms:
        raise HTTPException(status_code=404, detail="计划节点不存在")

    # 关联任务保留，仅解除挂接，避免误删工作记录
    (
        db.query(ProjectTask)
        .filter(ProjectTask.milestone_id == ms.id)
        .update({ProjectTask.milestone_id: None}, synchronize_session=False)
    )
    db.delete(ms)
    db.flush()
    recalculate_project_progress(db, project)
    db.commit()


def update_milestone(
    db: Session, user: User, project_id: int, milestone_id: int, payload: MilestoneUpdate
) -> ProjectMilestone:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)

    ms = (
        db.query(ProjectMilestone)
        .filter(ProjectMilestone.id == milestone_id, ProjectMilestone.project_id == project_id)
        .first()
    )
    if not ms:
        raise HTTPException(status_code=404, detail="里程碑不存在")

    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in MILESTONE_STATUSES:
        raise HTTPException(status_code=400, detail="无效的里程碑状态")

    # 仅提交/重提证据：可查看项目即可；其余字段变更需部门负责人/管理员
    evidence_only = set(data.keys()) <= {"evidence"}
    if evidence_only:
        pass
    else:
        assert_can_manage_plan(user, project)

    if "evidence" in data:
        if project.status in {PROJECT_STATUS_INITIATING, PROJECT_STATUS_PLANNING}:
            raise HTTPException(status_code=400, detail="项目未进入执行，暂不可提交完成证据")
        text = (data.get("evidence") or "").strip()
        data["evidence"] = text or None
        if not text:
            data["evidence_status"] = EVIDENCE_STATUS_NONE
            data["evidence_confirmed_by"] = None
            data["evidence_confirmed_at"] = None
            data["evidence_reject_reason"] = None
        else:
            # 新提交/修改证据后重新进入待确认；若曾误标完成则退回进行中
            data["evidence_status"] = EVIDENCE_STATUS_PENDING
            data["evidence_confirmed_by"] = None
            data["evidence_confirmed_at"] = None
            data["evidence_reject_reason"] = None
            data["status"] = MILESTONE_STATUS_DOING
            ms.evidence = text

    next_status = data.get("status", ms.status)
    if next_status == "done" and ms.status != "done":
        if "evidence" in data and data["evidence"] is not None:
            ms.evidence = data["evidence"]
        if "evidence_status" in data:
            ms.evidence_status = data["evidence_status"]
        assert_milestone_completable(db, ms)
        if not ms.actual_date:
            data.setdefault("actual_date", date.today())
    for k, v in data.items():
        setattr(ms, k, v)

    recalculate_project_progress(db, project)
    db.commit()
    db.refresh(ms)
    return enrich_milestone(db, ms)


def enrich_task(db: Session, task: ProjectTask) -> ProjectTask:
    project = db.query(Project).filter(Project.id == task.project_id).first()
    task.project_no = project.project_no if project else None  # type: ignore[attr-defined]
    task.project_name = project.name if project else None  # type: ignore[attr-defined]
    task.assignee_name = _user_name(db, task.assignee_id)  # type: ignore[attr-defined]
    if task.milestone_id:
        ms = db.query(ProjectMilestone).filter(ProjectMilestone.id == task.milestone_id).first()
        task.milestone_name = ms.name if ms else None  # type: ignore[attr-defined]
    else:
        task.milestone_name = None  # type: ignore[attr-defined]
    if task.department_id:
        dept = db.query(Department).filter(Department.id == task.department_id).first()
        task.department_name = dept.name if dept else None  # type: ignore[attr-defined]
    else:
        task.department_name = None  # type: ignore[attr-defined]
    if task.ticket_id:
        from app.models.ticket import Ticket

        linked = db.query(Ticket).filter(Ticket.id == task.ticket_id).first()
        task.ticket_no = linked.ticket_no if linked else None  # type: ignore[attr-defined]
    else:
        task.ticket_no = None  # type: ignore[attr-defined]
    if task.status == TASK_STATUS_DONE:
        task.due_status = "done"  # type: ignore[attr-defined]
    elif task.due_date and task.due_date < date.today():
        task.due_status = "overdue"  # type: ignore[attr-defined]
    else:
        task.due_status = "ok"  # type: ignore[attr-defined]
    task.schedule_booked = 0  # type: ignore[attr-defined]
    task.schedule_completed = 0  # type: ignore[attr-defined]
    return task


def _attach_task_schedule_counts(db: Session, tasks: list[ProjectTask]) -> None:
    if not tasks:
        return
    from app.models.schedule import (
        SCHEDULE_ACTIVE_STATUSES,
        SCHEDULE_STATUS_COMPLETED,
        Schedule,
    )

    task_ids = [t.id for t in tasks]
    rows = (
        db.query(Schedule.project_task_id, Schedule.status, func.count())
        .filter(Schedule.project_task_id.in_(task_ids))
        .group_by(Schedule.project_task_id, Schedule.status)
        .all()
    )
    booked: dict[int, int] = {}
    completed: dict[int, int] = {}
    for tid, st, cnt in rows:
        if not tid:
            continue
        n = int(cnt or 0)
        if st == SCHEDULE_STATUS_COMPLETED:
            completed[tid] = completed.get(tid, 0) + n
        elif st in SCHEDULE_ACTIVE_STATUSES:
            booked[tid] = booked.get(tid, 0) + n
    for t in tasks:
        t.schedule_booked = booked.get(t.id, 0)  # type: ignore[attr-defined]
        t.schedule_completed = completed.get(t.id, 0)  # type: ignore[attr-defined]

def create_task(db: Session, user: User, payload: ProjectTaskCreate) -> ProjectTask:
    project = db.query(Project).filter(Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    assert_can_view(user, project)
    assert_can_operate(user, project)

    assignee_id = payload.assignee_id or user.id
    assignee = db.query(User).filter(User.id == assignee_id).first()
    if not assignee:
        raise HTTPException(status_code=400, detail="责任人不存在")

    open_milestone_count = (
        db.query(ProjectMilestone)
        .filter(
            ProjectMilestone.project_id == project.id,
            ProjectMilestone.status != MILESTONE_STATUS_DONE,
        )
        .count()
    )
    if open_milestone_count and not payload.milestone_id:
        raise HTTPException(status_code=400, detail="请选择所属里程碑")

    if payload.milestone_id:
        ms = (
            db.query(ProjectMilestone)
            .filter(
                ProjectMilestone.id == payload.milestone_id,
                ProjectMilestone.project_id == project.id,
            )
            .first()
        )
        if not ms:
            raise HTTPException(status_code=400, detail="里程碑不存在")
        if ms.status == "done":
            raise HTTPException(status_code=400, detail="已完成里程碑不可再挂新任务")

    from app.services import project_resource as resource_service

    resource_service.assert_task_hours_within_budget(
        db, project.id, payload.planned_hours or Decimal("0")
    )

    task = ProjectTask(
        task_no=_gen_task_no(db),
        project_id=project.id,
        milestone_id=payload.milestone_id,
        title=payload.title.strip(),
        criteria=payload.criteria,
        assignee_id=assignee_id,
        department_id=assignee.department_id,
        due_date=payload.due_date,
        planned_hours=payload.planned_hours or Decimal("0"),
        actual_hours=Decimal("0"),
        status=TASK_STATUS_DOING if payload.due_date else TASK_STATUS_PENDING,
        remark=payload.remark,
        creator_id=user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return enrich_task(db, task)


def update_task(db: Session, user: User, task_id: int, payload: ProjectTaskUpdate) -> ProjectTask:
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    data = payload.model_dump(exclude_unset=True)
    assert_can_update_task(user, project, task, data)

    if "status" in data and data["status"] not in TASK_STATUSES:
        raise HTTPException(status_code=400, detail="无效的任务状态")
    if data.get("status") == TASK_STATUS_DONE:
        if "actual_hours" not in data:
            raise HTTPException(status_code=400, detail="完成任务须填写实际工时")
        if data["actual_hours"] is None or Decimal(str(data["actual_hours"])) < 0:
            raise HTTPException(status_code=400, detail="实际工时不能为空或负数")
    if "planned_hours" in data and data["planned_hours"] is not None:
        from app.services import project_resource as resource_service

        resource_service.assert_task_hours_within_budget(
            db,
            project.id,
            Decimal(str(data["planned_hours"])),
            exclude_task_id=task.id,
        )
    if "assignee_id" in data and data["assignee_id"] is not None:
        assignee = db.query(User).filter(User.id == data["assignee_id"]).first()
        if not assignee:
            raise HTTPException(status_code=400, detail="责任人不存在")
        task.department_id = assignee.department_id
    for k, v in data.items():
        setattr(task, k, v)

    if task.status == TASK_STATUS_DONE and task.milestone_id:
        ms = db.query(ProjectMilestone).filter(ProjectMilestone.id == task.milestone_id).first()
        if ms:
            _try_auto_complete_milestone(db, ms)

    db.commit()
    db.refresh(task)
    return enrich_task(db, task)


def list_tasks(
    db: Session,
    user: User,
    *,
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    scope_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[ProjectTask]]:
    q = db.query(ProjectTask).join(Project, Project.id == ProjectTask.project_id)
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    scope = widest_data_scope(collect_data_scopes(user)) if not is_admin else "company"

    if scope_filter == "mine":
        q = q.filter(ProjectTask.assignee_id == user.id)
    elif not is_admin:
        if scope == "personal":
            q = q.filter(
                or_(
                    ProjectTask.assignee_id == user.id,
                    Project.manager_id == user.id,
                    Project.creator_id == user.id,
                )
            )
        elif scope == "department" and user.department_id:
            q = q.filter(
                or_(
                    Project.department_id == user.department_id,
                    ProjectTask.assignee_id == user.id,
                    ProjectTask.department_id == user.department_id,
                )
            )

    if project_id:
        q = q.filter(ProjectTask.project_id == project_id)
    if status:
        if status == "overdue":
            q = q.filter(
                ProjectTask.status != TASK_STATUS_DONE,
                ProjectTask.due_date.isnot(None),
                ProjectTask.due_date < date.today(),
            )
        elif status == "open":
            q = q.filter(ProjectTask.status != TASK_STATUS_DONE)
        else:
            q = q.filter(ProjectTask.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                ProjectTask.title.ilike(like),
                ProjectTask.task_no.ilike(like),
                Project.name.ilike(like),
            )
        )

    total = q.count()
    items = (
        q.order_by(ProjectTask.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    enriched = [enrich_task(db, x) for x in items]
    _attach_task_schedule_counts(db, enriched)
    return total, enriched


def task_stats(db: Session, user: User) -> dict:
    _, items = list_tasks(db, user, page=1, page_size=5000)
    mine = 0
    overdue = 0
    planned = Decimal("0")
    actual = Decimal("0")
    for t in items:
        if t.assignee_id == user.id and t.status != TASK_STATUS_DONE:
            mine += 1
        if getattr(t, "due_status", None) == "overdue":
            overdue += 1
        planned += t.planned_hours or Decimal("0")
        actual += t.actual_hours or Decimal("0")

    linked = 0
    try:
        from app.models.ticket import Ticket

        project_ids = {t.project_id for t in items}
        if project_ids:
            linked = db.query(Ticket).filter(Ticket.project_id.in_(project_ids)).count()
    except Exception:
        linked = 0

    return {
        "mine": mine,
        "overdue": overdue,
        "planned_hours": planned,
        "actual_hours": actual,
        "linked_tickets": linked,
    }


def project_stats(db: Session, user: User) -> dict:
    def _count(*, status: Optional[str] = None, scope_filter: Optional[str] = None) -> int:
        total, _ = list_projects(
            db,
            user,
            status=status,
            scope_filter=scope_filter,
            page=1,
            page_size=1,
            enrich=False,
        )
        return total

    _, all_items = list_projects(db, user, page=1, page_size=5000, enrich=False)
    high_risk = sum(1 for p in all_items if compute_health(p) == "risk")
    leftover = sum(1 for p in all_items if p.leftover_summary and not p.leftover_closed)

    return {
        "total": _count(),
        "initiating": _count(status=PROJECT_STATUS_INITIATING),
        "planning": _count(status=PROJECT_STATUS_PLANNING),
        "executing": _count(status=PROJECT_STATUS_EXECUTING),
        "accepting": _count(status=PROJECT_STATUS_ACCEPTING),
        "accepted": _count(status=PROJECT_STATUS_ACCEPTED),
        "completed": _count(status=PROJECT_STATUS_COMPLETED),
        "terminated": _count(status=PROJECT_STATUS_TERMINATED),
        "mine": _count(scope_filter="mine"),
        "high_risk": high_risk,
        "leftover": leftover,
    }


def department_monitor(db: Session, user: User) -> dict:
    """部门负责人视角：按本部门（或全公司管理员）汇总任务执行。"""
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    dept_id = user.department_id
    dept_name = None
    if dept_id:
        d = db.query(Department).filter(Department.id == dept_id).first()
        dept_name = d.name if d else None

    _, tasks = list_tasks(db, user, page=1, page_size=5000)
    if not is_admin and dept_id:
        filtered = []
        for t in tasks:
            if t.department_id == dept_id:
                filtered.append(t)
                continue
            if t.assignee_id:
                u = db.query(User).filter(User.id == t.assignee_id).first()
                if u and u.department_id == dept_id:
                    filtered.append(t)
        tasks = filtered

    by_user: dict[int, dict] = {}
    overdue_total = 0
    missing_hours = 0
    done_or_ontime = 0
    total_active = 0
    planned_sum = Decimal("0")
    actual_sum = Decimal("0")

    for t in tasks:
        uid = t.assignee_id or 0
        if uid not in by_user:
            by_user[uid] = {
                "user_id": uid,
                "name": getattr(t, "assignee_name", None) or "未分配",
                "planned_tasks": 0,
                "done_tasks": 0,
                "overdue_tasks": 0,
                "planned_hours": Decimal("0"),
                "actual_hours": Decimal("0"),
            }
        row = by_user[uid]
        row["planned_tasks"] += 1
        ph = t.planned_hours or Decimal("0")
        ah = t.actual_hours or Decimal("0")
        row["planned_hours"] += ph
        row["actual_hours"] += ah
        planned_sum += ph
        actual_sum += ah
        if t.status == TASK_STATUS_DONE:
            row["done_tasks"] += 1
            done_or_ontime += 1
        else:
            total_active += 1
            if getattr(t, "due_status", None) == "overdue":
                row["overdue_tasks"] += 1
                overdue_total += 1
            else:
                done_or_ontime += 1
        if t.status != TASK_STATUS_DONE and ph > 0 and ah <= 0:
            missing_hours += 1

    members = []
    for row in by_user.values():
        ph = row["planned_hours"]
        ah = row["actual_hours"]
        rate = Decimal("100") if ph <= 0 else min(Decimal("100"), (ah * 100 / ph).quantize(Decimal("0.1")))
        members.append(
            {
                **row,
                "hours_complete_rate": rate,
                "open_tickets": 0,
            }
        )
    members.sort(key=lambda x: (-x["overdue_tasks"], -x["planned_tasks"]))

    # 工单粗算
    try:
        from app.models.ticket import Ticket

        for m in members:
            if not m["user_id"]:
                continue
            m["open_tickets"] = (
                db.query(Ticket)
                .filter(
                    Ticket.assignee_id == m["user_id"],
                    Ticket.status.in_(
                        ["pending_assign", "pending_accept", "processing", "pending_confirm"]
                    ),
                )
                .count()
            )
    except Exception:
        pass

    total_tasks = len(tasks) or 1
    on_time = Decimal(str(round((done_or_ontime / total_tasks) * 100, 1)))
    hours_rate = (
        Decimal("100")
        if planned_sum <= 0
        else min(Decimal("100"), (actual_sum * 100 / planned_sum).quantize(Decimal("0.1")))
    )
    health = int(max(0, min(100, float(on_time) * 0.6 + float(hours_rate) * 0.4 - overdue_total * 2)))

    return {
        "department_id": dept_id,
        "department_name": dept_name or ("全公司" if is_admin else "未分配部门"),
        "health_score": health,
        "on_time_rate": on_time,
        "hours_complete_rate": hours_rate,
        "overdue_tasks": overdue_total,
        "missing_hours": missing_hours,
        "members": members,
    }


_ = user_can
_ = _now
