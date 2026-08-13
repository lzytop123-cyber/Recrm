"""业务旅程聚合：线索 → 商机 → 合同 → 项目主线节点。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.contract import CONTRACT_STATUS_LABEL, Contract
from app.models.customer import Customer
from app.models.lead import (
    LEAD_STATUS_ASSIGNED,
    LEAD_STATUS_CONVERTED,
    LEAD_STATUS_FOLLOWING,
    LEAD_STATUS_LOST,
    LEAD_STATUS_PENDING,
    LEAD_STATUS_RETURNED,
    Lead,
    LeadLog,
)
from app.models.opportunity import (
    OPP_STAGE_LOST,
    OPP_STAGE_NEED,
    OPP_STAGE_NEGOTIATION,
    OPP_STAGE_PROPOSAL,
    OPP_STAGE_WON,
    Opportunity,
)
from app.models.project import (
    PROJECT_STATUS_COMPLETED,
    PROJECT_STATUS_LABEL,
    PROJECT_STATUS_TERMINATED,
    Project,
)
from app.services.opportunity import _active_contract_for_opportunity, _user_name


def _project_for_contract(db: Session, contract_id: int) -> Optional[Project]:
    return (
        db.query(Project)
        .filter(Project.contract_id == contract_id)
        .order_by(Project.id.asc())
        .first()
    )


def resolve_converted_opportunity_id(db: Session, lead: Lead) -> Optional[int]:
    """优先用线索上的字段；缺失时按 source_lead_id 兜底。"""
    if lead.converted_opportunity_id:
        return lead.converted_opportunity_id
    opp = (
        db.query(Opportunity)
        .filter(Opportunity.source_lead_id == lead.id)
        .order_by(Opportunity.id.asc())
        .first()
    )
    return opp.id if opp else None


def _log_for_action(db: Session, lead_id: int, action: str) -> Optional[LeadLog]:
    return (
        db.query(LeadLog)
        .filter(LeadLog.lead_id == lead_id, LeadLog.action == action)
        .order_by(LeadLog.created_at.asc())
        .first()
    )


def _milestone(
    *,
    key: str,
    label: str,
    status: str,
    at: Optional[datetime] = None,
    actor: Optional[str] = None,
    entity: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "at": at,
        "actor": actor,
        "entity": entity,
        "entity_id": entity_id,
    }


def _lead_phase_status(lead: Lead) -> dict[str, str]:
    """返回录入/分配/跟进/转化 四个节点的 status。"""
    status = lead.status
    if status == LEAD_STATUS_PENDING or status == LEAD_STATUS_RETURNED:
        return {
            "lead_created": "current" if status == LEAD_STATUS_PENDING else "done",
            "lead_assigned": "pending",
            "lead_following": "pending",
            "lead_converted": "pending",
        }
    if status == LEAD_STATUS_ASSIGNED:
        return {
            "lead_created": "done",
            "lead_assigned": "current",
            "lead_following": "pending",
            "lead_converted": "pending",
        }
    if status == LEAD_STATUS_FOLLOWING:
        return {
            "lead_created": "done",
            "lead_assigned": "done",
            "lead_following": "current",
            "lead_converted": "pending",
        }
    if status == LEAD_STATUS_CONVERTED:
        return {
            "lead_created": "done",
            "lead_assigned": "done",
            "lead_following": "done",
            "lead_converted": "done",
        }
    if status == LEAD_STATUS_LOST:
        # 流失停在线索侧：已发生节点 done，转化 pending/skipped
        assigned = bool(lead.owner_id or lead.assigned_at)
        followed = bool(lead.last_followed_at) or status == LEAD_STATUS_LOST
        return {
            "lead_created": "done",
            "lead_assigned": "done" if assigned else "skipped",
            "lead_following": "done" if followed else "skipped",
            "lead_converted": "skipped",
        }
    return {
        "lead_created": "done",
        "lead_assigned": "pending",
        "lead_following": "pending",
        "lead_converted": "pending",
    }


_OPP_FUNNEL = [
    (OPP_STAGE_NEED, "opp_need_confirm", "需求确认"),
    (OPP_STAGE_PROPOSAL, "opp_proposal", "方案报价"),
    (OPP_STAGE_NEGOTIATION, "opp_negotiation", "商务谈判"),
]


def _opp_stage_rank(stage: str) -> int:
    order = {
        "contact": 0,
        OPP_STAGE_NEED: 1,
        OPP_STAGE_PROPOSAL: 2,
        OPP_STAGE_NEGOTIATION: 3,
        OPP_STAGE_WON: 4,
        OPP_STAGE_LOST: 4,
        "paused": 2,
    }
    return order.get(stage, 1)


def build_sales_journey(
    db: Session,
    *,
    lead: Optional[Lead] = None,
    opportunity: Optional[Opportunity] = None,
    contract: Optional[Contract] = None,
    project: Optional[Project] = None,
) -> dict:
    """从线索 / 商机 / 合同 / 项目入口组装同一套业务旅程。"""
    customer: Optional[Customer] = None

    if project and not contract and project.contract_id:
        contract = db.query(Contract).filter(Contract.id == project.contract_id).first()

    if contract and not opportunity and contract.opportunity_id:
        opportunity = (
            db.query(Opportunity).filter(Opportunity.id == contract.opportunity_id).first()
        )

    if opportunity and not lead and opportunity.source_lead_id:
        lead = db.query(Lead).filter(Lead.id == opportunity.source_lead_id).first()

    if lead and not opportunity:
        opp_id = resolve_converted_opportunity_id(db, lead)
        if opp_id:
            opportunity = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
            if opportunity and not lead.converted_opportunity_id:
                lead.converted_opportunity_id = opportunity.id

    if opportunity and not contract:
        contract = _active_contract_for_opportunity(db, opportunity.id)

    if contract and not project:
        project = _project_for_contract(db, contract.id)

    if opportunity:
        customer = db.query(Customer).filter(Customer.id == opportunity.customer_id).first()
    elif contract:
        customer = db.query(Customer).filter(Customer.id == contract.customer_id).first()
    elif project and project.customer_id:
        customer = db.query(Customer).filter(Customer.id == project.customer_id).first()
    elif lead and lead.converted_customer_id:
        customer = db.query(Customer).filter(Customer.id == lead.converted_customer_id).first()

    milestones: list[dict] = []
    current_key: Optional[str] = None

    # —— 线索段（始终 4 节点；无线索时标 skipped=未发生）——
    if lead:
        phases = _lead_phase_status(lead)
        create_log = _log_for_action(db, lead.id, "create")
        assign_log = _log_for_action(db, lead.id, "assign") or _log_for_action(db, lead.id, "claim")
        follow_log = _log_for_action(db, lead.id, "follow")
        convert_log = _log_for_action(db, lead.id, "convert")
        convert_label = "已转化"
        if lead.status == LEAD_STATUS_LOST:
            convert_label = "已流失"
        elif lead.status == LEAD_STATUS_RETURNED:
            convert_label = "已释放"
        convert_status = (
            "current" if lead.status == LEAD_STATUS_LOST else phases["lead_converted"]
        )
        lead_entity = "customer" if lead.converted_customer_id else "lead"
        lead_entity_id = lead.converted_customer_id or lead.id
        milestones.extend(
            [
                _milestone(
                    key="lead_created",
                    label="录入",
                    status=phases["lead_created"],
                    at=create_log.created_at if create_log else lead.created_at,
                    actor=(
                        (_user_name(db, create_log.user_id) or create_log.username)
                        if create_log
                        else _user_name(db, lead.creator_id)
                    ),
                    entity="lead",
                    entity_id=lead.id,
                ),
                _milestone(
                    key="lead_assigned",
                    label="分配",
                    status=phases["lead_assigned"],
                    at=assign_log.created_at if assign_log else lead.assigned_at,
                    actor=(
                        (_user_name(db, assign_log.user_id) or assign_log.username)
                        if assign_log
                        else _user_name(db, lead.owner_id)
                    ),
                    entity="lead",
                    entity_id=lead.id,
                ),
                _milestone(
                    key="lead_following",
                    label="跟进中",
                    status=phases["lead_following"],
                    at=follow_log.created_at if follow_log else lead.last_followed_at,
                    actor=(
                        (_user_name(db, follow_log.user_id) or follow_log.username)
                        if follow_log
                        else _user_name(db, lead.owner_id)
                    ),
                    entity="lead",
                    entity_id=lead.id,
                ),
                _milestone(
                    key="lead_converted",
                    label=convert_label,
                    status=convert_status,
                    at=convert_log.created_at if convert_log else lead.converted_at or lead.lost_at,
                    actor=(
                        (_user_name(db, convert_log.user_id) or convert_log.username)
                        if convert_log
                        else None
                    ),
                    entity=lead_entity,
                    entity_id=lead_entity_id,
                ),
            ]
        )
        if lead.status == LEAD_STATUS_LOST:
            current_key = "lead_converted"
    else:
        for key, label in (
            ("lead_created", "录入"),
            ("lead_assigned", "分配"),
            ("lead_following", "跟进中"),
            ("lead_converted", "已转化"),
        ):
            milestones.append(_milestone(key=key, label=label, status="skipped", entity="lead"))

    # —— 商机漏斗（始终 4 节点）——
    if opportunity:
        rank = _opp_stage_rank(opportunity.stage)
        for stage_code, key, label in _OPP_FUNNEL:
            stage_rank = _opp_stage_rank(stage_code)
            if opportunity.stage in {OPP_STAGE_WON, OPP_STAGE_LOST}:
                st = "done"
            elif rank > stage_rank:
                st = "done"
            elif rank == stage_rank:
                st = "current"
            else:
                st = "pending"
            milestones.append(
                _milestone(
                    key=key,
                    label=label,
                    status=st,
                    entity="opportunity",
                    entity_id=opportunity.id,
                )
            )

        if opportunity.stage == OPP_STAGE_LOST:
            milestones.append(
                _milestone(
                    key="opp_closed",
                    label="输单",
                    status="current",
                    at=opportunity.lost_at or opportunity.closed_at,
                    entity="opportunity",
                    entity_id=opportunity.id,
                )
            )
            current_key = "opp_closed"
        else:
            closed_status = "done" if opportunity.stage == OPP_STAGE_WON else "pending"
            milestones.append(
                _milestone(
                    key="opp_closed",
                    label="赢单",
                    status=(
                        "current"
                        if opportunity.stage == OPP_STAGE_WON and not contract
                        else closed_status
                    ),
                    at=opportunity.won_at or opportunity.closed_at,
                    entity="opportunity",
                    entity_id=opportunity.id,
                )
            )
            if opportunity.stage == OPP_STAGE_WON and not contract:
                current_key = "opp_closed"
            elif opportunity.stage not in {OPP_STAGE_WON, OPP_STAGE_LOST}:
                for m in milestones:
                    if m["key"].startswith("opp_") and m["status"] == "current":
                        current_key = m["key"]
                        break
    else:
        # 有进行中的线索：商机待发生；否则（直接合同/无上游）标未发生
        opp_placeholder = (
            "pending"
            if lead is not None and lead.status not in {LEAD_STATUS_LOST, LEAD_STATUS_RETURNED}
            else "skipped"
        )
        for key, label in (
            ("opp_need_confirm", "需求确认"),
            ("opp_proposal", "方案报价"),
            ("opp_negotiation", "商务谈判"),
            ("opp_closed", "赢单"),
        ):
            milestones.append(
                _milestone(key=key, label=label, status=opp_placeholder, entity="opportunity")
            )

    # —— 合同 ——
    # 已立项后，合同节点视为完成（签约完成进入交付），当前落到项目
    project_takes_over = bool(
        project and project.status not in {PROJECT_STATUS_TERMINATED}
    )
    if contract:
        contract_label = CONTRACT_STATUS_LABEL.get(contract.status, contract.status)
        contract_closed = contract.status in {"completed", "terminated"}
        contract_handoff = contract.status in {
            "signed",
            "active",
            "completed",
            "terminated",
        }
        if project_takes_over and contract_handoff:
            contract_status = "done"
        elif contract_closed:
            contract_status = "done"
        else:
            contract_status = "current"
        milestones.append(
            _milestone(
                key="contract",
                label=f"合同·{contract_label}",
                status=contract_status,
                at=getattr(contract, "updated_at", None) or getattr(contract, "created_at", None),
                entity="contract",
                entity_id=contract.id,
            )
        )
        if contract_status == "current":
            current_key = "contract"
        elif not current_key:
            current_key = "contract"
    else:
        milestones.append(
            _milestone(
                key="contract",
                label="合同",
                status="pending",
                entity="contract",
                entity_id=None,
            )
        )

    # —— 项目 / 交付 ——
    if project:
        proj_label = PROJECT_STATUS_LABEL.get(project.status, project.status)
        if project.status == PROJECT_STATUS_TERMINATED:
            proj_status = "skipped"
        elif project.status == PROJECT_STATUS_COMPLETED:
            proj_status = "done"
        else:
            proj_status = "current"
        milestones.append(
            _milestone(
                key="project",
                label=f"项目·{proj_label}",
                status=proj_status,
                at=getattr(project, "updated_at", None) or getattr(project, "created_at", None),
                actor=_user_name(db, project.manager_id),
                entity="project",
                entity_id=project.id,
            )
        )
        if proj_status in {"current", "done", "skipped"}:
            current_key = "project"
    else:
        # 合同已签署/执行后提示待立项；否则占位
        proj_pending = "pending"
        milestones.append(
            _milestone(
                key="project",
                label="项目交付",
                status=proj_pending,
                entity="project",
                entity_id=None,
            )
        )

    # 线索未转化时：当前落在线索段
    if lead and lead.status != LEAD_STATUS_CONVERTED and lead.status != LEAD_STATUS_LOST:
        for m in milestones:
            if m["key"].startswith("lead_") and m["status"] == "current":
                current_key = m["key"]
                break

    if not current_key:
        for m in milestones:
            if m["status"] == "current":
                current_key = m["key"]
                break

    lead_label = None
    if lead:
        lead_label = lead.company_name or lead.name

    return {
        "milestones": milestones,
        "links": {
            "lead_id": lead.id if lead else None,
            "customer_id": (customer.id if customer else None)
            or (lead.converted_customer_id if lead else None)
            or (opportunity.customer_id if opportunity else None)
            or (contract.customer_id if contract else None)
            or (project.customer_id if project else None),
            "opportunity_id": opportunity.id if opportunity else None,
            "contract_id": contract.id if contract else None,
            "project_id": project.id if project else None,
            "lead_label": lead_label,
            "customer_name": customer.name if customer else None,
            "opportunity_no": opportunity.opportunity_no if opportunity else None,
            "contract_no": contract.contract_no if contract else None,
            "project_no": project.project_no if project else None,
            "project_name": project.name if project else None,
        },
        "current_key": current_key,
    }
