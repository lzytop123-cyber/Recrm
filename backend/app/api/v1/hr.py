"""人事闭环 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_current_active_user
from app.database import get_db
from app.models.user import User
from app.schemas.hr import (
    AttendanceMonthlyOut,
    HandoverAssignIn,
    HandoverOut,
    HandoverItemOut,
    HrDashboardOut,
    LaborContractCreate,
    LaborContractListOut,
    LaborContractOut,
    LaborContractRenew,
    LaborContractUpdate,
    LeaveBalanceOut,
    LeaveBalancePatch,
    LeaveRequestCreate,
    LeaveRequestListOut,
    LeaveRequestOut,
    PayslipCorrectIn,
    PayslipDownloadOut,
    PayslipListOut,
    PayslipOut,
    ResignationCreate,
    ResignationListOut,
    ResignationOut,
    TransferCreate,
    TransferListOut,
    TransferOut,
)
from app.services import hr as hr_service

router = APIRouter(prefix="/hr", tags=["人事"])
payslip_router = APIRouter(prefix="/payslips", tags=["工资条"])

_login = get_current_active_user
_org_view = PermissionChecker(["org:view", "org:manage"], any_of=True)


def _contract_out(row) -> LaborContractOut:
    return LaborContractOut.model_validate(row)


@router.get("/contracts/expiring", response_model=LaborContractListOut, summary="合同到期预警")
def expiring_contracts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_org_view)],
    days: Annotated[int, Query(ge=1, le=365)] = 90,
) -> LaborContractListOut:
    data = hr_service.list_expiring(db, current_user, days=days)
    return LaborContractListOut(total=data["total"], items=[_contract_out(x) for x in data["items"]])


@router.get("/contracts", response_model=LaborContractListOut, summary="劳动合同台账")
def list_contracts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
    department_id: Annotated[Optional[int], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    employee_id: Annotated[Optional[int], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LaborContractListOut:
    data = hr_service.list_contracts(
        db, current_user, department_id=department_id, status=status, employee_id=employee_id, page=page, page_size=page_size
    )
    return LaborContractListOut(total=data["total"], items=[_contract_out(x) for x in data["items"]])


@router.post("/contracts", response_model=LaborContractOut, summary="新建劳动合同")
def create_contract(
    payload: LaborContractCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> LaborContractOut:
    return _contract_out(hr_service.create_contract(db, current_user, payload))


@router.get("/contracts/{contract_id}", response_model=LaborContractOut, summary="合同详情")
def get_contract(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> LaborContractOut:
    return _contract_out(hr_service.get_contract(db, current_user, contract_id))


@router.patch("/contracts/{contract_id}", response_model=LaborContractOut, summary="编辑劳动合同")
def update_contract(
    contract_id: int,
    payload: LaborContractUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> LaborContractOut:
    return _contract_out(hr_service.update_contract(db, current_user, contract_id, payload))


@router.post("/contracts/{contract_id}/renew", response_model=LaborContractOut, summary="发起续签")
def renew_contract(
    contract_id: int,
    payload: LaborContractRenew,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> LaborContractOut:
    return _contract_out(hr_service.renew_contract(db, current_user, contract_id, payload))


@router.get("/contracts/{contract_id}/file", summary="合同扫描件路径")
def contract_file(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> dict:
    path = hr_service.contract_file_path(db, current_user, contract_id)
    url = path if path.startswith("/") else f"/uploads/{path}"
    return {"url": url, "expires_in": 300}


@router.get("/transfers", response_model=TransferListOut, summary="转岗列表")
def list_transfers(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
    status: Annotated[Optional[str], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TransferListOut:
    data = hr_service.list_transfers(db, current_user, status=status, page=page, page_size=page_size)
    return TransferListOut(total=data["total"], items=[TransferOut.model_validate(x) for x in data["items"]])


@router.post("/transfers", response_model=TransferOut, summary="转岗申请")
def create_transfer(
    payload: TransferCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> TransferOut:
    return TransferOut.model_validate(hr_service.create_transfer(db, current_user, payload))


@router.get("/transfers/{transfer_id}", response_model=TransferOut, summary="转岗详情")
def get_transfer(
    transfer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> TransferOut:
    return TransferOut.model_validate(hr_service.get_transfer(db, current_user, transfer_id))


@router.get("/resignations", response_model=ResignationListOut, summary="离职列表")
def list_resignations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
    status: Annotated[Optional[str], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResignationListOut:
    data = hr_service.list_resignations(db, current_user, status=status, page=page, page_size=page_size)
    return ResignationListOut(total=data["total"], items=[ResignationOut.model_validate(x) for x in data["items"]])


@router.post("/resignations", response_model=ResignationOut, summary="发起离职")
def create_resignation(
    payload: ResignationCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> ResignationOut:
    return ResignationOut.model_validate(hr_service.create_resignation(db, current_user, payload))


@router.get("/resignations/{resignation_id}", response_model=ResignationOut, summary="离职详情")
def get_resignation(
    resignation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> ResignationOut:
    return ResignationOut.model_validate(hr_service.get_resignation(db, current_user, resignation_id))


def _handover_out(row) -> HandoverOut:
    return HandoverOut(
        id=row.id,
        resignation_id=row.resignation_id,
        employee_id=row.employee_id,
        status=row.status,
        items=[HandoverItemOut.model_validate(x) for x in row.items],
        open_items=getattr(row, "open_items", []) or [],
        can_complete=bool(getattr(row, "can_complete", False)),
        signed_by=row.signed_by,
        signed_at=row.signed_at,
    )


@router.get("/handovers/{handover_id}", response_model=HandoverOut, summary="交接单与一致性检查")
def get_handover(
    handover_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> HandoverOut:
    return _handover_out(hr_service.get_handover(db, current_user, handover_id))


@router.post("/handovers/{handover_id}/items/{item_id}/assign", response_model=HandoverOut, summary="指定接收人")
def assign_item(
    handover_id: int,
    item_id: int,
    payload: HandoverAssignIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> HandoverOut:
    return _handover_out(hr_service.assign_handover_item(db, current_user, handover_id, item_id, payload))


@router.post("/handovers/{handover_id}/items/{item_id}/confirm", response_model=HandoverOut, summary="接收人确认")
def confirm_item(
    handover_id: int,
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> HandoverOut:
    return _handover_out(hr_service.confirm_handover_item(db, current_user, handover_id, item_id))


@router.post("/handovers/{handover_id}/complete", response_model=HandoverOut, summary="完成交接")
def complete_handover(
    handover_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> HandoverOut:
    return _handover_out(hr_service.complete_handover(db, current_user, handover_id))


@router.get("/leave-requests", response_model=LeaveRequestListOut, summary="假勤申请列表")
def list_leave_requests(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
    status: Annotated[Optional[str], Query()] = None,
    employee_id: Annotated[Optional[int], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LeaveRequestListOut:
    data = hr_service.list_leave_requests(
        db, current_user, status=status, employee_id=employee_id, page=page, page_size=page_size
    )
    return LeaveRequestListOut(total=data["total"], items=[LeaveRequestOut.model_validate(x) for x in data["items"]])


@router.post("/leave-requests", response_model=LeaveRequestOut, summary="提交假勤申请")
def create_leave_request(
    payload: LeaveRequestCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> LeaveRequestOut:
    return LeaveRequestOut.model_validate(hr_service.create_leave_request(db, current_user, payload))


@router.get("/leave-requests/{request_id}", response_model=LeaveRequestOut, summary="假勤申请详情")
def get_leave_request(
    request_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> LeaveRequestOut:
    return LeaveRequestOut.model_validate(hr_service.get_leave_request(db, current_user, request_id))


@router.get("/leave-balances", response_model=list[LeaveBalanceOut], summary="假期余额")
def list_leave_balances(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
    employee_id: Annotated[Optional[int], Query()] = None,
    year: Annotated[Optional[int], Query()] = None,
) -> list[LeaveBalanceOut]:
    return [LeaveBalanceOut.model_validate(x) for x in hr_service.list_leave_balances(db, current_user, employee_id=employee_id, year=year)]


@router.post("/leave-balances", response_model=LeaveBalanceOut, summary="配置假期余额")
def create_leave_balance(
    employee_id: int,
    leave_type: str,
    quota: float,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
    year: Annotated[int, Query()] = 0,
) -> LeaveBalanceOut:
    from datetime import date
    from decimal import Decimal

    y = year or date.today().year
    return LeaveBalanceOut.model_validate(
        hr_service.ensure_leave_balance(db, current_user, employee_id, leave_type, y, Decimal(str(quota)))
    )


@router.patch("/leave-balances/{balance_id}", response_model=LeaveBalanceOut, summary="调入/结转余额")
def patch_leave_balance(
    balance_id: int,
    payload: LeaveBalancePatch,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> LeaveBalanceOut:
    return LeaveBalanceOut.model_validate(hr_service.patch_leave_balance(db, current_user, balance_id, payload))


@router.get("/attendance/monthly", response_model=AttendanceMonthlyOut, summary="月度考勤汇总")
def attendance_monthly(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
    user_id: Annotated[Optional[int], Query()] = None,
    month: Annotated[Optional[str], Query()] = None,
) -> AttendanceMonthlyOut:
    data = hr_service.attendance_monthly(db, current_user, user_id=user_id, month=month)
    data["approved_leaves"] = [LeaveRequestOut.model_validate(x) for x in data["approved_leaves"]]
    return AttendanceMonthlyOut.model_validate(data)


@router.get("/dashboard", response_model=HrDashboardOut, summary="人事看板")
def dashboard(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_org_view)],
) -> HrDashboardOut:
    return HrDashboardOut.model_validate(hr_service.dashboard(db, current_user))


@payslip_router.get("/me", response_model=PayslipListOut, summary="本人工资条")
def my_payslips(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> PayslipListOut:
    data = hr_service.list_my_payslips(db, current_user)
    return PayslipListOut(total=data["total"], items=[PayslipOut.model_validate(x) for x in data["items"]])


@payslip_router.get("", response_model=PayslipListOut, summary="工资条全量")
def list_payslips(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
    period_label: Annotated[Optional[str], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PayslipListOut:
    data = hr_service.list_payslips(db, current_user, period_label=period_label, page=page, page_size=page_size)
    return PayslipListOut(total=data["total"], items=[PayslipOut.model_validate(x) for x in data["items"]])


@payslip_router.get("/{payslip_id}", response_model=PayslipOut, summary="工资条明细")
def get_payslip(
    payslip_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> PayslipOut:
    return PayslipOut.model_validate(hr_service.get_payslip(db, current_user, payslip_id))


@payslip_router.get("/{payslip_id}/download", response_model=PayslipDownloadOut, summary="下载工资条")
def download_payslip(
    payslip_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> PayslipDownloadOut:
    return PayslipDownloadOut.model_validate(hr_service.download_payslip(db, current_user, payslip_id))


@payslip_router.post("/{payslip_id}/correct", response_model=PayslipOut, summary="更正工资条")
def correct_payslip(
    payslip_id: int,
    payload: PayslipCorrectIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(_login)],
) -> PayslipOut:
    return PayslipOut.model_validate(hr_service.correct_payslip(db, current_user, payslip_id, payload))
