"""通用审批流引擎服务。

职责：
- 从 approval_rules 读取节点/条件配置，按业务事实（金额等）命中规则
- 发起审批实例、逐级串行推进、会签、禁止自审、驳回/撤回
- 向审批中心提供待办/已办快照，向业务域派发通过/驳回回调

规则配置约定（存 approval_rules）：
  nodes_json = {
    "nodes": [
      {"name":"总经理审批","type":"approve","roles":["executive","board"]},
      {"name":"财务负责人执行退款","type":"execute","roles":["finance"]},
      {"name":"财务+行政会签","type":"countersign","groups":[
          {"label":"财务","roles":["finance"]},
          {"label":"行政主管","roles":["admin_office","operations"]}]}
    ],
    "cc": ["board","finance"]
  }
  conditions_json = {"when": {"field":"amount","op":"lt","value":10000}}  # 可空=默认规则
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.approval_flow import (
    ACTOR_NODE_TYPES,
    INSTANCE_APPROVED,
    INSTANCE_BLOCKED,
    INSTANCE_OPEN_STATUSES,
    INSTANCE_PENDING,
    INSTANCE_REJECTED,
    INSTANCE_WITHDRAWN,
    NODE_ASSIGNEE,
    NODE_COUNTERSIGN,
    TASK_ACTIVE,
    TASK_APPROVED,
    TASK_REJECTED,
    TASK_SKIPPED,
    TASK_WAITING,
    ApprovalInstance,
    ApprovalTask,
)
from app.models.approval_rule import RULE_STATUS_PUBLISHED, ApprovalRule
from app.models.audit_log import AuditLog
from app.models.platform import Delegation
from app.models.role import Role
from app.models.user import User
from app.schemas.approval import ApprovalFact, ApprovalItemOut, ApprovalTimelineNode


# N-03：高风险流程不允许代理（合同族、退款、资产赔偿）
HIGH_RISK_BIZ_TYPES: frozenset[str] = frozenset({
    "refund",
    "contract",
    "contract_activate",
    "contract_terminate",
    "contract_modify",
    "asset_compensation",
})


def _now() -> datetime:
    return datetime.now(timezone.utc)


# —— 业务类型 → 审批中心展示分类 ——
BIZ_CATEGORY: dict[str, str] = {
    "refund": "财务退款",
    "contract": "销售合同",
    "contract_activate": "销售合同",
    "contract_modify": "销售合同",
    "contract_terminate": "销售合同",
    "project_no_contract": "项目立项",
    "project_initiation": "项目立项",
    "project_handover": "项目交付",
    "project_acceptance": "项目交付",
    "project_settlement": "项目交付",
    "project_terminate": "项目交付",
    "timesheet": "工时审批",
    "receipt": "收款到账",
    "receipt_diff": "收款到账",
    "asset_borrow": "固定资产",
    "asset_return": "固定资产",
    "asset_maintenance": "固定资产",
    "asset_inventory_diff": "固定资产",
    "asset_compensation": "固定资产",
    "role_change": "组织权限",
    "ticket": "协作工单",
    "ticket_cross_accept": "协作工单",
    "schedule": "排期会议",
}


def biz_category(biz_type: str) -> str:
    return BIZ_CATEGORY.get(biz_type, "审批流程")


def approval_title(label: str, detail: str) -> str:
    """审批中心事项标题：类型 · 中文描述（单号单独展示，不写入标题）。"""
    detail = (detail or "").strip()
    return f"{label} · {detail}" if detail else label


def borrow_asset_title(db: Session, label: str, request_id: int, fallback_detail: str = "") -> str:
    """资产借用类审批标题：优先展示设备名称（苹果5、VivoS18Pro…），无设备时回退用途说明。"""
    from app.models.asset import AssetBorrowItem, FixedAsset

    rows = (
        db.query(FixedAsset.name)
        .join(AssetBorrowItem, AssetBorrowItem.asset_id == FixedAsset.id)
        .filter(AssetBorrowItem.request_id == request_id)
        .order_by(AssetBorrowItem.id)
        .all()
    )
    names = [r[0] for r in rows if r[0]]
    if names:
        shown = "、".join(names[:3])
        if len(names) > 3:
            shown += f" 等{len(names)}件"
        return approval_title(label, shown)
    return approval_title(label, (fallback_detail or "").strip())


def _display_title(db: Session, instance: ApprovalInstance) -> str:
    """列表展示用标题：优先从业务实体取中文描述，兼容历史带编码标题。"""
    bid = instance.biz_id
    if not bid:
        return instance.title or ""
    bt = instance.biz_type or ""
    try:
        if bt == "asset_borrow":
            from app.models.asset import AssetBorrowRequest

            br = db.query(AssetBorrowRequest).filter(AssetBorrowRequest.id == bid).first()
            if br:
                return borrow_asset_title(db, "资产领用", br.id, br.purpose or "")
        elif bt == "asset_return":
            from app.models.asset import AssetBorrowRequest

            br = db.query(AssetBorrowRequest).filter(AssetBorrowRequest.id == bid).first()
            if br:
                return borrow_asset_title(db, "资产归还确认", br.id, br.purpose or "")
        elif bt in {"ticket", "ticket_cross_accept"}:
            from app.models.ticket import Ticket

            ticket = db.query(Ticket).filter(Ticket.id == bid).first()
            if ticket and ticket.title:
                label = "工单接单" if bt == "ticket" else "跨部门工单验收"
                return approval_title(label, ticket.title)
        elif bt == "schedule":
            from app.models.schedule import Schedule

            item = db.query(Schedule).filter(Schedule.id == bid).first()
            if item and item.title:
                return approval_title("排期确认", item.title)
        elif bt.startswith("project"):
            from app.models.project import Project

            project = db.query(Project).filter(Project.id == bid).first()
            if project and project.name:
                labels = {
                    "project_no_contract": (
                        "无到款立项" if project.contract_id else "无合同立项"
                    ),
                    "project_initiation": "项目立项",
                    "project_handover": "项目交接确认",
                    "project_acceptance": "项目验收",
                    "project_settlement": "结项归档核验",
                    "project_terminate": "终止项目",
                }
                label = labels.get(bt)
                if label:
                    return approval_title(label, project.name)
    except Exception:
        pass
    return instance.title or ""


# ---------------------------------------------------------------------------
# 规则解析与命中
# ---------------------------------------------------------------------------
def _loads(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _match_condition(cond: Any, facts: dict[str, Any]) -> bool:
    """cond 形如 {"when": {"field","op","value"}}；空/无 when 视为默认命中。"""
    if not cond:
        return True
    when = cond.get("when") if isinstance(cond, dict) else None
    if not when:
        return True
    field = when.get("field")
    op = (when.get("op") or "eq").lower()
    expected = when.get("value")
    actual = facts.get(field)
    if actual is None:
        return False
    try:
        a = Decimal(str(actual))
        b = Decimal(str(expected))
    except (InvalidOperation, TypeError):
        a, b = actual, expected
    return {
        "lt": a < b,
        "lte": a <= b,
        "le": a <= b,
        "gt": a > b,
        "gte": a >= b,
        "ge": a >= b,
        "eq": a == b,
        "ne": a != b,
    }.get(op, False)


def select_rule(db: Session, biz_type: str, facts: dict[str, Any]) -> Optional[ApprovalRule]:
    """在该业务类型的已发布规则中，取第一条条件命中的（无条件的作为兜底默认）。"""
    rules = (
        db.query(ApprovalRule)
        .filter(
            ApprovalRule.biz_type == biz_type,
            ApprovalRule.status == RULE_STATUS_PUBLISHED,
        )
        .order_by(ApprovalRule.id.asc())
        .all()
    )
    fallback: Optional[ApprovalRule] = None
    for rule in rules:
        cond = _loads(rule.conditions_json)
        if not cond or not (isinstance(cond, dict) and cond.get("when")):
            fallback = fallback or rule
            continue
        if _match_condition(cond, facts):
            return rule
    return fallback


def _rule_nodes(rule: ApprovalRule) -> tuple[list[dict], list[str]]:
    cfg = _loads(rule.nodes_json) or {}
    nodes = cfg.get("nodes") if isinstance(cfg, dict) else None
    if not isinstance(nodes, list):
        raise HTTPException(status_code=500, detail=f"审批规则 {rule.code} 节点配置无效")
    cc = cfg.get("cc") if isinstance(cfg, dict) else None
    cc_list = [str(c) for c in cc] if isinstance(cc, list) else []
    return nodes, cc_list


# ---------------------------------------------------------------------------
# 审批人解析
# ---------------------------------------------------------------------------
def _role_holder_ids(db: Session, role_codes: Iterable[str], *, exclude_id: Optional[int]) -> set[int]:
    """启用状态、且拥有任一角色码的用户 id 集合；按 G-08 排除发起人。

    注意：系统管理员(admin)不作为审批兜底（职责分离，见配置表 sysadmin 说明），
    只有规则显式列出 admin 才会命中。
    """
    codes = [c for c in role_codes if c]
    if not codes:
        return set()
    rows = (
        db.query(User.id)
        .join(User.roles)
        .filter(Role.code.in_(codes), User.is_active.is_(True))
        .all()
    )
    ids = {r[0] for r in rows}
    if exclude_id is not None:
        ids.discard(exclude_id)
    return ids


def _task_roles(task: ApprovalTask) -> list[str]:
    val = _loads(task.roles_json)
    return [str(x) for x in val] if isinstance(val, list) else []


def _user_role_codes(user: User) -> set[str]:
    return {r.code for r in (user.roles or [])}


def _is_flow_superuser(user: User) -> bool:
    """系统管理员（role=admin）：可代审任意节点，含本人发起与无人节点。"""
    return "admin" in _user_role_codes(user)


def _flow_superuser_ids(db: Session) -> set[int]:
    rows = (
        db.query(User.id)
        .join(User.roles)
        .filter(Role.code == "admin", User.is_active.is_(True))
        .all()
    )
    return {r[0] for r in rows}


def _direct_actor_ids(db: Session, task: ApprovalTask, instance: ApprovalInstance) -> set[int]:
    """任务本人（非代理）能处理的用户 id：指定人 or 角色 holder（去发起人）。"""
    if task.assignee_id is not None:
        return {task.assignee_id}
    roles = _task_roles(task)
    if not roles:
        return set()
    ids = _role_holder_ids(db, roles, exclude_id=None)
    if instance.initiator_id is not None:
        ids.discard(instance.initiator_id)
    return ids


def _tz_normalize(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _active_delegations_for_grantee(db: Session, grantee_id: int, at_time: datetime) -> list[Delegation]:
    """当前时刻，某人作为被委托人生效的所有委托（SQLite/PG 通用，避免 naive/aware 混用）。"""
    at = _tz_normalize(at_time)
    rows = (
        db.query(Delegation)
        .filter(
            Delegation.grantee_id == grantee_id,
            Delegation.status == "active",
        )
        .all()
    )
    out: list[Delegation] = []
    for r in rows:
        starts = _tz_normalize(r.starts_at)
        ends = _tz_normalize(r.ends_at)
        if starts is not None and starts > at:
            continue
        if ends is not None and ends <= at:
            continue
        out.append(r)
    return out


def _delegation_covers(delegation: Delegation, biz_type: str) -> bool:
    """委托是否覆盖该 biz_type（空 biz_types_json = 覆盖全部）。"""
    if not delegation.biz_types_json:
        return True
    try:
        types = json.loads(delegation.biz_types_json)
    except (json.JSONDecodeError, TypeError):
        return True
    if not isinstance(types, list) or not types:
        return True
    return biz_type in types


def can_delegate(instance: ApprovalInstance) -> bool:
    """N-03：高风险 biz_type 不允许代理。"""
    return instance.biz_type not in HIGH_RISK_BIZ_TYPES


def _user_can_act_task(db: Session, user: User, task: ApprovalTask, instance: ApprovalInstance) -> bool:
    if task.status != TASK_ACTIVE:
        return False
    if _is_flow_superuser(user):
        return True
    if task.assignee_id is not None:
        # 指定人节点：本人或（非高风险）其生效委托的代理人可处理
        if user.id == task.assignee_id:
            return True
        if not can_delegate(instance):
            return False
        for d in _active_delegations_for_grantee(db, user.id, _now()):
            if d.granter_id == task.assignee_id and _delegation_covers(d, instance.biz_type):
                return True
        return False
    if instance.initiator_id is not None and user.id == instance.initiator_id:
        return False  # G-08 禁止自审
    # 本人是角色候选人 → 直通
    if _user_role_codes(user) & set(_task_roles(task)):
        # 部门负责人/中心负责人节点：须与申请人同部门（含上级链），防止跨部门误审
        if DEPT_SCOPED_ROLES & set(_task_roles(task)) and instance.department_id:
            allowed = _dept_ancestor_ids(db, instance.department_id)
            if (user.department_id or 0) not in allowed:
                return False
        return True
    # 委托路径：非高风险 + 委托人本是候选人 + 委托覆盖 biz_type
    if not can_delegate(instance):
        return False
    direct = _direct_actor_ids(db, task, instance)
    if not direct:
        return False
    for d in _active_delegations_for_grantee(db, user.id, _now()):
        if d.granter_id in direct and _delegation_covers(d, instance.biz_type):
            return True
    return False


def _dept_ancestor_ids(db: Session, dept_id: Optional[int]) -> set[int]:
    """部门及全部上级部门 id 集合（申请人部门 + 向上到根的链条）。"""
    from app.models.department import Department

    ids: set[int] = set()
    cur = dept_id
    while cur:
        ids.add(cur)
        row = db.query(Department.id, Department.parent_id).filter(Department.id == cur).first()
        if not row:
            break
        cur = row[1]
    return ids


# 按申请人部门（含上级链）匹配的"部门级负责人"角色
DEPT_SCOPED_ROLES = {"dept_head", "center_lead"}


def _resolve_task_candidates(
    db: Session, instance: ApprovalInstance, task: ApprovalTask
) -> tuple[set[int], str]:
    """解析节点候选人。

    返回 (candidate_ids, resolution)：
    - ok：有可用审批人
    - skip_g08：仅发起人持有角色，按 G-08 跳过
    - blocked：角色无人或指定人不可用，流程应挂起
    """
    if task.assignee_id is not None:
        u = (
            db.query(User.id)
            .filter(User.id == task.assignee_id, User.is_active.is_(True))
            .first()
        )
        return ({task.assignee_id} if u else set()), "ok" if u else "blocked"

    roles = _task_roles(task)
    if not roles:
        if _flow_superuser_ids(db):
            return _flow_superuser_ids(db), "ok"
        return set(), "blocked"
    all_ids = _role_holder_ids(db, roles, exclude_id=None)
    if not all_ids:
        su = _flow_superuser_ids(db)
        if su:
            return su, "ok"
        return set(), "blocked"
    eligible = all_ids.copy()
    # 部门负责人/中心负责人节点：只匹配申请人部门（含上级部门链）内的持有人，避免跨部门误派
    if DEPT_SCOPED_ROLES & set(roles) and instance.department_id:
        allowed = _dept_ancestor_ids(db, instance.department_id)
        dept_map = dict(
            db.query(User.id, User.department_id).filter(User.id.in_(eligible)).all()
        )
        eligible = {uid for uid in eligible if dept_map.get(uid) in allowed}
    if instance.initiator_id is not None:
        eligible.discard(instance.initiator_id)
    if eligible:
        return eligible, "ok"
    su = _flow_superuser_ids(db)
    if su:
        return su, "ok"
    if instance.initiator_id in all_ids:
        return set(), "skip_g08"
    return set(), "blocked"


def _task_candidates(db: Session, instance: ApprovalInstance, task: ApprovalTask) -> set[int]:
    """能处理该任务的候选用户 id 集合（仅 ok 时非空）。"""
    ids, resolution = _resolve_task_candidates(db, instance, task)
    return ids if resolution == "ok" else set()


def _block_instance(instance: ApprovalInstance, *, reason: str) -> None:
    instance.status = INSTANCE_BLOCKED
    instance.reject_reason = reason
    instance.updated_at = _now()


# ---------------------------------------------------------------------------
# 发起与推进
# ---------------------------------------------------------------------------
def _gen_code(db: Session, instance_id: int) -> str:
    return f"AF{_now():%Y%m%d}{instance_id:05d}"


def start_instance(
    db: Session,
    *,
    biz_type: str,
    biz_id: Optional[int],
    initiator: User,
    title: str,
    summary: Optional[str] = None,
    amount: Optional[Decimal] = None,
    currency: str = "CNY",
    department_id: Optional[int] = None,
    deep_link: Optional[str] = None,
    facts: Optional[dict[str, Any]] = None,
    assignees: Optional[dict[str, int]] = None,
    commit: bool = True,
) -> ApprovalInstance:
    """按业务类型命中规则并发起一条审批实例（返回已推进到首个有效节点的实例）。"""
    facts = dict(facts or {})
    if amount is not None and "amount" not in facts:
        facts["amount"] = amount
    rule = select_rule(db, biz_type, facts)
    if rule is None:
        raise HTTPException(status_code=409, detail=f"未找到已发布的审批规则：{biz_type}")
    nodes, cc_list = _rule_nodes(rule)
    if not nodes:
        raise HTTPException(status_code=500, detail=f"审批规则 {rule.code} 未配置任何节点")

    instance = ApprovalInstance(
        code="",
        rule_id=rule.id,
        rule_code=rule.code,
        biz_type=biz_type,
        biz_id=biz_id,
        title=title,
        summary=summary,
        amount=amount,
        currency=currency or "CNY",
        status=INSTANCE_PENDING,
        current_seq=0,
        initiator_id=initiator.id,
        initiator_name=initiator.real_name or initiator.username,
        department_id=department_id if department_id is not None else initiator.department_id,
        cc_json=json.dumps(cc_list, ensure_ascii=False) if cc_list else None,
        context_json=json.dumps(_jsonable(facts), ensure_ascii=False) if facts else None,
        deep_link=deep_link,
    )
    db.add(instance)
    db.flush()
    instance.code = _gen_code(db, instance.id)

    for idx, node in enumerate(nodes):
        seq = idx + 1
        node_type = (node.get("type") or "approve").lower()
        if node_type == NODE_ASSIGNEE:
            key = node.get("assignee_key")
            aid = (assignees or {}).get(key) if key else node.get("assignee_id")
            db.add(
                ApprovalTask(
                    instance_id=instance.id,
                    seq=seq,
                    name=node.get("name") or f"节点{seq}",
                    node_type=NODE_ASSIGNEE,
                    roles_json="[]",
                    assignee_id=aid,
                    status=TASK_WAITING,
                )
            )
        elif node_type == NODE_COUNTERSIGN:
            groups = node.get("groups") or []
            for grp in groups:
                db.add(
                    ApprovalTask(
                        instance_id=instance.id,
                        seq=seq,
                        name=node.get("name") or "会签",
                        node_type=NODE_COUNTERSIGN,
                        group_label=grp.get("label"),
                        roles_json=json.dumps(grp.get("roles") or [], ensure_ascii=False),
                        status=TASK_WAITING,
                    )
                )
        else:
            db.add(
                ApprovalTask(
                    instance_id=instance.id,
                    seq=seq,
                    name=node.get("name") or f"节点{seq}",
                    node_type=node_type if node_type in ACTOR_NODE_TYPES else "approve",
                    roles_json=json.dumps(node.get("roles") or [], ensure_ascii=False),
                    status=TASK_WAITING,
                )
            )
    db.flush()

    _advance(db, instance, from_seq=0)
    _audit(db, initiator, instance, action="submit", detail=f"发起审批 {instance.code}（规则 {rule.code}）")
    if commit:
        db.commit()
        db.refresh(instance)
    return instance


def _tasks_at(instance: ApprovalInstance, seq: int) -> list[ApprovalTask]:
    return [t for t in instance.tasks if t.seq == seq]


def _max_seq(instance: ApprovalInstance) -> int:
    return max((t.seq for t in instance.tasks), default=0)


def _advance(db: Session, instance: ApprovalInstance, *, from_seq: int) -> None:
    """从 from_seq 之后找到下一个有有效审批人的节点激活。

    - 仅发起人可批（G-08）→ 跳过该节点
    - 角色无人 / 指定人不可用 → 挂起（blocked），禁止自动通过
    - 全部节点走完且至少有一人审批通过 → 终审通过
    """
    max_seq = _max_seq(instance)
    seq = from_seq + 1
    while seq <= max_seq:
        tasks = _tasks_at(instance, seq)
        actionable: list[ApprovalTask] = []
        seq_blocked = False
        for t in tasks:
            if t.status in (TASK_APPROVED, TASK_REJECTED, TASK_SKIPPED):
                continue
            _candidates, resolution = _resolve_task_candidates(db, instance, t)
            if resolution == "ok":
                actionable.append(t)
            elif resolution == "skip_g08":
                t.status = TASK_SKIPPED
                t.comment = "发起人即审批人，按 G-08 自动跳过"
                t.acted_at = _now()
            else:
                seq_blocked = True
        if seq_blocked:
            _block_instance(instance, reason="当前节点无可用审批人，流程已挂起")
            return
        if actionable:
            for t in actionable:
                t.status = TASK_ACTIVE
            instance.status = INSTANCE_PENDING
            instance.current_seq = seq
            instance.updated_at = _now()
            db.flush()
            try:
                from app.services import feishu_notify

                feishu_notify.notify_active_approvers(db, instance)
            except Exception:
                import logging

                logging.getLogger(__name__).exception(
                    "飞书审批待办通知失败 instance=%s", instance.id
                )
            return
        seq += 1
    if not any(t.status == TASK_APPROVED for t in instance.tasks):
        _block_instance(instance, reason="无有效审批节点，流程已挂起")
        return
    _finalize(db, instance, approved=True)


def _finalize(db: Session, instance: ApprovalInstance, *, approved: bool, reason: Optional[str] = None) -> None:
    instance.status = INSTANCE_APPROVED if approved else INSTANCE_REJECTED
    instance.finished_at = _now()
    instance.updated_at = _now()
    if not approved and reason:
        instance.reject_reason = reason
    db.flush()  # 先落状态，回调里若查"进行中实例"能看到已终结，避免误触发护栏
    _dispatch_callback(db, instance, approved=approved)
    try:
        from app.services import feishu_notify

        feishu_notify.notify_initiator_result(db, instance, approved=approved)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "飞书审批结果通知失败 instance=%s approved=%s", instance.id, approved
        )


# ---------------------------------------------------------------------------
# 处理动作
# ---------------------------------------------------------------------------
def get_instance(db: Session, instance_id: int) -> ApprovalInstance:
    row = db.query(ApprovalInstance).filter(ApprovalInstance.id == instance_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="审批单不存在")
    return row


def _superuser_reopen_for_act(db: Session, instance: ApprovalInstance) -> None:
    """管理员代审：挂起或节点被跳过后，重新激活可审任务。"""
    if instance.status == INSTANCE_BLOCKED:
        instance.status = INSTANCE_PENDING
        instance.reject_reason = None
    if any(t.status == TASK_ACTIVE for t in instance.tasks):
        return
    for seq in range(1, _max_seq(instance) + 1):
        tasks = _tasks_at(instance, seq)
        if not tasks:
            continue
        reopened = False
        for t in tasks:
            if t.status in (TASK_WAITING, TASK_SKIPPED):
                t.status = TASK_ACTIVE
                t.acted_by = None
                t.acted_by_name = None
                t.acted_at = None
                if t.comment and "G-08" in (t.comment or ""):
                    t.comment = None
                reopened = True
        if reopened:
            instance.current_seq = seq
            instance.updated_at = _now()
            return


def act(
    db: Session,
    user: User,
    instance: ApprovalInstance,
    *,
    approve: bool,
    comment: Optional[str],
    commit: bool = True,
) -> ApprovalInstance:
    if instance.status not in INSTANCE_OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="该审批单已挂起或已结束，无法处理")
    comment = (comment or "").strip()
    if not approve and not comment:
        raise HTTPException(status_code=400, detail="驳回意见必填")  # G-10
    if not comment:
        comment = "同意通过"  # G-10：通过节点也留痕，前端未填意见时给默认

    if _is_flow_superuser(user):
        _superuser_reopen_for_act(db, instance)

    seq = instance.current_seq
    active_tasks = [t for t in _tasks_at(instance, seq) if t.status == TASK_ACTIVE]
    mine = [t for t in active_tasks if _user_can_act_task(db, user, t, instance)]
    if not mine:
        raise HTTPException(status_code=403, detail="你不是当前节点的审批人，或不能审批自己发起的单据")

    task = mine[0]
    if _is_flow_superuser(user) and (
        instance.initiator_id == user.id
        or not (_user_role_codes(user) & set(_task_roles(task)))
    ):
        _audit(db, user, instance, action="admin_act", detail="系统管理员代审")
    task.acted_by = user.id
    task.acted_by_name = user.real_name or user.username
    task.acted_at = _now()
    task.comment = comment

    if not approve:
        task.status = TASK_REJECTED
        # 其余同 seq 的会签任务一并作废
        for t in active_tasks:
            if t.id != task.id and t.status == TASK_ACTIVE:
                t.status = TASK_SKIPPED
                t.comment = "同节点已被驳回"
        _finalize(db, instance, approved=False, reason=comment)
        _audit(db, user, instance, action="reject", detail=f"驳回：{comment}")
    else:
        task.status = TASK_APPROVED
        remaining = [t for t in _tasks_at(instance, seq) if t.status == TASK_ACTIVE]
        if remaining:
            # 会签：仍有其他签署方未处理，节点未完成
            _audit(db, user, instance, action="countersign", detail=f"会签通过（{task.group_label or ''}）：{comment}")
        else:
            _audit(db, user, instance, action="approve", detail=f"通过：{comment}")
            _advance(db, instance, from_seq=seq)

    instance.version += 1
    if commit:
        db.commit()
        db.refresh(instance)
    return instance


def cancel_instance(
    db: Session,
    instance: ApprovalInstance,
    *,
    reason: Optional[str] = None,
    commit: bool = True,
) -> ApprovalInstance:
    """由业务域撤销进行中的实例（域侧已鉴权，不再校验发起人）。回调按撤回处理。"""
    if instance.status not in INSTANCE_OPEN_STATUSES:
        return instance
    instance.status = INSTANCE_WITHDRAWN
    instance.finished_at = _now()
    if reason:
        instance.reject_reason = reason
    for t in instance.tasks:
        if t.status in (TASK_ACTIVE, TASK_WAITING):
            t.status = TASK_SKIPPED
            t.comment = t.comment or "审批已撤销"
    db.flush()
    _dispatch_callback(db, instance, approved=False, withdrawn=True)
    if commit:
        db.commit()
        db.refresh(instance)
    return instance


def withdraw(db: Session, user: User, instance: ApprovalInstance, *, commit: bool = True) -> ApprovalInstance:
    if instance.initiator_id != user.id:
        raise HTTPException(status_code=403, detail="仅发起人可撤回")
    if instance.status not in INSTANCE_OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="该审批单已结束，无法撤回")
    instance.status = INSTANCE_WITHDRAWN
    instance.finished_at = _now()
    for t in instance.tasks:
        if t.status in (TASK_ACTIVE, TASK_WAITING):
            t.status = TASK_SKIPPED
            t.comment = t.comment or "发起人撤回"
    db.flush()
    _dispatch_callback(db, instance, approved=False, withdrawn=True)
    _audit(db, user, instance, action="withdraw", detail="发起人撤回")
    if commit:
        db.commit()
        db.refresh(instance)
    return instance


# ---------------------------------------------------------------------------
# 业务回调派发（终审通过 / 驳回 / 撤回时通知业务域）
# ---------------------------------------------------------------------------
def _dispatch_callback(
    db: Session, instance: ApprovalInstance, *, approved: bool, withdrawn: bool = False
) -> None:
    biz = instance.biz_type
    if biz == "refund":
        from app.services import finance as finance_service

        finance_service.on_refund_flow_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "contract":
        from app.services import contract as contract_service

        contract_service.on_contract_flow_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "contract_terminate":
        from app.services import contract as contract_service

        contract_service.on_contract_terminate_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "contract_activate":
        from app.services import contract as contract_service

        contract_service.on_contract_activate_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "contract_modify":
        from app.services import contract_modify as contract_modify_service

        contract_modify_service.on_contract_modify_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "asset_borrow":
        from app.services import asset as asset_service

        asset_service.on_borrow_flow_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "timesheet":
        from app.services import timesheet as timesheet_service

        timesheet_service.on_timesheet_flow_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "receipt":
        from app.services import finance as finance_service

        finance_service.on_receipt_flow_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "project_terminate":
        from app.services import project as project_service

        project_service.on_project_terminate_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "project_no_contract":
        from app.services import project as project_service

        project_service.on_project_no_contract_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "project_initiation":
        from app.services import project as project_service

        project_service.on_project_initiation_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "project_handover":
        from app.services import project as project_service

        project_service.on_project_handover_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "project_acceptance":
        from app.services import project as project_service

        project_service.on_project_acceptance_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "project_settlement":
        from app.services import project as project_service

        project_service.on_project_settlement_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "receipt_diff":
        from app.services import finance as finance_service

        finance_service.on_receipt_diff_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "asset_return":
        from app.services import asset as asset_service

        asset_service.on_return_flow_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "asset_maintenance":
        from app.services import asset as asset_service

        asset_service.on_maintenance_flow_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "asset_inventory_diff":
        from app.services import asset as asset_service

        asset_service.on_inventory_diff_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "ticket":
        from app.services import ticket as ticket_service

        ticket_service.on_ticket_flow_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "ticket_cross_accept":
        from app.services import ticket as ticket_service

        ticket_service.on_ticket_cross_accept_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "schedule":
        from app.services import schedule as schedule_service

        schedule_service.on_schedule_flow_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    elif biz == "role_change":
        from app.services import org as org_service

        org_service.on_role_change_result(
            db, instance, approved=approved, withdrawn=withdrawn
        )
    # 其余业务回调在各自接入阶段注册


# ---------------------------------------------------------------------------
# 审计
# ---------------------------------------------------------------------------
def last_actor_id(instance: ApprovalInstance) -> Optional[int]:
    """终审/末位通过节点的处理人 id（供业务回调确定执行人）。"""
    return next(
        (t.acted_by for t in sorted(instance.tasks, key=lambda x: x.seq, reverse=True) if t.acted_by),
        None,
    )


def last_actor(db: Session, instance: ApprovalInstance) -> Optional[User]:
    aid = last_actor_id(instance)
    if aid is None:
        return None
    return db.query(User).filter(User.id == aid).first()


def _audit(db: Session, user: User, instance: ApprovalInstance, *, action: str, detail: str) -> None:
    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            action=f"approval_flow_{action}",
            module="approval",
            target_type="approval_instance",
            target_id=str(instance.id),
            detail=detail,
        )
    )


def _jsonable(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        out[k] = str(v) if isinstance(v, Decimal) else v
    return out


# ---------------------------------------------------------------------------
# 审批中心快照（转 ApprovalItemOut / 时间线）
# ---------------------------------------------------------------------------
ITEM_PREFIX = "approval_instance"

_INSTANCE_STATUS_LABEL = {
    INSTANCE_PENDING: "审批中",
    INSTANCE_BLOCKED: "已挂起",
    INSTANCE_APPROVED: "已通过",
    INSTANCE_REJECTED: "已驳回",
    INSTANCE_WITHDRAWN: "已撤回",
}


def _current_node_label(instance: ApprovalInstance) -> str:
    if instance.status == INSTANCE_BLOCKED:
        return instance.reject_reason or "无可用审批人，已挂起"
    if instance.status != INSTANCE_PENDING:
        return _INSTANCE_STATUS_LABEL.get(instance.status, "已结束")
    active = [t for t in _tasks_at(instance, instance.current_seq) if t.status == TASK_ACTIVE]
    if not active:
        return "推进中"
    if len(active) > 1:
        parts = [t.group_label or t.name for t in active]
        return f"{active[0].name}（会签：{'、'.join(parts)}）"
    return active[0].name


def _role_names_label(db: Session, role_ids: list[int]) -> str:
    if not role_ids:
        return "无"
    rows = db.query(Role).filter(Role.id.in_(role_ids)).order_by(Role.id.asc()).all()
    by_id = {r.id: r.name for r in rows}
    parts = [by_id.get(int(rid), f"角色#{rid}") for rid in role_ids]
    return "、".join(parts) if parts else "无"


def _role_change_labels(db: Session, instance: ApprovalInstance) -> tuple[str, str, str]:
    """解析角色调整：调整前、调整后、摘要（旧单无名称时按 id 反查）。"""
    ctx = _loads(instance.context_json) if instance.context_json else {}
    if not isinstance(ctx, dict):
        ctx = {}
    prev_ids = [int(x) for x in (ctx.get("prev_role_ids") or [])]
    new_ids = [int(x) for x in (ctx.get("role_ids") or [])]
    prev = str(ctx.get("prev_roles") or "").strip()
    new = str(ctx.get("new_roles") or "").strip()
    if not prev:
        prev = _role_names_label(db, prev_ids)
    if not new:
        new = _role_names_label(db, new_ids)
    summary = f"{prev} → {new}"
    return prev, new, summary


def _instance_facts(db: Session, instance: ApprovalInstance) -> list[ApprovalFact]:
    facts = [ApprovalFact(label="审批单号", value=instance.code)]
    if instance.rule_code:
        facts.append(ApprovalFact(label="适用规则", value=instance.rule_code))
    if instance.biz_type == "role_change":
        employee = (
            db.query(User).filter(User.id == instance.biz_id).first() if instance.biz_id else None
        )
        if employee:
            facts.append(
                ApprovalFact(
                    label="员工",
                    value=f"{employee.real_name or employee.username}（{employee.username}）",
                )
            )
        prev, new, _ = _role_change_labels(db, instance)
        facts.append(ApprovalFact(label="调整前角色", value=prev))
        facts.append(ApprovalFact(label="调整后角色", value=new))
    if instance.amount is not None:
        facts.append(ApprovalFact(label="金额", value=f"¥{instance.amount} {instance.currency}"))
    if instance.summary and instance.biz_type != "role_change":
        facts.append(ApprovalFact(label="说明", value=instance.summary))
    return facts


def _instance_to_item(
    db: Session, instance: ApprovalInstance, *, can_act: bool, allow_withdraw: bool = False, is_superuser: bool = False
) -> ApprovalItemOut:
    if can_act:
        actions = ["approve", "reject", "open"]
        if is_superuser:
            actions.append("remind")
    elif allow_withdraw and instance.status in (INSTANCE_PENDING, INSTANCE_BLOCKED):
        actions = ["open", "withdraw", "remind"]
    elif is_superuser and instance.status in (INSTANCE_PENDING, INSTANCE_BLOCKED):
        actions = ["open", "remind"]
    else:
        actions = ["open"]
    summary = instance.summary or ""
    if instance.biz_type == "role_change":
        _, _, summary = _role_change_labels(db, instance)
    return ApprovalItemOut(
        id=f"{ITEM_PREFIX}:{instance.id}",
        type=ITEM_PREFIX,
        category=biz_category(instance.biz_type),
        source=instance.rule_code or "审批流程",
        source_id=instance.code,
        title=_display_title(db, instance),
        applicant_name=instance.initiator_name or "—",
        department_name="—",
        submitted_at=instance.created_at,
        status=instance.status,
        status_label=_INSTANCE_STATUS_LABEL.get(instance.status, instance.status),
        node=_current_node_label(instance),
        summary=summary,
        facts=_instance_facts(db, instance),
        deep_link=instance.deep_link or "/approvals",
        can_act=can_act,
        actions=actions,
        meta={
            "entity_id": instance.id,
            "instance_id": instance.id,
            "rule_code": instance.rule_code,
            "version": instance.version,
            "biz_type": instance.biz_type,
        },
    )


def find_open_instance(db: Session, biz_type: str, biz_id: int) -> Optional[ApprovalInstance]:
    """取某业务实体仍在审批中的实例（无则 None）。"""
    return (
        db.query(ApprovalInstance)
        .filter(
            ApprovalInstance.biz_type == biz_type,
            ApprovalInstance.biz_id == biz_id,
            ApprovalInstance.status.in_([INSTANCE_PENDING, INSTANCE_BLOCKED]),
        )
        .order_by(ApprovalInstance.id.desc())
        .first()
    )


def latest_instance(db: Session, biz_type: str, biz_id: int) -> Optional[ApprovalInstance]:
    return (
        db.query(ApprovalInstance)
        .filter(ApprovalInstance.biz_type == biz_type, ApprovalInstance.biz_id == biz_id)
        .order_by(ApprovalInstance.id.desc())
        .first()
    )


def latest_instance_status(db: Session, biz_type: str, biz_id: int) -> Optional[str]:
    inst = latest_instance(db, biz_type, biz_id)
    return inst.status if inst else None


def has_approved_instance(db: Session, biz_type: str, biz_id: int) -> bool:
    return (
        db.query(ApprovalInstance.id)
        .filter(
            ApprovalInstance.biz_type == biz_type,
            ApprovalInstance.biz_id == biz_id,
            ApprovalInstance.status == INSTANCE_APPROVED,
        )
        .first()
        is not None
    )


_FLOW_ACTION_LABEL: dict[str, str] = {
    "submit": "发起审批",
    "approve": "审批通过",
    "reject": "审批驳回",
    "countersign": "会签通过",
    "withdraw": "发起人撤回",
    "admin_act": "管理员代审",
}


def _flow_action_label(action: str) -> str:
    # AuditLog.action 形如 "approval_flow_approve"
    key = action[len("approval_flow_") :] if action.startswith("approval_flow_") else action
    return _FLOW_ACTION_LABEL.get(key, key)


def list_flow_activity(
    db: Session, biz_types: Iterable[str], biz_id: int
) -> list[dict]:
    """业务实体维度的审批操作日志：把该实体（同 biz_id + 传入的一批 biz_type）所有实例的 AuditLog 汇总，按时间倒序。

    传多个 biz_type 是为了一张业务单据可能同时挂多种审批流（如合同的 contract / contract_activate /
    contract_terminate / contract_modify，都用 contract.id 做 biz_id）。含历史撤回/驳回过的实例。
    返回 dict 列表，供 API 层转成 FlowActivityItem。
    """
    biz_type_list = [b for b in (biz_types or []) if b]
    if not biz_type_list:
        return []
    instances = (
        db.query(ApprovalInstance)
        .filter(ApprovalInstance.biz_type.in_(biz_type_list), ApprovalInstance.biz_id == biz_id)
        .order_by(ApprovalInstance.id.asc())
        .all()
    )
    if not instances:
        return []
    id_to_inst = {inst.id: inst for inst in instances}
    rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.target_type == "approval_instance",
            AuditLog.target_id.in_([str(iid) for iid in id_to_inst.keys()]),
        )
        .order_by(AuditLog.id.desc())
        .all()
    )
    user_ids = {r.user_id for r in rows if r.user_id is not None}
    real_names: dict[int, str] = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            real_names[u.id] = u.real_name or u.username
    out: list[dict] = []
    for r in rows:
        inst = id_to_inst.get(int(r.target_id)) if r.target_id and r.target_id.isdigit() else None
        out.append(
            {
                "id": r.id,
                "instance_id": inst.id if inst else 0,
                "instance_code": inst.code if inst else None,
                "rule_code": inst.rule_code if inst else None,
                "action": r.action,
                "action_label": _flow_action_label(r.action),
                "actor_id": r.user_id,
                "actor_name": real_names.get(r.user_id) if r.user_id is not None else r.username,
                "detail": r.detail,
                "created_at": r.created_at,
            }
        )
    return out


def instance_biz_ids(db: Session, biz_type: str) -> set[int]:
    """该业务类型下已进入审批引擎的业务实体 id 集合（用于旧聚合去重）。"""
    rows = (
        db.query(ApprovalInstance.biz_id)
        .filter(
            ApprovalInstance.biz_type == biz_type,
            ApprovalInstance.biz_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def _load_pending(db: Session, *, limit: int = 300) -> list[ApprovalInstance]:
    return (
        db.query(ApprovalInstance)
        .filter(ApprovalInstance.status == INSTANCE_PENDING)
        .order_by(ApprovalInstance.id.desc())
        .limit(limit)
        .all()
    )


def _load_open_for_superuser(db: Session, *, limit: int = 300) -> list[ApprovalInstance]:
    return (
        db.query(ApprovalInstance)
        .filter(ApprovalInstance.status.in_([INSTANCE_PENDING, INSTANCE_BLOCKED]))
        .order_by(ApprovalInstance.id.desc())
        .limit(limit)
        .all()
    )


def pending_items_for(db: Session, user: User) -> list[ApprovalItemOut]:
    """当前用户可处理的审批实例（管理员可见全部进行中/挂起且可代审）。"""
    items: list[ApprovalItemOut] = []
    is_su = _is_flow_superuser(user)
    rows = _load_open_for_superuser(db) if is_su else _load_pending(db)
    for inst in rows:
        active = [t for t in _tasks_at(inst, inst.current_seq) if t.status == TASK_ACTIVE]
        if is_su and inst.status == INSTANCE_BLOCKED and not active:
            items.append(_instance_to_item(db, inst, can_act=True, is_superuser=is_su))
            continue
        if any(_user_can_act_task(db, user, t, inst) for t in active):
            items.append(_instance_to_item(db, inst, can_act=True, is_superuser=is_su))
    return items


def cc_items_for(db: Session, user: User) -> list[ApprovalItemOut]:
    """抄送给我的：规则 cc 角色与当前用户角色相交的实例（含进行中与已完结）。"""
    role_codes = _user_role_codes(user)
    is_admin = _is_flow_superuser(user)
    if not role_codes and not is_admin:
        return []
    rows = (
        db.query(ApprovalInstance)
        .filter(
            ApprovalInstance.cc_json.isnot(None),
            ApprovalInstance.cc_json != "",
            ApprovalInstance.cc_json != "[]",
            ApprovalInstance.status != INSTANCE_WITHDRAWN,
        )
        .order_by(ApprovalInstance.id.desc())
        .limit(300)
        .all()
    )
    out: list[ApprovalItemOut] = []
    for inst in rows:
        cc_raw = _loads(inst.cc_json)
        if not isinstance(cc_raw, list) or not cc_raw:
            continue
        cc_set = {str(c) for c in cc_raw if c}
        if not cc_set:
            continue
        if not is_admin and not (role_codes & cc_set):
            continue
        out.append(_instance_to_item(db, inst, can_act=False, is_superuser=is_admin))
    return out


def open_item_id(instance: ApprovalInstance) -> str:
    return f"{ITEM_PREFIX}:{instance.id}"


def find_open_item_id(
    db: Session, biz_type: str, biz_id: int, *, biz_types: Optional[Iterable[str]] = None
) -> Optional[str]:
    """按业务实体查找进行中实例的审批中心 id；contract 族可传多 biz_type。"""
    types = list(biz_types) if biz_types else [biz_type]
    for bt in types:
        inst = find_open_instance(db, bt, biz_id)
        if inst is not None:
            return open_item_id(inst)
    return None


def initiated_items_for(db: Session, user: User) -> list[ApprovalItemOut]:
    rows = (
        db.query(ApprovalInstance)
        .filter(
            ApprovalInstance.initiator_id == user.id,
            ApprovalInstance.status.in_([INSTANCE_PENDING, INSTANCE_BLOCKED]),
        )
        .order_by(ApprovalInstance.id.desc())
        .limit(100)
        .all()
    )
    out: list[ApprovalItemOut] = []
    for inst in rows:
        active = [t for t in _tasks_at(inst, inst.current_seq) if t.status == TASK_ACTIVE]
        can_act = _is_flow_superuser(user) and (
            bool(active) or inst.status == INSTANCE_BLOCKED
        )
        out.append(
            _instance_to_item(
                db,
                inst,
                can_act=can_act,
                allow_withdraw=True,
                is_superuser=_is_flow_superuser(user),
            )
        )
    return out


def processed_items_for(db: Session, user: User) -> list[ApprovalItemOut]:
    inst_ids = [
        r[0]
        for r in (
            db.query(ApprovalTask.instance_id)
            .filter(
                ApprovalTask.acted_by == user.id,
                ApprovalTask.status.in_([TASK_APPROVED, TASK_REJECTED]),
            )
            .distinct()
            .all()
        )
    ]
    if not inst_ids:
        return []
    rows = (
        db.query(ApprovalInstance)
        .filter(ApprovalInstance.id.in_(inst_ids))
        .order_by(ApprovalInstance.id.desc())
        .limit(100)
        .all()
    )
    return [_instance_to_item(db, inst, can_act=False) for inst in rows]


def _resolve_candidates_for_display(
    db: Session, instance: ApprovalInstance, task: ApprovalTask
) -> tuple[list[str], int]:
    """节点未处理时，返回候选审批人姓名（用于时间线"下一步该谁审"展示）。

    - 指定人 → 该员工
    - 角色 → 该角色候选人（含 G-08 剔除发起人后的兜底）
    - 剔除系统管理员（admin 是全局兜底，不该作为业务候选人露出）
    - >2 人时列表截断，前端可拿 count 显示"张三 等 N 人"
    """
    ids, resolution = _resolve_task_candidates(db, instance, task)
    if resolution != "ok" or not ids:
        return [], 0
    # 若节点本身就是给 admin 用的（罕见），保留；否则剔除 admin
    node_roles = set(_task_roles(task))
    if task.assignee_id is None and "admin" not in node_roles:
        ids = ids - _flow_superuser_ids(db)
        if not ids:
            return [], 0
    rows = db.query(User).filter(User.id.in_(ids)).all()
    names = sorted({(u.real_name or u.username) for u in rows if u})
    return names[:3], len(names)


def _task_role_label(db: Session, task: ApprovalTask) -> Optional[str]:
    """节点角色/组标签：'法务'、'财务、行政'（会签组）、或指定人姓名。"""
    if task.node_type == NODE_COUNTERSIGN:
        return task.group_label
    if task.assignee_id is not None:
        u = db.query(User).filter(User.id == task.assignee_id).first()
        return (u.real_name or u.username) if u else None
    role_codes = _task_roles(task)
    if not role_codes:
        return None
    rows = (
        db.query(Role.name)
        .filter(Role.code.in_(role_codes))
        .order_by(Role.id.asc())
        .all()
    )
    labels = [r[0] for r in rows if r[0]]
    return "、".join(labels) if labels else None


def instance_timeline(
    instance: ApprovalInstance, db: Optional[Session] = None
) -> list[ApprovalTimelineNode]:
    nodes: list[ApprovalTimelineNode] = [
        ApprovalTimelineNode(
            name="提交申请",
            status="done",
            actor_name=instance.initiator_name,
            acted_at=instance.created_at,
        )
    ]
    for seq in range(1, _max_seq(instance) + 1):
        tasks = _tasks_at(instance, seq)
        if not tasks:
            continue
        name = tasks[0].name
        if len(tasks) > 1:
            name = f"{name}（会签）"
        if all(t.status == TASK_APPROVED for t in tasks):
            status = "done"
        elif any(t.status == TASK_REJECTED for t in tasks):
            status = "rejected"
        elif all(t.status == TASK_SKIPPED for t in tasks):
            status = "skipped"
        elif any(t.status == TASK_ACTIVE for t in tasks):
            status = "active"
        else:
            status = "waiting"
        acted = [t for t in tasks if t.acted_by_name]
        actor = "、".join(sorted({t.acted_by_name for t in acted if t.acted_by_name})) or None
        comment = next((t.comment for t in tasks if t.comment and t.status in (TASK_APPROVED, TASK_REJECTED)), None)

        # 未处理节点（active/waiting）：算候选人 + 角色标签，展示"下一步该谁审"
        candidate_names: list[str] = []
        candidate_count = 0
        role_label: Optional[str] = None
        if db is not None and status in ("active", "waiting"):
            group_labels: list[str] = []
            name_set: set[str] = set()
            total = 0
            for t in tasks:
                names, cnt = _resolve_candidates_for_display(db, instance, t)
                name_set.update(names)
                total += cnt
                lbl = _task_role_label(db, t)
                if lbl:
                    group_labels.append(lbl)
            candidate_names = sorted(name_set)[:3]
            candidate_count = total
            if group_labels:
                sep = "、"
                role_label = sep.join(group_labels)

        nodes.append(
            ApprovalTimelineNode(
                name=name,
                status=status,
                actor_name=actor,
                acted_at=next((t.acted_at for t in acted), None),
                comment=comment,
                candidate_names=candidate_names,
                candidate_count=candidate_count,
                role_label=role_label,
            )
        )
    return nodes


def get_instance_by_item_id(db: Session, item_id: str) -> ApprovalInstance:
    parts = item_id.split(":")
    if len(parts) < 2 or parts[0] != ITEM_PREFIX:
        raise HTTPException(status_code=400, detail="无效的审批单号")
    try:
        instance_id = int(parts[1])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="无效的审批单号") from exc
    return get_instance(db, instance_id)
