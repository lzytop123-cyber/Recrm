"""排期 API。"""
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker
from app.database import get_db
from app.models.user import User
from app.schemas.schedule import (
    ResourceLoadListOut,
    ResourceLoadOut,
    ScheduleCancelRequest,
    ScheduleCompleteRequest,
    ScheduleCoordinateRequest,
    ScheduleCreate,
    ScheduleListOut,
    ScheduleOut,
    ScheduleStatsOut,
    ScheduleUpdate,
)
from app.services import schedule as schedule_service

router = APIRouter(prefix="/schedules", tags=["排期管理"])


class ResourceOption(BaseModel):
    id: int
    name: str
    department_name: Optional[str] = None
    job_title: Optional[str] = None
    role_names: list[str] = []


class PersonTreeNode(BaseModel):
    value: int | str
    label: str
    disabled: bool = False
    is_person: bool = False
    children: list["PersonTreeNode"] = Field(default_factory=list)


PersonTreeNode.model_rebuild()


@router.get("/stats", response_model=ScheduleStatsOut, summary="排期统计")
def stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> ScheduleStatsOut:
    return ScheduleStatsOut(**schedule_service.schedule_stats(db, current_user))


@router.get("/options/resources", response_model=list[ResourceOption], summary="资源人员选项")
def resource_options(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
    resource_type: Optional[str] = Query(
        None,
        description="可选；仅把匹配组织角色的人排到前面：instructor/streamer/shooting_edit/other",
    ),
) -> list[ResourceOption]:
    _ = current_user
    return [
        ResourceOption(**x)
        for x in schedule_service.list_resource_options(db, resource_type=resource_type)
    ]


@router.get(
    "/options/person-tree",
    response_model=list[PersonTreeNode],
    summary="组织架构人员树（部门下挂人）",
)
def person_tree(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> list[PersonTreeNode]:
    _ = current_user
    return [PersonTreeNode.model_validate(x) for x in schedule_service.list_person_tree(db)]


@router.get("/resource-load", response_model=ResourceLoadListOut, summary="资源负载")
def resource_load(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
    resource_type: str = Query(..., description="instructor/streamer/shooting_edit/other"),
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
) -> ResourceLoadListOut:
    items = schedule_service.resource_load(
        db,
        current_user,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
    )
    return ResourceLoadListOut(items=[ResourceLoadOut(**x) for x in items])


@router.get("", response_model=ScheduleListOut, summary="排期列表")
def list_schedules(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
    status: Optional[str] = None,
    resource_type: Optional[str] = None,
    employee_id: Optional[int] = None,
    project_id: Optional[int] = None,
    project_task_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    scope: Optional[str] = Query(None, description="mine/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ScheduleListOut:
    total, items = schedule_service.list_schedules(
        db,
        current_user,
        status=status,
        resource_type=resource_type,
        employee_id=employee_id,
        project_id=project_id,
        project_task_id=project_task_id,
        date_from=date_from,
        date_to=date_to,
        scope_filter=scope,
        page=page,
        page_size=page_size,
    )
    return ScheduleListOut(total=total, items=[ScheduleOut.model_validate(x) for x in items])


@router.post("", response_model=ScheduleOut, summary="申请排期")
def create_schedule(
    payload: ScheduleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> ScheduleOut:
    return ScheduleOut.model_validate(schedule_service.create_schedule(db, current_user, payload))


@router.get("/{schedule_id}", response_model=ScheduleOut, summary="排期详情")
def get_schedule(
    schedule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> ScheduleOut:
    return ScheduleOut.model_validate(schedule_service.get_schedule(db, current_user, schedule_id))


@router.patch("/{schedule_id}", response_model=ScheduleOut, summary="编辑排期")
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> ScheduleOut:
    return ScheduleOut.model_validate(
        schedule_service.update_schedule(db, current_user, schedule_id, payload)
    )


@router.post("/{schedule_id}/confirm", response_model=ScheduleOut, summary="确认排期")
def confirm_schedule(
    schedule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> ScheduleOut:
    return ScheduleOut.model_validate(
        schedule_service.confirm_schedule(db, current_user, schedule_id)
    )


@router.post("/{schedule_id}/coordinate", response_model=ScheduleOut, summary="请求协调")
def coordinate_schedule(
    schedule_id: int,
    payload: ScheduleCoordinateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> ScheduleOut:
    return ScheduleOut.model_validate(
        schedule_service.request_coordination(db, current_user, schedule_id, payload)
    )


@router.post("/{schedule_id}/start", response_model=ScheduleOut, summary="开始执行")
def start_schedule(
    schedule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> ScheduleOut:
    return ScheduleOut.model_validate(
        schedule_service.start_schedule(db, current_user, schedule_id)
    )


@router.post("/{schedule_id}/complete", response_model=ScheduleOut, summary="完成排期")
def complete_schedule(
    schedule_id: int,
    payload: ScheduleCompleteRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> ScheduleOut:
    return ScheduleOut.model_validate(
        schedule_service.complete_schedule(db, current_user, schedule_id, payload)
    )


@router.post("/{schedule_id}/cancel", response_model=ScheduleOut, summary="取消排期")
def cancel_schedule(
    schedule_id: int,
    payload: ScheduleCancelRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> ScheduleOut:
    return ScheduleOut.model_validate(
        schedule_service.cancel_schedule(db, current_user, schedule_id, payload)
    )


@router.delete("/{schedule_id}", summary="删除排期（仅管理员，已完成也可删）")
def delete_schedule(
    schedule_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(PermissionChecker(["schedule:view"]))],
) -> dict:
    schedule_service.delete_schedule(db, current_user, schedule_id)
    return {"ok": True, "message": "已删除"}
