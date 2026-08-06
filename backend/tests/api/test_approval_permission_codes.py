"""审批相关权限码：contract:approve / project:accept_approve / project:finance_approve。"""

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services.contract import can_approve_contract
from app.services.project import can_approve_acceptance, can_review_finance_check
from app.services.timesheet import can_approve as can_approve_timesheet


def _user_with_perms(db: Session, username: str, *codes: str) -> User:
    role = Role(name=f"{username}-role", code=f"{username}_role", data_scope="company")
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


def test_contract_approve_permission_gate(db_session: Session) -> None:
    yes = _user_with_perms(db_session, "c_yes", "contract:approve")
    no = _user_with_perms(db_session, "c_no", "contract:view")
    assert can_approve_contract(yes) is True
    assert can_approve_contract(no) is False


def test_project_accept_and_finance_permission_gates(db_session: Session) -> None:
    accept = _user_with_perms(db_session, "p_acc", "project:accept_approve")
    finance = _user_with_perms(db_session, "p_fin", "project:finance_approve")
    viewer = _user_with_perms(db_session, "p_view", "project:view")
    assert can_approve_acceptance(accept) is True
    assert can_approve_acceptance(viewer) is False
    assert can_review_finance_check(finance) is True
    assert can_review_finance_check(viewer) is False


def test_timesheet_approve_permission_gate(db_session: Session) -> None:
    yes = _user_with_perms(db_session, "ts_yes", "timesheet:approve")
    no = _user_with_perms(db_session, "ts_no", "timesheet:view")
    assert can_approve_timesheet(yes) is True
    assert can_approve_timesheet(no) is False


def test_seed_roles_include_board_and_new_perms() -> None:
    from app.seed import PERMISSIONS, ROLES

    codes = {p[1] for p in PERMISSIONS}
    assert "contract:approve" in codes
    assert "contract:complete" in codes
    assert "contract:force_complete" in codes
    assert "project:accept_submit" in codes
    assert "project:accept_approve" in codes
    assert "project:finance_submit" in codes
    assert "project:finance_approve" in codes
    assert "project:complete" in codes
    assert "timesheet:approve" in codes

    by_code = {r[1]: r for r in ROLES}
    assert "board" in by_code
    assert "contract:approve" in by_code["dept_head"][3]
    assert "approval:center" in by_code["dept_head"][3]
    assert "contract:approve" in by_code["finance"][3]
    assert "contract:force_complete" in by_code["finance"][3]
    assert "project:finance_approve" in by_code["finance"][3]
    assert "project:accept_approve" in by_code["delivery_lead"][3]
    assert "project:accept_submit" in by_code["delivery_lead"][3]
    assert "contract:force_complete" not in by_code["sales"][3]
    assert "contract:complete" in by_code["sales"][3]


def test_admin_role_code_still_bypasses(db_session: Session) -> None:
    role = Role(name="管理员", code="admin", data_scope="company")
    user = User(
        username="admin_bypass",
        password_hash=hash_password("secret123"),
        real_name="管理员",
        is_active=True,
    )
    user.roles.append(role)
    db_session.add_all([role, user])
    db_session.commit()
    db_session.refresh(user)
    assert can_approve_contract(user) is True
    assert can_approve_acceptance(user) is True
    assert can_review_finance_check(user) is True
    assert can_approve_timesheet(user) is True
