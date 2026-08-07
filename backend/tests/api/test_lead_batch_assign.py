"""管理层待分配池与批量分配（对齐最终 PRD + 原型 lead-allocation）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.lead import LEAD_STATUS_ASSIGNED, LEAD_STATUS_PENDING, Lead
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.schemas.lead import LeadCreate
from app.services import lead as lead_service


def _ensure_role(db: Session, code: str, name: str, *, manage: bool) -> Role:
    role = db.query(Role).filter(Role.code == code).first()
    if not role:
        role = Role(name=name, code=code, data_scope="personal" if code == "sales" else "company")
        db.add(role)
        db.flush()
    if manage:
        perm = db.query(Permission).filter(Permission.code == "lead:manage").first()
        if not perm:
            perm = Permission(name="管理线索", code="lead:manage", module="lead")
            db.add(perm)
            db.flush()
        if perm not in role.permissions:
            role.permissions.append(perm)
        view = db.query(Permission).filter(Permission.code == "lead:view").first()
        if not view:
            view = Permission(name="查看线索", code="lead:view", module="lead")
            db.add(view)
            db.flush()
        if view not in role.permissions:
            role.permissions.append(view)
    else:
        view = db.query(Permission).filter(Permission.code == "lead:view").first()
        if not view:
            view = Permission(name="查看线索", code="lead:view", module="lead")
            db.add(view)
            db.flush()
        if view not in role.permissions:
            role.permissions.append(view)
    db.flush()
    return role


def _user(db: Session, username: str, role: Role) -> User:
    dept = db.query(Department).filter(Department.code == "ROOT").first()
    if not dept:
        dept = Department(name="总公司", code="ROOT")
        db.add(dept)
        db.flush()
    u = User(
        username=username,
        password_hash=hash_password("x"),
        real_name=username,
        is_active=True,
        department_id=dept.id,
    )
    u.roles.append(role)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_sales_create_defaults_to_self_follow(db_session: Session) -> None:
    from app.models.lead import LEAD_STATUS_ASSIGNED

    sales_role = _ensure_role(db_session, "sales", "销售", manage=False)
    sales = _user(db_session, "sales_self", sales_role)
    lead = lead_service.create_lead(
        db_session,
        sales,
        LeadCreate(name="自跟进客户", company_name="自跟进公司", phone="13900002222"),
    )
    assert lead.status == LEAD_STATUS_ASSIGNED
    assert lead.owner_id == sales.id


def test_unassigned_pool_hidden_from_sales(db_session: Session) -> None:
    mgr_role = _ensure_role(db_session, "executive", "管理层", manage=True)
    sales_role = _ensure_role(db_session, "sales", "销售", manage=False)
    manager = _user(db_session, "mgr_alloc", mgr_role)
    sales = _user(db_session, "sales_alloc", sales_role)

    lead = lead_service.create_lead(
        db_session,
        sales,
        LeadCreate(
            name="隐藏客户",
            company_name="隐藏公司",
            phone="13900001111",
            self_follow=False,
        ),
    )
    assert lead.status == LEAD_STATUS_PENDING

    total_sales, items_sales = lead_service.list_leads(db_session, sales, pool="public")
    assert total_sales == 0
    assert items_sales == []

    total_mgr, items_mgr = lead_service.list_leads(db_session, manager, pool="public")
    assert total_mgr >= 1
    assert any(x.id == lead.id for x in items_mgr)


def test_batch_assign_average(db_session: Session) -> None:
    mgr_role = _ensure_role(db_session, "executive", "管理层", manage=True)
    sales_role = _ensure_role(db_session, "sales", "销售", manage=False)
    manager = _user(db_session, "mgr_batch", mgr_role)
    a = _user(db_session, "sales_a", sales_role)
    b = _user(db_session, "sales_b", sales_role)

    leads = []
    for i in range(3):
        leads.append(
            lead_service.create_lead(
                db_session,
                manager,
                LeadCreate(name=f"客户{i}", company_name=f"公司{i}", phone=f"1370000000{i}"),
            )
        )

    result = lead_service.batch_assign_leads(
        db_session,
        manager,
        lead_ids=[x.id for x in leads],
        owner_ids=[a.id, b.id],
        method="average",
        reason="管理层批量分配",
    )
    assert result["success_count"] == 3
    assert result["failed_count"] == 0

    owners = {
        db_session.query(Lead).filter(Lead.id == lid).first().owner_id  # type: ignore[union-attr]
        for lid in [x.id for x in leads]
    }
    assert owners == {a.id, b.id}
    for lid in [x.id for x in leads]:
        row = db_session.query(Lead).filter(Lead.id == lid).first()
        assert row is not None
        assert row.status == LEAD_STATUS_ASSIGNED
