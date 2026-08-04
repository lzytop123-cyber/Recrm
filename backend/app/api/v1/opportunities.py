"""商机管理 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.contract import ContractOut
from app.schemas.opportunity import (
    OpportunityActivityCreate,
    OpportunityActivityOut,
    OpportunityCreate,
    OpportunityDetailOut,
    OpportunityListOut,
    OpportunityOut,
    OpportunityStageChange,
    OpportunityStatsOut,
    OpportunityUpdate,
)
from app.services import opportunity as opportunity_service

router = APIRouter(prefix="/opportunities", tags=["商机管理"])


@router.get("/stats", response_model=OpportunityStatsOut, summary="商机统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["opportunity:view"]))],
) -> OpportunityStatsOut:
    return OpportunityStatsOut(**opportunity_service.opportunity_stats(db, current_user))


@router.get("", response_model=OpportunityListOut, summary="商机列表")
def list_opportunities(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["opportunity:view"]))],
    stage: Optional[str] = None,
    keyword: Optional[str] = None,
    customer_id: Optional[int] = None,
    scope: Optional[str] = Query(None, description="mine/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> OpportunityListOut:
    total, items = opportunity_service.list_opportunities(
        db,
        current_user,
        stage=stage,
        keyword=keyword,
        customer_id=customer_id,
        scope_filter=scope,
        page=page,
        page_size=page_size,
    )
    return OpportunityListOut(total=total, items=[OpportunityOut.model_validate(x) for x in items])


@router.post("", response_model=OpportunityOut, summary="新建商机")
def create_opportunity(
    payload: OpportunityCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["opportunity:view"]))],
) -> OpportunityOut:
    opp = opportunity_service.create_opportunity(db, current_user, payload)
    return OpportunityOut.model_validate(opp)


@router.get("/{opportunity_id}", response_model=OpportunityDetailOut, summary="商机详情")
def get_opportunity(
    opportunity_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["opportunity:view"]))],
) -> OpportunityDetailOut:
    opp = opportunity_service.get_opportunity_detail(db, current_user, opportunity_id)
    return OpportunityDetailOut.model_validate(opp)


@router.patch("/{opportunity_id}", response_model=OpportunityOut, summary="编辑商机")
def update_opportunity(
    opportunity_id: int,
    payload: OpportunityUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["opportunity:view"]))],
) -> OpportunityOut:
    opp = opportunity_service.update_opportunity(db, current_user, opportunity_id, payload)
    return OpportunityOut.model_validate(opp)


@router.post("/{opportunity_id}/stage", response_model=OpportunityOut, summary="变更阶段")
def change_stage(
    opportunity_id: int,
    payload: OpportunityStageChange,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["opportunity:view"]))],
) -> OpportunityOut:
    opp = opportunity_service.change_stage(db, current_user, opportunity_id, payload)
    return OpportunityOut.model_validate(opp)


@router.post(
    "/{opportunity_id}/activities",
    response_model=OpportunityActivityOut,
    summary="写跟进",
)
def create_activity(
    opportunity_id: int,
    payload: OpportunityActivityCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["opportunity:view"]))],
) -> OpportunityActivityOut:
    act = opportunity_service.add_activity(db, current_user, opportunity_id, payload)
    return OpportunityActivityOut.model_validate(act)


@router.post(
    "/{opportunity_id}/draft-contract",
    response_model=ContractOut,
    summary="起草合同",
)
def draft_contract(
    opportunity_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["opportunity:view", "contract:view"]))],
) -> ContractOut:
    contract = opportunity_service.draft_contract_from_opportunity(
        db, current_user, opportunity_id
    )
    return ContractOut.model_validate(contract)
