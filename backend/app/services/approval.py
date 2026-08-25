"""审批中心聚合：引擎实例 + 遗留核销/绩效申诉。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.rbac import user_can
from app.models.audit_log import AuditLog
from app.models.contract import Contract
from app.models.department import Department
from app.models.finance import (
    ALLOCATION_STATUS_ACTIVE,
    ALLOCATION_STATUS_PENDING,
    ALLOCATION_STATUS_REJECTED,
    Receipt,
    ReceiptAllocation,
    ReceivablePlan,
)
from app.models.performance import APPEAL_PENDING, PerformanceAppeal, PerformanceAssessment
from app.models.user import User
from app.schemas.approval import (
    ApprovalActRequest,
    ApprovalActResult,
    ApprovalDetailOut,
    ApprovalFact,
    ApprovalItemOut,
    ApprovalListOut,
    ApprovalStatsOut,
    ApprovalTimelineNode,
)
from app.schemas.finance import AllocationReviewRequest
from app.schemas.performance import AppealResolveRequest


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


def _can_review_receipt(user: User) -> bool:
    return (
        user_can(user, "payment:confirm")
        or user_can(user, "payment:manage")
        or "admin" in {r.code for r in user.roles}
    )


def _can_resolve_appeal(user: User) -> bool:
    if user_can(user, "org:manage"):
        return True
    role_codes = {r.code for r in user.roles}
    return bool(role_codes & {"executive", "middle_manager", "hr_supervisor"})


def _contract_brief(db: Session, contract_id: int | None) -> str:
    if not contract_id:
        return "—"
    c = db.query(Contract).filter(Contract.id == contract_id).first()
    if not c:
        return f"#{contract_id}"
    no = c.contract_no or str(c.id)
    title = (c.title or "").strip()
    return f"{no} · {title}" if title else no


def _allocation_facts(
    db: Session, a: ReceiptAllocation, r: Receipt, plan: ReceivablePlan
) -> list[ApprovalFact]:
    return [
        ApprovalFact(label="核销金额", value=f"¥{a.amount}"),
        ApprovalFact(label="应收计划", value=plan.title or "—"),
        ApprovalFact(label="收款单号", value=r.receipt_no or "—"),
        ApprovalFact(label="关联合同", value=_contract_brief(db, r.contract_id)),
        ApprovalFact(label="付款方", value=r.payer_name or "—"),
    ]


def _receipt_deep_link(contract_id: int | None) -> str:
    if contract_id:
        return f"/contracts/{contract_id}"
    return "/sales?tab=contracts"


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


# ---------------------------------------------------------------------------
# 遗留：收款核销 / 绩效申诉（尚未完整进引擎）
# ---------------------------------------------------------------------------


def _legacy_pending_allocation(db: Session, user: User) -> list[ApprovalItemOut]:
    if not _can_review_receipt(user):
        return []
    items: list[ApprovalItemOut] = []
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
                category="收款核销",
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
                facts=_allocation_facts(db, a, r, plan),
                deep_link=_receipt_deep_link(r.contract_id),
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
    return items


def _legacy_pending_appeal(db: Session, user: User) -> list[ApprovalItemOut]:
    if not _can_resolve_appeal(user):
        return []
    items: list[ApprovalItemOut] = []
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
    return items


def _legacy_initiated_allocation(db: Session, user: User) -> list[ApprovalItemOut]:
    items: list[ApprovalItemOut] = []
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
                category="收款核销",
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
                facts=_allocation_facts(db, a, r, plan),
                deep_link=_receipt_deep_link(r.contract_id),
                can_act=False,
                actions=["open"],
                meta={
                    "entity_id": a.id,
                    "version": a.version,
                    "contract_id": r.contract_id,
                },
            )
        )
    return items


def _legacy_initiated_appeal(db: Session, user: User) -> list[ApprovalItemOut]:
    items: list[ApprovalItemOut] = []
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
    return items


def _legacy_processed_allocation(db: Session, user: User) -> list[ApprovalItemOut]:
    items: list[ApprovalItemOut] = []
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
                category="收款核销",
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
                facts=_allocation_facts(db, a, r, plan),
                deep_link=_receipt_deep_link(r.contract_id),
                can_act=False,
                actions=["open"],
                meta={"entity_id": a.id, "contract_id": r.contract_id},
            )
        )
    return items


def _collect_pending_for_actor(db: Session, user: User) -> list[ApprovalItemOut]:
    from app.services import approval_flow

    items: list[ApprovalItemOut] = []
    items.extend(_legacy_pending_allocation(db, user))
    items.extend(_legacy_pending_appeal(db, user))
    items.extend(approval_flow.pending_items_for(db, user))
    items.sort(key=lambda x: x.submitted_at or datetime.min, reverse=True)
    return _attach_published_rules(db, items)


def list_pending_approvals(
    db: Session, user: User, *, limit: Optional[int] = None
) -> list[ApprovalItemOut]:
    """公开接口：当前用户待办审批列表（供审批中心 / 我的待办复用）。"""
    items = _collect_pending_for_actor(db, user)
    if limit is None:
        return items
    return items[: max(0, limit)]


def _attach_published_rules(db: Session, items: list[ApprovalItemOut]) -> list[ApprovalItemOut]:
    """把已发布审批规则挂到条目 meta（审批人判定仍走领域角色，规则先承载版本/时限展示）。"""
    from app.services import approval_rule as rule_service

    cache: dict[str, object] = {}
    out: list[ApprovalItemOut] = []
    for item in items:
        if item.type not in cache:
            cache[item.type] = rule_service.get_published_rule(db, item.type)
        rule = cache[item.type]
        if not rule:
            out.append(item)
            continue
        meta = dict(item.meta or {})
        meta["rule_id"] = getattr(rule, "id", None)
        meta["rule_code"] = getattr(rule, "code", None)
        meta["rule_version"] = getattr(rule, "version", None)
        meta["rule_timeout_hours"] = getattr(rule, "timeout_hours", None)
        node = item.node
        if getattr(rule, "name", None) and (not node or node == "—"):
            node = str(rule.name)
        out.append(item.model_copy(update={"meta": meta, "node": node}))
    return out


def _collect_initiated(db: Session, user: User) -> list[ApprovalItemOut]:
    from app.services import approval_flow

    items: list[ApprovalItemOut] = []
    items.extend(_legacy_initiated_allocation(db, user))
    items.extend(_legacy_initiated_appeal(db, user))
    items.extend(approval_flow.initiated_items_for(db, user))
    items.sort(key=lambda x: x.submitted_at or datetime.min, reverse=True)
    return items


def _collect_processed(db: Session, user: User) -> list[ApprovalItemOut]:
    from app.services import approval_flow

    items: list[ApprovalItemOut] = []
    items.extend(_legacy_processed_allocation(db, user))
    items.extend(approval_flow.processed_items_for(db, user))
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
        from app.services import approval_flow

        items = approval_flow.cc_items_for(db, user)
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
    from app.services import approval_flow

    return ApprovalStatsOut(
        pending=len(_collect_pending_for_actor(db, user)),
        initiated=len(_collect_initiated(db, user)),
        processed=len(_collect_processed(db, user)),
        cc=len(approval_flow.cc_items_for(db, user)),
    )


def _collect_cc(db: Session, user: User) -> list[ApprovalItemOut]:
    from app.services import approval_flow

    return approval_flow.cc_items_for(db, user)


def _find_approval_item(db: Session, user: User, approval_id: str) -> Optional[ApprovalItemOut]:
    for collector in (
        _collect_pending_for_actor,
        _collect_initiated,
        _collect_processed,
        _collect_cc,
    ):
        for item in collector(db, user):
            if item.id == approval_id:
                return item
    # 深链兜底：有审批中心权限的用户可直接打开引擎实例详情
    from app.services import approval_flow

    if approval_id.startswith(f"{approval_flow.ITEM_PREFIX}:"):
        try:
            instance = approval_flow.get_instance_by_item_id(db, approval_id)
        except HTTPException:
            return None
        return approval_flow._instance_to_item(db, instance, can_act=False)
    return None


def resolve_open_approval(
    db: Session, user: User, *, biz_type: str, biz_id: int
) -> dict[str, str]:
    """业务页 → 审批中心深链：解析进行中实例 id。"""
    from app.services import approval_flow

    bt = (biz_type or "").strip()
    types: list[str]
    if bt == "contract":
        types = [
            "contract",
            "contract_activate",
            "contract_modify",
            "contract_terminate",
        ]
    else:
        types = [bt]
    item_id = approval_flow.find_open_item_id(db, bt, biz_id, biz_types=types)
    if not item_id:
        raise HTTPException(status_code=404, detail="未找到进行中的审批单")
    return {"id": item_id, "biz_type": bt}


def _parse_approval_id(approval_id: str) -> tuple[str, int]:
    parts = approval_id.split(":")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="无效的审批单号")
    biz_type = parts[0]
    try:
        entity_id = int(parts[1])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="无效的审批单号") from exc
    return biz_type, entity_id


def _build_timeline(item: ApprovalItemOut) -> list[ApprovalTimelineNode]:
    submitted = ApprovalTimelineNode(
        name="提交申请",
        status="done",
        actor_name=item.applicant_name,
        acted_at=item.submitted_at,
    )
    if item.can_act:
        current_status = "pending"
        current_comment = "待你处理"
    elif item.status_label.startswith("已"):
        current_status = "done"
        current_comment = None
    else:
        current_status = "active"
        current_comment = "等待审批人处理"

    if item.type == "allocation" and item.can_act:
        current_comment = "核对核销金额与合同应收"
    elif item.type == "appeal" and item.can_act:
        current_comment = "复核绩效申诉"

    current = ApprovalTimelineNode(
        name=item.node or "当前节点",
        status=current_status,
        comment=current_comment,
    )
    nodes = [submitted, current]
    if item.type == "allocation" and item.can_act:
        nodes.append(
            ApprovalTimelineNode(
                name="计入应收",
                status="waiting",
                comment="审批通过后生效",
            )
        )
    return nodes


def get_approval(db: Session, user: User, approval_id: str) -> ApprovalDetailOut:
    item = _find_approval_item(db, user, approval_id)
    if not item:
        raise HTTPException(status_code=404, detail="审批单不存在")
    from app.services import approval_flow

    if item.type == approval_flow.ITEM_PREFIX:
        instance = approval_flow.get_instance_by_item_id(db, approval_id)
        timeline = approval_flow.instance_timeline(instance, db)
    else:
        timeline = _build_timeline(item)
    rule_version = item.meta.get("rule_version") if isinstance(item.meta, dict) else None
    if rule_version is not None:
        try:
            rule_version = int(rule_version)
        except (TypeError, ValueError):
            rule_version = None
    return ApprovalDetailOut(
        **item.model_dump(),
        timeline=timeline,
        nodes=timeline,
        rule_version=rule_version,
    )


def _write_approval_audit(
    db: Session,
    user: User,
    *,
    action: str,
    approval_id: str,
    detail: str,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            action=action,
            module="approval",
            target_type="approval",
            target_id=approval_id,
            detail=detail,
        )
    )
    db.commit()


def _stub_act(
    db: Session,
    user: User,
    approval_id: str,
    action: str,
    message: str,
    payload: ApprovalActRequest,
) -> ApprovalActResult:
    bits = [message]
    if payload.comment:
        bits.append(f"comment={payload.comment}")
    if payload.reason:
        bits.append(f"reason={payload.reason}")
    if payload.target_user_id:
        bits.append(f"target_user_id={payload.target_user_id}")
    _write_approval_audit(
        db,
        user,
        action=f"approval_{action}",
        approval_id=approval_id,
        detail="; ".join(bits),
    )
    return ApprovalActResult(ok=True, message=message, approval_id=approval_id, action=action)


def _dispatch_approve_reject(
    db: Session,
    user: User,
    *,
    biz_type: str,
    entity_id: int,
    approve: bool,
    payload: ApprovalActRequest,
    item: ApprovalItemOut,
) -> None:
    from app.services import finance as finance_service
    from app.services import performance as perf_service

    reason = (payload.reason or payload.comment or "").strip() or None
    remark = payload.comment or payload.reason

    if biz_type == "allocation":
        version = item.meta.get("version")
        if version is None:
            row = (
                db.query(ReceiptAllocation)
                .filter(ReceiptAllocation.id == entity_id)
                .first()
            )
            if not row:
                raise HTTPException(status_code=404, detail="核销记录不存在")
            version = row.version
        finance_service.review_allocation(
            db,
            user,
            entity_id,
            AllocationReviewRequest(remark=remark, version=int(version)),
            approve=approve,
        )
        return

    if biz_type == "appeal":
        resolution = (reason or ("同意申诉" if approve else "驳回申诉")).strip()
        perf_service.resolve_appeal(
            db,
            user,
            entity_id,
            AppealResolveRequest(approve=approve, resolution=resolution),
        )
        return

    raise HTTPException(status_code=400, detail=f"不支持的审批类型: {biz_type}")


def _act_instance(
    db: Session,
    user: User,
    approval_id: str,
    instance_id: int,
    action: str,
    payload: ApprovalActRequest,
) -> ApprovalActResult:
    """审批流实例的动作路由（通过/驳回/撤回/催办）。"""
    from app.services import approval_flow

    instance = approval_flow.get_instance(db, instance_id)
    comment = (payload.comment or payload.reason or "").strip() or None

    if action in ("approve", "reject"):
        approval_flow.act(db, user, instance, approve=(action == "approve"), comment=comment)
        return ApprovalActResult(
            ok=True,
            message="已通过" if action == "approve" else "已驳回",
            approval_id=approval_id,
            action=action,
        )
    if action == "withdraw":
        approval_flow.withdraw(db, user, instance)
        return ApprovalActResult(ok=True, message="已撤回", approval_id=approval_id, action=action)
    if action == "remind":
        return _stub_act(db, user, approval_id, action, "催办提醒已记录", payload)
    raise HTTPException(
        status_code=400,
        detail="审批流单据暂不支持该动作；驳回后请由发起人重新发起",
    )


def act_approval(
    db: Session,
    user: User,
    approval_id: str,
    action: str,
    payload: Optional[ApprovalActRequest] = None,
) -> ApprovalActResult:
    payload = payload or ApprovalActRequest()
    action = action.strip().lower()
    allowed = {"approve", "reject", "return", "transfer", "remind", "withdraw", "resubmit"}
    if action not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持的动作: {action}")

    item = _find_approval_item(db, user, approval_id)
    if not item:
        raise HTTPException(status_code=404, detail="审批单不存在")

    biz_type, entity_id = _parse_approval_id(approval_id)

    from app.services import approval_flow

    if biz_type == approval_flow.ITEM_PREFIX:
        return _act_instance(db, user, approval_id, entity_id, action, payload)

    if action in ("approve", "reject"):
        _dispatch_approve_reject(
            db,
            user,
            biz_type=biz_type,
            entity_id=entity_id,
            approve=(action == "approve"),
            payload=payload,
            item=item,
        )
        label = "已通过" if action == "approve" else "已驳回"
        return ApprovalActResult(
            ok=True,
            message=label,
            approval_id=approval_id,
            action=action,
        )

    if action == "withdraw":
        initiated_ids = {x.id for x in _collect_initiated(db, user)}
        base_id = f"{biz_type}:{entity_id}"
        if approval_id not in initiated_ids and base_id not in initiated_ids:
            raise HTTPException(status_code=403, detail="仅发起人可撤回")
        return _stub_act(
            db,
            user,
            approval_id,
            action,
            "撤回请求已记录（该业务暂未开放完整撤回）",
            payload,
        )

    messages = {
        "return": "退回请求已记录（该业务暂未开放完整退回）",
        "transfer": "转交请求已记录（该业务暂未开放完整转交）",
        "remind": "催办提醒已记录",
        "resubmit": "重新提交请求已记录（该业务暂未开放完整重提）",
    }
    return _stub_act(db, user, approval_id, action, messages[action], payload)
