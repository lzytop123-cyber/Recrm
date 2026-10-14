"""飞书通讯录同步：岗位字段「只填空缺、不覆盖」回归测试（2026-10-14 事故）。"""
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.user import User
from app.services.feishu_contact_sync import FeishuSyncResult, _upsert_employee


def _dept(db: Session) -> Department:
    d = Department(name="新媒体运营交付中心", code="FEISHU_DEPT_X")
    db.add(d)
    db.flush()
    return d


def _item(open_id: str, name: str, job_title: str | None) -> dict:
    return {
        "open_id": open_id,
        "name": name,
        "job_title": job_title,
        "status": {"is_resigned": False, "is_activated": True},
    }


def test_sync_does_not_overwrite_manual_job_title(db_session: Session) -> None:
    """系统内已维护的岗位（考核分组）不能被飞书同步覆盖。"""
    dept = _dept(db_session)
    u = User(
        username="sync_u1",
        password_hash=hash_password("x"),
        real_name="王峰",
        is_active=True,
        department_id=dept.id,
        job_title="直播团队",  # 系统内按《团队KPI考核表》维护的考核分组
        feishu_open_id="ou_wangfeng",
        employment_status="正式",
    )
    db_session.add(u)
    db_session.commit()

    res = FeishuSyncResult()
    # 飞书里这个人是「直播运营」甚至没填岗位
    _upsert_employee(db_session, item=_item("ou_wangfeng", "王峰", "直播运营"), department=dept, employee_role=None, result=res)
    db_session.commit()
    assert u.job_title == "直播团队", "系统内岗位被飞书覆盖了（考核匹配会因此失效）"

    res2 = FeishuSyncResult()
    _upsert_employee(db_session, item=_item("ou_wangfeng", "王峰", None), department=dept, employee_role=None, result=res2)
    db_session.commit()
    assert u.job_title == "直播团队", "飞书岗位为空时被清空了"


def test_sync_fills_empty_job_title(db_session: Session) -> None:
    """系统内岗位为空时，飞书的值可以补上（新人首次同步）。"""
    dept = _dept(db_session)
    u = User(
        username="sync_u2",
        password_hash=hash_password("x"),
        real_name="新人",
        is_active=True,
        department_id=dept.id,
        job_title=None,
        feishu_open_id="ou_newbie",
        employment_status="正式",
    )
    db_session.add(u)
    db_session.commit()

    res = FeishuSyncResult()
    _upsert_employee(db_session, item=_item("ou_newbie", "新人", "拍摄剪辑"), department=dept, employee_role=None, result=res)
    db_session.commit()
    assert u.job_title == "拍摄剪辑"
