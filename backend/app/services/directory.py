"""公共目录：业务选人/选部门/挂接项目，不要求 org:view / project:view。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.contract import Contract
from app.models.customer import Customer
from app.models.project import Project, ProjectTask
from app.models.user import User
from app.services import org as org_service


def list_departments_for_picker(db: Session) -> list:
    """部门树（结构同员工管理，但不要求 org:view）。"""
    return org_service.build_department_tree(db)


def list_people_for_picker(
    db: Session,
    *,
    keyword: Optional[str] = None,
    department_id: Optional[int] = None,
    is_active: Optional[bool] = True,
    page: int = 1,
    page_size: int = 50,
) -> tuple[int, list[dict]]:
    """在职人员精简列表：仅 id/姓名/部门等选人字段。"""
    q = db.query(User).options(joinedload(User.department))
    if department_id:
        q = q.filter(User.department_id == department_id)
    if is_active is not None:
        q = q.filter(User.is_active.is_(is_active))
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(
            (User.username.like(like))
            | (User.real_name.like(like))
            | (User.job_title.like(like))
            | (User.employee_no.like(like))
        )
    total = q.count()
    rows = (
        q.order_by(User.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": u.id,
            "username": u.username,
            "real_name": u.real_name,
            "job_title": u.job_title,
            "department_id": u.department_id,
            "department_name": u.department.name if u.department else None,
            "is_active": bool(u.is_active),
        }
        for u in rows
    ]
    return total, items


def list_projects_for_picker(
    db: Session,
    *,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[int, list[dict]]:
    """项目精简列表：工单/排期/工时挂接用，不要求 project:view。"""
    q = db.query(Project)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(or_(Project.name.ilike(like), Project.project_no.ilike(like)))
    total = q.count()
    rows = (
        q.order_by(Project.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": p.id,
            "name": p.name,
            "project_no": p.project_no,
            "status": p.status,
        }
        for p in rows
    ]
    return total, items


def list_project_tasks_for_picker(
    db: Session,
    *,
    project_id: int,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> tuple[int, list[dict]]:
    """某项目下任务精简列表：排期/工单挂接用。"""
    q = db.query(ProjectTask).filter(ProjectTask.project_id == project_id)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(ProjectTask.title.ilike(like))
    total = q.count()
    rows = (
        q.order_by(ProjectTask.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": t.id,
            "project_id": t.project_id,
            "title": t.title,
            "status": t.status,
        }
        for t in rows
    ]
    return total, items


def list_customers_for_picker(
    db: Session,
    *,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[int, list[dict]]:
    """客户精简列表：合同/商机选客户用。"""
    q = db.query(Customer)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(or_(Customer.name.ilike(like), Customer.short_name.ilike(like)))
    total = q.count()
    rows = (
        q.order_by(Customer.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, [{"id": c.id, "name": c.name} for c in rows]


def list_contracts_for_picker(
    db: Session,
    *,
    user: Optional[User] = None,
    mine_only: bool = False,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[int, list[dict]]:
    """合同精简列表：项目/收款挂接用。"""
    q = db.query(Contract, Customer.name).outerjoin(
        Customer, Customer.id == Contract.customer_id
    )
    if mine_only and user is not None:
        q = q.filter(or_(Contract.owner_id == user.id, Contract.creator_id == user.id))
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(
            or_(
                Contract.title.ilike(like),
                Contract.contract_no.ilike(like),
                Customer.name.ilike(like),
            )
        )
    total = q.count()
    rows = (
        q.order_by(Contract.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": c.id,
            "contract_no": c.contract_no,
            "title": c.title,
            "status": c.status,
            "customer_name": cust_name,
        }
        for c, cust_name in rows
    ]
    return total, items
