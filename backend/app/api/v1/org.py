"""组织员工 / 员工管理 API。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.org import (
    AttendanceSummaryOut,
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeHistoryOut,
    EmployeeListOut,
    EmployeeOut,
    EmployeeResetPassword,
    EmployeeUpdate,
    FeishuAttendanceSyncRequest,
    FeishuAttendanceSyncResult,
    FeishuContactSyncResult,
    FeishuSyncStatusOut,
    OrgStatsOut,
    RoleBriefOut,
)
from app.services import org as org_service
from app.services.feishu_attendance import get_attendance_summary, sync_feishu_attendance
from app.services.feishu_auth import FeishuAuthError
from app.services.feishu_contact_sync import sync_feishu_contacts
from app.services.sync_state import list_feishu_sync_status

router = APIRouter(prefix="/org", tags=["员工管理"])


@router.get("/stats", response_model=OrgStatsOut, summary="组织统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:view"]))],
) -> OrgStatsOut:
    _ = current_user
    return OrgStatsOut(**org_service.org_stats(db))


@router.get("/departments", response_model=list[DepartmentOut], summary="部门树")
def department_tree(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:view"]))],
) -> list[DepartmentOut]:
    _ = current_user
    return [DepartmentOut.model_validate(x) for x in org_service.build_department_tree(db)]


@router.post("/departments", response_model=DepartmentOut, summary="创建部门")
def create_department(
    payload: DepartmentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:manage"]))],
) -> DepartmentOut:
    _ = current_user
    return DepartmentOut.model_validate(org_service.create_department(db, payload))


@router.patch("/departments/{dept_id}", response_model=DepartmentOut, summary="编辑部门")
def update_department(
    dept_id: int,
    payload: DepartmentUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:manage"]))],
) -> DepartmentOut:
    _ = current_user
    return DepartmentOut.model_validate(org_service.update_department(db, dept_id, payload))


@router.delete("/departments/{dept_id}", summary="删除部门")
def delete_department(
    dept_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:manage"]))],
) -> dict:
    _ = current_user
    org_service.delete_department(db, dept_id)
    return {"ok": True}


@router.get("/roles", response_model=list[RoleBriefOut], summary="角色选项")
def role_options(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:view"]))],
) -> list[RoleBriefOut]:
    _ = current_user
    return [RoleBriefOut.model_validate(x) for x in org_service.list_role_options(db)]


@router.get("/employees", response_model=EmployeeListOut, summary="员工列表")
def list_employees(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:view"]))],
    keyword: Optional[str] = None,
    department_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    employment_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> EmployeeListOut:
    _ = current_user
    total, items = org_service.list_employees(
        db,
        keyword=keyword,
        department_id=department_id,
        is_active=is_active,
        employment_status=employment_status,
        page=page,
        page_size=page_size,
    )
    return EmployeeListOut(total=total, items=[EmployeeOut.model_validate(x) for x in items])


@router.post("/employees", response_model=EmployeeOut, summary="创建员工")
def create_employee(
    payload: EmployeeCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:manage"]))],
) -> EmployeeOut:
    _ = current_user
    return EmployeeOut.model_validate(org_service.create_employee(db, payload))


@router.get("/employees/{user_id}", response_model=EmployeeOut, summary="员工详情")
def get_employee(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:view"]))],
) -> EmployeeOut:
    _ = current_user
    return EmployeeOut.model_validate(org_service.get_employee(db, user_id, with_overview=True))


@router.get(
    "/employees/{user_id}/history",
    response_model=list[EmployeeHistoryOut],
    summary="任职经历",
)
def employee_history(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:view"]))],
) -> list[EmployeeHistoryOut]:
    _ = current_user
    return [EmployeeHistoryOut.model_validate(x) for x in org_service.list_employee_history(db, user_id)]


@router.get(
    "/employees/{user_id}/attendance",
    response_model=AttendanceSummaryOut,
    summary="员工飞书考勤汇总",
)
async def employee_attendance(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:view"]))],
    month: Optional[str] = Query(None, description="YYYY-MM"),
    refresh: bool = Query(False, description="是否先从飞书刷新"),
) -> AttendanceSummaryOut:
    _ = current_user
    if refresh:
        try:
            await sync_feishu_attendance(db, user_id=user_id, month=month)
        except FeishuAuthError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"飞书考勤同步失败: {exc}",
            ) from exc
    return AttendanceSummaryOut(**get_attendance_summary(db, user_id, month=month))


@router.patch("/employees/{user_id}", response_model=EmployeeOut, summary="编辑员工")
def update_employee(
    user_id: int,
    payload: EmployeeUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:manage"]))],
) -> EmployeeOut:
    return EmployeeOut.model_validate(
        org_service.update_employee(db, user_id, payload, actor=current_user)
    )


@router.post(
    "/employees/{user_id}/reset-password",
    response_model=EmployeeOut,
    summary="重置密码",
)
def reset_password(
    user_id: int,
    payload: EmployeeResetPassword,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:manage"]))],
) -> EmployeeOut:
    _ = current_user
    return EmployeeOut.model_validate(org_service.reset_employee_password(db, user_id, payload))


@router.get("/feishu/sync-status", response_model=FeishuSyncStatusOut, summary="飞书同步状态")
def feishu_sync_status(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:view"]))],
) -> FeishuSyncStatusOut:
    _ = current_user
    return FeishuSyncStatusOut(**list_feishu_sync_status(db))


@router.post(
    "/feishu/sync",
    response_model=FeishuContactSyncResult,
    summary="从飞书通讯录同步部门与员工",
)
async def sync_feishu_org(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:sync"]))],
) -> FeishuContactSyncResult:
    """
    使用应用 tenant_access_token 拉取通讯录：
    - 部门按 open_department_id 映射到本地 code=FS_{id}
    - 员工按 open_id / 邮箱 / 手机匹配；写入 user_id、工号、入职日、负责人
    需在飞书应用开通通讯录只读权限，并配置可用范围。
    """
    _ = current_user
    try:
        result = await sync_feishu_contacts(db)
    except FeishuAuthError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"飞书通讯录同步失败: {exc}",
        ) from exc
    return FeishuContactSyncResult(**result.as_dict())


@router.post(
    "/feishu/attendance/sync",
    response_model=FeishuAttendanceSyncResult,
    summary="从飞书拉取考勤事实",
)
async def sync_feishu_attendance_api(
    payload: FeishuAttendanceSyncRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["org:sync"]))],
) -> FeishuAttendanceSyncResult:
    """
    调用 attendance/v1/user_tasks/query（employee_id / employee_no）。
    需开通「导出打卡数据」权限，并先完成通讯录同步以获得 feishu_user_id。
    """
    _ = current_user
    try:
        result = await sync_feishu_attendance(
            db, user_id=payload.user_id, month=payload.month
        )
    except FeishuAuthError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"飞书考勤同步失败: {exc}",
        ) from exc
    return FeishuAttendanceSyncResult(**result.as_dict())
