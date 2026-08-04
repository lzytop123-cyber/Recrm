"""线索池 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_current_active_user
from app.database import get_db
from app.models.user import User
from app.schemas.lead import (
    DuplicateCheckOut,
    LeadAssignRequest,
    LeadBatchAssignRequest,
    LeadBatchAssignResult,
    LeadConvertOut,
    LeadConvertRequest,
    LeadCreate,
    LeadDetailOut,
    LeadFollowUpCreate,
    LeadFollowUpOut,
    LeadListOut,
    LeadLostRequest,
    LeadOut,
    LeadQuotaOut,
    LeadReturnRequest,
    LeadStatsOut,
    LeadTransferRequest,
    LeadUpdate,
)
from app.services import lead as lead_service

router = APIRouter(prefix="/leads", tags=["线索池"])


@router.get("/stats", response_model=LeadStatsOut, summary="线索统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
) -> LeadStatsOut:
    return LeadStatsOut(**lead_service.lead_stats(db, current_user))


@router.get("/quota", response_model=LeadQuotaOut, summary="我的公海抢领额度")
def quota(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
) -> LeadQuotaOut:
    return LeadQuotaOut(**lead_service.get_lead_quota(db, current_user))


@router.get("/duplicates", response_model=DuplicateCheckOut, summary="重复检测")
def check_duplicates(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    credit_code: Optional[str] = None,
    company_domain: Optional[str] = None,
) -> DuplicateCheckOut:
    dups = lead_service.find_duplicates(
        db,
        phone=phone,
        company_name=company_name,
        credit_code=credit_code,
        company_domain=company_domain,
    )

    def _out(items):
        return [LeadOut.model_validate(lead_service.enrich_lead(db, x)) for x in items]

    hard = bool(dups["by_phone"] or dups["by_credit"])
    soft = bool(dups["by_company"] or dups["by_domain"])
    return DuplicateCheckOut(
        has_duplicate=hard or soft,
        is_hard_duplicate=hard,
        by_phone=_out(dups["by_phone"]),
        by_company=_out(dups["by_company"]),
        by_credit=_out(dups["by_credit"]),
        by_domain=_out(dups["by_domain"]),
    )


@router.get("", response_model=LeadListOut, summary="线索列表")
def list_leads(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    pool: Optional[str] = Query(None, description="mine/created/public/all"),
    business_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> LeadListOut:
    total, items = lead_service.list_leads(
        db,
        current_user,
        status=status,
        keyword=keyword,
        pool=pool,
        business_type=business_type,
        page=page,
        page_size=page_size,
    )
    return LeadListOut(total=total, items=[LeadOut.model_validate(x) for x in items])


@router.post("", response_model=LeadOut, summary="录入线索")
def create_lead(
    payload: LeadCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"], any_of=False))],
    force: bool = Query(False, description="手机号重复时强制创建"),
) -> LeadOut:
    # 全员有 lead:view 即可录入（普通员工种子会补上）
    lead = lead_service.create_lead(db, current_user, payload, force=force)
    return LeadOut.model_validate(lead)


@router.get("/{lead_id}", response_model=LeadDetailOut, summary="线索详情")
def get_lead(
    lead_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
) -> LeadDetailOut:
    lead = lead_service.get_lead_detail(db, current_user, lead_id)
    return LeadDetailOut.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadOut, summary="编辑线索")
def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
) -> LeadOut:
    lead = lead_service.update_lead(db, current_user, lead_id, payload)
    return LeadOut.model_validate(lead)


@router.post("/{lead_id}/assign", response_model=LeadOut, summary="手动分配")
def assign_lead(
    lead_id: int,
    payload: LeadAssignRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:manage"]))],
) -> LeadOut:
    lead = lead_service.assign_lead(db, current_user, lead_id, payload)
    return LeadOut.model_validate(lead)


@router.post("/batch-assign", response_model=LeadBatchAssignResult, summary="批量分配待分配线索")
def batch_assign_leads(
    payload: LeadBatchAssignRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:manage"]))],
) -> LeadBatchAssignResult:
    result = lead_service.batch_assign_leads(
        db,
        current_user,
        lead_ids=payload.lead_ids,
        owner_ids=payload.owner_ids,
        method=payload.method,
        assignments=[x.model_dump() for x in payload.assignments],
        reason=payload.reason,
    )
    return LeadBatchAssignResult(**result)


@router.post("/{lead_id}/claim", response_model=LeadOut, summary="公海领取（兼容旧入口，正式流程请用分配）")
def claim_lead(
    lead_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> LeadOut:
    lead = lead_service.claim_lead(db, current_user, lead_id)
    return LeadOut.model_validate(lead)


@router.post("/{lead_id}/transfer", response_model=LeadOut, summary="流转给他人")
def transfer_lead(
    lead_id: int,
    payload: LeadTransferRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
) -> LeadOut:
    lead = lead_service.transfer_lead(db, current_user, lead_id, payload)
    return LeadOut.model_validate(lead)


@router.post("/{lead_id}/return", response_model=LeadOut, summary="退回公海")
def return_lead(
    lead_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
    payload: Optional[LeadReturnRequest] = None,
    reason: Optional[str] = Query(None, description="兼容旧版 query 参数"),
) -> LeadOut:
    body = payload or LeadReturnRequest()
    lead = lead_service.return_to_pool(
        db,
        current_user,
        lead_id,
        body.reason or reason,
        reason_type=body.reason_type,
    )
    return LeadOut.model_validate(lead)


@router.post("/{lead_id}/follow-ups", response_model=LeadFollowUpOut, summary="写跟进")
def create_follow_up(
    lead_id: int,
    payload: LeadFollowUpCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
) -> LeadFollowUpOut:
    fu = lead_service.add_follow_up(db, current_user, lead_id, payload)
    return LeadFollowUpOut.model_validate(fu)


@router.post("/{lead_id}/convert", response_model=LeadConvertOut, summary="转化为客户与商机")
def convert_lead(
    lead_id: int,
    payload: LeadConvertRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
) -> LeadConvertOut:
    result = lead_service.convert_lead(db, current_user, lead_id, payload)
    return LeadConvertOut(
        lead=LeadOut.model_validate(result["lead"]),
        customer_id=result["customer_id"],
        opportunity_id=result["opportunity_id"],
    )


@router.post("/{lead_id}/lost", response_model=LeadOut, summary="标记流失")
def lost_lead(
    lead_id: int,
    payload: LeadLostRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["lead:view"]))],
) -> LeadOut:
    lead = lead_service.mark_lost(db, current_user, lead_id, payload)
    return LeadOut.model_validate(lead)
