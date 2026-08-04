"""飞书考勤事实同步与汇总。"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.employee_hr import FeishuAttendanceDaily
from app.models.user import User
from app.services.feishu_auth import FeishuAuthError
from app.services.feishu_client import FeishuClient, get_feishu_client
from app.services.sync_state import SYNC_KEY_ATTENDANCE, upsert_sync_state

# 飞书 check_result → 本地展示状态
_RESULT_MAP = {
    "Normal": "正常",
    "Late": "迟到",
    "SeriousLate": "迟到",
    "Early": "早退",
    "Lack": "缺卡",
    "NoNeedCheck": "休息日",
    "SystemCheck": "正常",
    "Todo": "异常",
    "None": "异常",
    "Invalid": "异常",
}

_EXCEPTION_STATUSES = {"迟到", "早退", "缺卡", "异常"}
_LEAVE_STATUSES = {"请假"}
_OUT_STATUSES = {"外出"}
_PRESENT_STATUSES = {"正常", "迟到", "早退"}


@dataclass
class AttendanceSyncResult:
    users_synced: int = 0
    days_upserted: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "users_synced": self.users_synced,
            "days_upserted": self.days_upserted,
            "warnings": self.warnings,
        }


def _parse_month(month: Optional[str]) -> tuple[date, date, str]:
    if month:
        try:
            year_s, month_s = month.split("-", 1)
            year, mon = int(year_s), int(month_s)
            if mon < 1 or mon > 12:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="month 格式应为 YYYY-MM") from exc
    else:
        today = date.today()
        year, mon = today.year, today.month
    last = monthrange(year, mon)[1]
    start = date(year, mon, 1)
    end = date(year, mon, last)
    return start, end, f"{year:04d}-{mon:02d}"


def _ymd(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day


def _parse_ymd(value: int | str) -> date | None:
    try:
        raw = int(value)
        return date(raw // 10000, (raw % 10000) // 100, raw % 100)
    except (TypeError, ValueError):
        return None


def _ts_to_time(ts: int | str | None) -> time | None:
    if ts is None or ts == "" or ts == 0:
        return None
    try:
        n = int(ts)
        if n > 10_000_000_000:
            n = n // 1000
        return datetime.fromtimestamp(n, tz=timezone.utc).astimezone().time().replace(microsecond=0)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def map_task_status(task: dict) -> tuple[str, str | None]:
    """从 user_task 映射本地状态与原始结果码。"""
    records = task.get("records") or []
    results: list[str] = []
    for rec in records:
        for key in ("check_in_result", "check_out_result"):
            val = rec.get(key)
            if val:
                results.append(str(val))
        for flow_key in ("check_in_record", "check_out_record"):
            flow = rec.get(flow_key) or {}
            if flow.get("check_result"):
                results.append(str(flow["check_result"]))

    if not results:
        # 无记录且无班次时视作休息日
        if not task.get("shift_id") or str(task.get("shift_id")) in ("0", ""):
            return "休息日", None
        return "异常", None

    # 请假/外出：飞书结果里偶发字段，兜底看 result 文案
    joined = ",".join(results).lower()
    if "leave" in joined or "请假" in joined:
        return "请假", results[0]
    if "out" in joined or "外出" in joined or "trip" in joined:
        return "外出", results[0]

    priority = ["Lack", "SeriousLate", "Late", "Early", "Todo", "Invalid", "None", "Normal", "SystemCheck", "NoNeedCheck"]
    picked = None
    for code in priority:
        if code in results:
            picked = code
            break
    if not picked:
        picked = results[0]
    return _RESULT_MAP.get(picked, "异常"), picked


def extract_punches(task: dict) -> tuple[time | None, time | None]:
    first: time | None = None
    last: time | None = None
    for rec in task.get("records") or []:
        in_flow = rec.get("check_in_record") or {}
        out_flow = rec.get("check_out_record") or {}
        in_t = _ts_to_time(in_flow.get("check_time") or rec.get("check_in_time"))
        out_t = _ts_to_time(out_flow.get("check_time") or rec.get("check_out_time"))
        if in_t and (first is None or in_t < first):
            first = in_t
        if out_t and (last is None or out_t > last):
            last = out_t
        if in_t and (last is None or in_t > last):
            last = in_t
    return first, last


def attendance_identity(user: User) -> tuple[str, str] | None:
    """返回 (employee_type, id)。优先 employee_id。"""
    if user.feishu_user_id:
        return "employee_id", user.feishu_user_id
    if user.employee_no:
        return "employee_no", user.employee_no
    return None


async def sync_feishu_attendance(
    db: Session,
    *,
    user_id: Optional[int] = None,
    month: Optional[str] = None,
    settings: Settings | None = None,
    client: FeishuClient | None = None,
) -> AttendanceSyncResult:
    start, end, month_label = _parse_month(month)
    cfg = settings or get_settings()
    own_client = client is None
    api = client or get_feishu_client(cfg)
    result = AttendanceSyncResult()

    q = db.query(User).filter(User.is_active.is_(True))
    if user_id:
        q = q.filter(User.id == user_id)
    users = q.all()

    if own_client:
        await api.__aenter__()
    try:
        upsert_sync_state(db, SYNC_KEY_ATTENDANCE, status="pending")
        db.commit()

        # 按 identity type 分组批量拉取
        by_type: dict[str, list[User]] = {"employee_id": [], "employee_no": []}
        for u in users:
            ident = attendance_identity(u)
            if not ident:
                result.warnings.append(
                    f"用户 #{u.id} 未绑定飞书 user_id/工号，请先同步通讯录"
                )
                continue
            emp_type, _ = ident
            by_type[emp_type].append(u)

        # 分段：飞书跨度不能超过 30 天
        windows: list[tuple[date, date]] = []
        cursor = start
        while cursor <= end:
            chunk_end = min(date.fromordinal(cursor.toordinal() + 29), end)
            windows.append((cursor, chunk_end))
            cursor = date.fromordinal(chunk_end.toordinal() + 1)

        for emp_type, group in by_type.items():
            if not group:
                continue
            # 每次最多 50 人
            for i in range(0, len(group), 50):
                batch = group[i : i + 50]
                id_map = {attendance_identity(u)[1]: u for u in batch if attendance_identity(u)}
                for win_start, win_end in windows:
                    try:
                        tasks = await api.query_user_tasks(
                            user_ids=list(id_map.keys()),
                            check_date_from=_ymd(win_start),
                            check_date_to=_ymd(win_end),
                            employee_type=emp_type,
                        )
                    except FeishuAuthError as exc:
                        result.warnings.append(f"拉取考勤失败 ({emp_type}): {exc}")
                        continue
                    for task in tasks:
                        uid = str(task.get("user_id") or "")
                        user = id_map.get(uid)
                        if not user:
                            continue
                        work_date = _parse_ymd(task.get("day") or task.get("date") or 0)
                        if not work_date or work_date < start or work_date > end:
                            continue
                        if work_date < win_start or work_date > win_end:
                            continue
                        status_label, raw = map_task_status(task)
                        first, last = extract_punches(task)
                        source = "日历规则" if status_label == "休息日" else "飞书同步"
                        row = (
                            db.query(FeishuAttendanceDaily)
                            .filter(
                                FeishuAttendanceDaily.user_id == user.id,
                                FeishuAttendanceDaily.work_date == work_date,
                            )
                            .first()
                        )
                        if not row:
                            row = FeishuAttendanceDaily(
                                user_id=user.id, work_date=work_date, status=status_label
                            )
                            db.add(row)
                        row.status = status_label
                        row.first_punch = first
                        row.last_punch = last
                        row.source = source
                        row.raw_result = raw
                        result.days_upserted += 1
                        db.flush()
                result.users_synced += len(batch)

        upsert_sync_state(
            db,
            SYNC_KEY_ATTENDANCE,
            status="ok" if not any("失败" in w for w in result.warnings) else "error",
            last_error="; ".join(result.warnings[:3]) if result.warnings else None,
            meta={"month": month_label, **result.as_dict()},
            success=True,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        upsert_sync_state(db, SYNC_KEY_ATTENDANCE, status="error", last_error=str(exc))
        db.commit()
        raise
    finally:
        if own_client:
            await api.__aexit__(None, None, None)


def get_attendance_summary(db: Session, user_id: int, month: Optional[str] = None) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="员工不存在")
    start, end, month_label = _parse_month(month)
    rows = (
        db.query(FeishuAttendanceDaily)
        .filter(
            FeishuAttendanceDaily.user_id == user_id,
            FeishuAttendanceDaily.work_date >= start,
            FeishuAttendanceDaily.work_date <= end,
        )
        .order_by(FeishuAttendanceDaily.work_date.desc())
        .all()
    )
    expected = sum(1 for r in rows if r.status != "休息日")
    actual = sum(1 for r in rows if r.status in _PRESENT_STATUSES)
    leave_days = sum(1 for r in rows if r.status in _LEAVE_STATUSES)
    out_days = sum(1 for r in rows if r.status in _OUT_STATUSES)
    exception_pending = sum(1 for r in rows if r.status in _EXCEPTION_STATUSES)
    today = date.today()
    today_row = next((r for r in rows if r.work_date == today), None)
    return {
        "month": month_label,
        "expected_days": expected,
        "actual_days": actual,
        "leave_days": leave_days,
        "out_days": out_days,
        "exception_pending": exception_pending,
        "today_status": today_row.status if today_row else None,
        "days": [
            {
                "work_date": r.work_date,
                "status": r.status,
                "first_punch": r.first_punch,
                "last_punch": r.last_punch,
                "source": r.source,
            }
            for r in rows
        ],
    }


def today_status_for_user(db: Session, user_id: int) -> Optional[str]:
    today = date.today()
    row = (
        db.query(FeishuAttendanceDaily)
        .filter(
            FeishuAttendanceDaily.user_id == user_id,
            FeishuAttendanceDaily.work_date == today,
        )
        .first()
    )
    return row.status if row else None
