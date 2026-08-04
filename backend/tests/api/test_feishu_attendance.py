"""飞书考勤同步与状态映射单测。"""
from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.services.feishu_attendance import (
    attendance_identity,
    get_attendance_summary,
    map_task_status,
    sync_feishu_attendance,
)
from app.services.feishu_auth import FeishuAuthError


def test_map_task_status_normal_and_late() -> None:
    status, raw = map_task_status(
        {
            "shift_id": "1",
            "records": [{"check_in_result": "Late", "check_out_result": "Normal"}],
        }
    )
    assert status == "迟到"
    assert raw == "Late"

    status2, _ = map_task_status({"shift_id": "0", "records": []})
    assert status2 == "休息日"


def test_attendance_identity_prefers_user_id(db_session: Session) -> None:
    user = User(
        username="u1",
        password_hash=hash_password("x"),
        feishu_user_id="uid_1",
        employee_no="YG-1",
        is_active=True,
    )
    assert attendance_identity(user) == ("employee_id", "uid_1")
    user.feishu_user_id = None
    assert attendance_identity(user) == ("employee_no", "YG-1")
    user.employee_no = None
    assert attendance_identity(user) is None


class FakeAttendanceClient:
    async def query_user_tasks(self, *, user_ids, check_date_from, check_date_to, employee_type="employee_id"):
        _ = employee_type
        today = date.today()
        day = today.year * 10000 + today.month * 100 + today.day
        if day < int(check_date_from) or day > int(check_date_to):
            return []
        return [
            {
                "user_id": user_ids[0],
                "day": day,
                "shift_id": "1",
                "records": [
                    {
                        "check_in_result": "Normal",
                        "check_out_result": "Normal",
                        "check_in_record": {"check_time": 1719288000},
                        "check_out_record": {"check_time": 1719321600},
                    }
                ],
            }
        ]


def test_sync_attendance_upserts_daily(db_session: Session) -> None:
    user = User(
        username="att_user",
        password_hash=hash_password("x"),
        real_name="考勤员",
        feishu_user_id="uid_att",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    month = f"{date.today().year:04d}-{date.today().month:02d}"
    result = asyncio.run(
        sync_feishu_attendance(
            db_session,
            user_id=user.id,
            month=month,
            client=FakeAttendanceClient(),  # type: ignore[arg-type]
        )
    )
    assert result.days_upserted >= 1
    summary = get_attendance_summary(db_session, user.id, month=month)
    assert summary["actual_days"] >= 1
    assert summary["today_status"] == "正常"


def test_sync_attendance_warns_when_unbound(db_session: Session) -> None:
    user = User(
        username="no_bind",
        password_hash=hash_password("x"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    month = f"{date.today().year:04d}-{date.today().month:02d}"
    result = asyncio.run(
        sync_feishu_attendance(
            db_session,
            user_id=user.id,
            month=month,
            client=FakeAttendanceClient(),  # type: ignore[arg-type]
        )
    )
    assert result.users_synced == 0
    assert any("未绑定" in w for w in result.warnings)


class FailingAttendanceClient:
    async def query_user_tasks(self, **kwargs):
        raise FeishuAuthError("auth no permission")


def test_sync_attendance_collects_api_errors(db_session: Session) -> None:
    user = User(
        username="fail_att",
        password_hash=hash_password("x"),
        feishu_user_id="uid_fail",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    month = f"{date.today().year:04d}-{date.today().month:02d}"
    result = asyncio.run(
        sync_feishu_attendance(
            db_session,
            user_id=user.id,
            month=month,
            client=FailingAttendanceClient(),  # type: ignore[arg-type]
        )
    )
    assert any("拉取考勤失败" in w for w in result.warnings)
