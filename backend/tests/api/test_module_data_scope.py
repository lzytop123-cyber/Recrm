"""按模块解析数据范围 resolve_data_scope。"""

from app.core.rbac import resolve_data_scope, widest_data_scope
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def _role(
    *,
    name: str,
    code: str,
    data_scope: str,
    perms: list[tuple[str, str]],
    module_scopes: dict | None = None,
) -> Role:
    role = Role(
        name=name,
        code=code,
        data_scope=data_scope,
        module_scopes=module_scopes or {},
    )
    for pname, pcode in perms:
        role.permissions.append(
            Permission(name=pname, code=pcode, module=pcode.split(":")[0])
        )
    return role


def test_resolve_falls_back_to_role_default_scope() -> None:
    user = User(username="u1", password_hash="x", is_active=True)
    user.roles.append(
        _role(
            name="销售",
            code="sales_x",
            data_scope="department",
            perms=[("线索查看", "lead:view")],
        )
    )
    assert resolve_data_scope(user, "lead") == "department"
    assert resolve_data_scope(user, "ticket") == "personal"


def test_resolve_uses_module_override() -> None:
    user = User(username="u2", password_hash="x", is_active=True)
    user.roles.append(
        _role(
            name="秘书",
            code="secretary",
            data_scope="company",
            perms=[
                ("线索查看", "lead:view"),
                ("工单查看", "ticket:view"),
            ],
            module_scopes={"ticket": "personal", "lead": "department"},
        )
    )
    assert resolve_data_scope(user, "lead") == "department"
    assert resolve_data_scope(user, "ticket") == "personal"
    assert resolve_data_scope(user, "contract") == "personal"


def test_resolve_multi_role_only_counts_roles_with_module_perm() -> None:
    user = User(username="u3", password_hash="x", is_active=True)
    user.roles.append(
        _role(
            name="销售部",
            code="sales_dept",
            data_scope="department",
            perms=[("线索查看", "lead:view")],
        )
    )
    user.roles.append(
        _role(
            name="员工工单",
            code="emp_ticket",
            data_scope="personal",
            perms=[("工单查看", "ticket:view")],
            module_scopes={"ticket": "personal"},
        )
    )
    # 旧逻辑会因销售角色 department + 员工 personal 取最宽 → department 套到工单
    assert widest_data_scope({"department", "personal"}) == "department"
    assert resolve_data_scope(user, "lead") == "department"
    assert resolve_data_scope(user, "ticket") == "personal"


def test_resolve_admin_is_company() -> None:
    user = User(username="admin_x", password_hash="x", is_active=True)
    user.roles.append(
        _role(
            name="系统管理员",
            code="admin",
            data_scope="personal",
            perms=[("线索查看", "lead:view")],
            module_scopes={"lead": "personal"},
        )
    )
    assert resolve_data_scope(user, "lead") == "company"


def test_resolve_widest_among_matching_roles() -> None:
    user = User(username="u4", password_hash="x", is_active=True)
    user.roles.append(
        _role(
            name="A",
            code="role_a",
            data_scope="personal",
            perms=[("线索查看", "lead:view")],
            module_scopes={"lead": "personal"},
        )
    )
    user.roles.append(
        _role(
            name="B",
            code="role_b",
            data_scope="company",
            perms=[("线索管理", "lead:manage")],
        )
    )
    assert resolve_data_scope(user, "lead") == "company"
