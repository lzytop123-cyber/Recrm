"""飞书通讯录同步：用假客户端注入，不访问真实开放平台。"""
from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.services.feishu_auth import FeishuAuthError
from app.services.feishu_contact_sync import sync_feishu_contacts


class FakeFeishuClient:
    def __init__(self) -> None:
        self.dept_tree = {
            "0": [
                {
                    "open_department_id": "od_sales",
                    "name": "销售部",
                    "department_id": "od_sales",
                }
            ],
            "od_sales": [],
        }
        self.users = {
            "0": [
                {
                    "open_id": "ou_admin_like",
                    "user_id": "uid_admin",
                    "name": "管理员甲",
                    "email": "admin@ztxd.com",
                    "mobile": "+8613800000001",
                    "job_title": "总经理",
                    "employee_no": "YG-0001",
                    "join_time": 1704672000,
                    "employee_type": 1,
                    "status": {"is_activated": True, "is_resigned": False},
                    "department_ids": ["0"],
                }
            ],
            "od_sales": [
                {
                    "open_id": "ou_sales_1",
                    "user_id": "uid_sales_1",
                    "name": "销售小王",
                    "email": "wang@ztxd.com",
                    "mobile": "13800000002",
                    "job_title": "销售经理",
                    "employee_no": "YG-0012",
                    "join_time": 1710720000,
                    "employee_type": 1,
                    "leader_user_id": "ou_admin_like",
                    "status": {"is_activated": True, "is_resigned": False},
                    "department_ids": ["od_sales"],
                }
            ],
        }

    async def iter_department_children(self, department_id: str = "0", *, fetch_child: bool = False):
        _ = fetch_child
        return list(self.dept_tree.get(department_id, []))

    async def iter_users_by_department(self, department_id: str):
        return list(self.users.get(department_id, []))

    async def list_contact_scopes(self):
        return {"department_ids": [], "user_ids": [], "group_ids": []}

    async def get_department(self, department_id: str):
        return {"open_department_id": department_id, "name": department_id}

    async def get_user(self, user_id: str):
        return {"open_id": user_id, "name": user_id}


class ScopeOnlyFeishuClient:
    """模拟「与应用可用范围一致」：根部门无权限，仅 scopes 有数据。"""

    async def iter_department_children(self, department_id: str = "0", *, fetch_child: bool = False):
        _ = fetch_child
        if department_id == "0":
            raise FeishuAuthError("no dept authority error", detail={"code": 40004})
        if department_id == "od_sales":
            return []
        return []

    async def iter_users_by_department(self, department_id: str):
        if department_id == "0":
            raise FeishuAuthError("no dept authority error", detail={"code": 40004})
        if department_id == "od_sales":
            return [
                {
                    "open_id": "ou_sales_1",
                    "name": "销售小王",
                    "email": "wang@ztxd.com",
                    "mobile": "13800000002",
                    "status": {"is_activated": True, "is_resigned": False},
                    "department_ids": ["od_sales"],
                }
            ]
        return []

    async def list_contact_scopes(self):
        return {
            "department_ids": ["od_sales"],
            "user_ids": ["ou_solo"],
            "group_ids": [],
        }

    async def get_department(self, department_id: str):
        if department_id == "od_sales":
            return {"open_department_id": "od_sales", "name": "销售部"}
        return {"open_department_id": department_id, "name": department_id}

    async def get_user(self, user_id: str):
        if user_id == "ou_solo":
            return {
                "open_id": "ou_solo",
                "name": "单独授权用户",
                "email": "solo@ztxd.com",
                "department_ids": [],
                "status": {"is_activated": True, "is_resigned": False},
            }
        return {"open_id": user_id, "name": user_id}


def test_sync_creates_departments_and_employees(db_session: Session) -> None:
    db_session.add(Role(name="普通员工", code="employee", data_scope="personal"))
    db_session.add(Department(name="总公司", code="ROOT"))
    db_session.commit()

    result = asyncio.run(sync_feishu_contacts(db_session, client=FakeFeishuClient()))  # type: ignore[arg-type]

    assert result.departments_created >= 1
    assert result.employees_created == 2
    sales = db_session.query(Department).filter(Department.code == "FS_od_sales").first()
    assert sales is not None
    assert sales.name == "销售部"
    wang = db_session.query(User).filter(User.feishu_open_id == "ou_sales_1").first()
    assert wang is not None
    assert wang.real_name == "销售小王"
    assert wang.department_id == sales.id
    assert wang.job_title == "销售经理"
    assert wang.employee_no == "YG-0012"
    assert wang.feishu_user_id == "uid_sales_1"
    assert wang.employment_status == "正式"
    assert wang.hire_date is not None
    admin = db_session.query(User).filter(User.feishu_open_id == "ou_admin_like").first()
    assert admin is not None
    assert wang.manager_id == admin.id
    from app.models.employee_hr import EmployeeHistoryEvent, SystemSyncState

    hire = (
        db_session.query(EmployeeHistoryEvent)
        .filter(
            EmployeeHistoryEvent.user_id == wang.id,
            EmployeeHistoryEvent.event_type == "hire",
        )
        .first()
    )
    assert hire is not None
    state = db_session.query(SystemSyncState).filter(SystemSyncState.key == "feishu_contact").first()
    assert state is not None
    assert state.status == "ok"


def test_sync_binds_existing_user_by_email(db_session: Session) -> None:
    db_session.add(Role(name="普通员工", code="employee", data_scope="personal"))
    db_session.add(Department(name="总公司", code="ROOT"))
    existing = User(
        username="wang",
        password_hash=hash_password("x"),
        real_name="旧名",
        email="wang@ztxd.com",
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()

    result = asyncio.run(sync_feishu_contacts(db_session, client=FakeFeishuClient()))  # type: ignore[arg-type]

    assert result.employees_bound >= 1
    db_session.refresh(existing)
    assert existing.feishu_open_id == "ou_sales_1"
    assert existing.real_name == "销售小王"


def test_sync_falls_back_to_contact_scopes(db_session: Session) -> None:
    db_session.add(Role(name="普通员工", code="employee", data_scope="personal"))
    db_session.add(Department(name="总公司", code="ROOT"))
    db_session.commit()

    result = asyncio.run(sync_feishu_contacts(db_session, client=ScopeOnlyFeishuClient()))  # type: ignore[arg-type]

    assert result.employees_created == 2
    sales = db_session.query(Department).filter(Department.code == "FS_od_sales").first()
    assert sales is not None
    wang = db_session.query(User).filter(User.feishu_open_id == "ou_sales_1").first()
    solo = db_session.query(User).filter(User.feishu_open_id == "ou_solo").first()
    assert wang is not None
    assert solo is not None
    assert any("授权范围" in w for w in result.warnings)
