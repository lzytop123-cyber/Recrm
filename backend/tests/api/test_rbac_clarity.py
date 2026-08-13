"""资产/系统权限拆分与销售工单侧栏。"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services.asset import can_manage_assets
from app.services.menu import build_menus_for_user


def _user_with_perms(db: Session, username: str, *codes: str, role_code: str | None = None) -> User:
    role = Role(
        name=f"{username}-role",
        code=role_code or f"{username}_role",
        data_scope="company",
    )
    for code in codes:
        role.permissions.append(
            Permission(name=code, code=code, module=code.split(":")[0])
        )
    user = User(
        username=username,
        password_hash=hash_password("secret123"),
        real_name=username,
        is_active=True,
    )
    user.roles.append(role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_asset_manage_permission_not_role_hardcode(db_session: Session) -> None:
    yes = _user_with_perms(db_session, "asset_mgr", "asset:manage", role_code="asset_admin")
    view_only = _user_with_perms(db_session, "asset_viewer", "asset:view", role_code="employee")
    assert can_manage_assets(yes) is True
    assert can_manage_assets(view_only) is False


def test_sales_has_ticket_perm_but_no_tickets_menu(db_session: Session) -> None:
    sales = _user_with_perms(
        db_session,
        "sales_menu",
        "dashboard:view",
        "lead:view",
        "ticket:view",
        role_code="sales",
    )
    paths = {m.path for m in build_menus_for_user(sales)}
    assert "/tickets" not in paths
    assert "/dashboard" in paths


def test_employee_still_sees_tickets_menu(db_session: Session) -> None:
    emp = _user_with_perms(
        db_session,
        "emp_menu",
        "ticket:view",
        "schedule:view",
        role_code="employee",
    )
    paths = {m.path for m in build_menus_for_user(emp)}
    assert "/tickets" in paths


def test_system_manage_required_for_role_create(
    client: TestClient,
    db_session: Session,
) -> None:
    _user_with_perms(db_session, "sys_viewer", "system:view")
    headers = _auth_headers(client, "sys_viewer")
    assert client.get("/api/v1/system/roles", headers=headers).status_code == 200
    denied = client.post(
        "/api/v1/system/roles",
        headers=headers,
        json={"name": "临时", "code": "tmp_role_x", "data_scope": "personal", "permission_ids": []},
    )
    assert denied.status_code == 403


def test_seed_has_asset_and_system_manage() -> None:
    from app.seed import PERMISSIONS, ROLES

    codes = {p[1] for p in PERMISSIONS}
    assert "asset:manage" in codes
    assert "system:manage" in codes
    by_code = {r[1]: r for r in ROLES}
    assert "asset:manage" in by_code["asset_admin"][3]
    assert "asset:manage" in by_code["operations"][3]
    assert "lead:view" in by_code["operations"][3]
    assert "ticket:view" in by_code["sales"][3]


def test_operations_sees_lead_entry_not_sales(db_session: Session) -> None:
    ops = _user_with_perms(
        db_session,
        "ops_menu",
        "lead:view",
        "customer:view",
        "dashboard:view",
        role_code="operations",
    )
    paths = {m.path for m in build_menus_for_user(ops)}
    assert "/lead-entry" in paths
    assert "/sales" not in paths
