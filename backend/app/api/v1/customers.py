"""客户管理 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.customer import (
    CustomerCreate,
    CustomerDetailOut,
    CustomerFollowUpCreate,
    CustomerFollowUpOut,
    CustomerListOut,
    CustomerOut,
    CustomerStatsOut,
    CustomerUpdate,
)
from app.services import customer as customer_service

router = APIRouter(prefix="/customers", tags=["客户管理"])


@router.get("/stats", response_model=CustomerStatsOut, summary="客户统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["customer:view"]))],
) -> CustomerStatsOut:
    return CustomerStatsOut(**customer_service.customer_stats(db, current_user))


@router.get("", response_model=CustomerListOut, summary="客户列表")
def list_customers(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["customer:view"]))],
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    scope: Optional[str] = Query(None, description="mine/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> CustomerListOut:
    total, items = customer_service.list_customers(
        db,
        current_user,
        status=status,
        keyword=keyword,
        scope_filter=scope,
        page=page,
        page_size=page_size,
    )
    return CustomerListOut(total=total, items=[CustomerOut.model_validate(x) for x in items])


@router.post("", response_model=CustomerOut, summary="录入客户")
def create_customer(
    payload: CustomerCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["customer:view"]))],
) -> CustomerOut:
    customer = customer_service.create_customer(db, current_user, payload)
    return CustomerOut.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerDetailOut, summary="客户详情")
def get_customer(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["customer:view"]))],
) -> CustomerDetailOut:
    customer = customer_service.get_customer_detail(db, current_user, customer_id)
    return CustomerDetailOut.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerOut, summary="编辑客户")
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["customer:view"]))],
) -> CustomerOut:
    customer = customer_service.update_customer(db, current_user, customer_id, payload)
    return CustomerOut.model_validate(customer)


@router.post("/{customer_id}/follow-ups", response_model=CustomerFollowUpOut, summary="写跟进")
def create_follow_up(
    customer_id: int,
    payload: CustomerFollowUpCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["customer:view"]))],
) -> CustomerFollowUpOut:
    fu = customer_service.add_follow_up(db, current_user, customer_id, payload)
    return CustomerFollowUpOut.model_validate(fu)
