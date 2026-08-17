"""公共目录 API：登录即可读，与 org:view / project:view 模块入口解耦。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.schemas.directory import (
    DirectoryContractListOut,
    DirectoryContractOut,
    DirectoryCustomerListOut,
    DirectoryCustomerOut,
    DirectoryDepartmentOut,
    DirectoryPersonListOut,
    DirectoryPersonOut,
    DirectoryProjectListOut,
    DirectoryProjectOut,
    DirectoryProjectTaskListOut,
    DirectoryProjectTaskOut,
)
from app.services import directory as directory_service

router = APIRouter(prefix="/directory", tags=["公共目录"])


def _dept_node(d) -> DirectoryDepartmentOut:
    children = [_dept_node(c) for c in (getattr(d, "children", None) or [])]
    return DirectoryDepartmentOut(
        id=d.id,
        name=d.name,
        code=d.code,
        parent_id=d.parent_id,
        children=children,
    )


@router.get(
    "/departments",
    response_model=list[DirectoryDepartmentOut],
    summary="部门树（业务选部门，登录可读）",
)
def list_departments(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[DirectoryDepartmentOut]:
    _ = current_user
    return [_dept_node(x) for x in directory_service.list_departments_for_picker(db)]


@router.get(
    "/people",
    response_model=DirectoryPersonListOut,
    summary="人员选项（业务选人，登录可读）",
)
def list_people(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    keyword: Optional[str] = None,
    department_id: Optional[int] = None,
    is_active: Optional[bool] = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> DirectoryPersonListOut:
    _ = current_user
    total, items = directory_service.list_people_for_picker(
        db,
        keyword=keyword,
        department_id=department_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return DirectoryPersonListOut(
        total=total,
        items=[DirectoryPersonOut.model_validate(x) for x in items],
    )


@router.get(
    "/projects",
    response_model=DirectoryProjectListOut,
    summary="项目选项（挂接用，登录可读；不开项目管理）",
)
def list_projects(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> DirectoryProjectListOut:
    _ = current_user
    total, items = directory_service.list_projects_for_picker(
        db,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return DirectoryProjectListOut(
        total=total,
        items=[DirectoryProjectOut.model_validate(x) for x in items],
    )


@router.get(
    "/project-tasks",
    response_model=DirectoryProjectTaskListOut,
    summary="项目任务选项（挂接用，登录可读）",
)
def list_project_tasks(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    project_id: int = Query(..., ge=1),
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
) -> DirectoryProjectTaskListOut:
    _ = current_user
    total, items = directory_service.list_project_tasks_for_picker(
        db,
        project_id=project_id,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return DirectoryProjectTaskListOut(
        total=total,
        items=[DirectoryProjectTaskOut.model_validate(x) for x in items],
    )


@router.get(
    "/customers",
    response_model=DirectoryCustomerListOut,
    summary="客户选项（挂接用，登录可读）",
)
def list_customers(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> DirectoryCustomerListOut:
    _ = current_user
    total, items = directory_service.list_customers_for_picker(
        db,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return DirectoryCustomerListOut(
        total=total,
        items=[DirectoryCustomerOut.model_validate(x) for x in items],
    )


@router.get(
    "/contracts",
    response_model=DirectoryContractListOut,
    summary="合同选项（挂接用，登录可读；不开合同回款）",
)
def list_contracts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    keyword: Optional[str] = None,
    mine: bool = Query(False, description="仅本人负责或创建的合同（立项选合同）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> DirectoryContractListOut:
    total, items = directory_service.list_contracts_for_picker(
        db,
        user=current_user,
        mine_only=mine,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return DirectoryContractListOut(
        total=total,
        items=[DirectoryContractOut.model_validate(x) for x in items],
    )
