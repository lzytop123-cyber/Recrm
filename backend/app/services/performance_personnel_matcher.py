"""按模板范围匹配考核人员：资格、在岗天数、重复考核。"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.employee_hr import FeishuAttendanceDaily
from app.models.hr import HrLeaveRequest
from app.models.performance import (
    PerformanceAssessment,
    PerformanceCycle,
    PerformanceTemplate,
    PerformanceTemplateScope,
)
from app.models.user import User
from app.services.performance_data_source import cycle_window
from app.services.performance_template import require_published_for_launch

DEFAULT_MIN_DAYS = 15
ABSENT_ATTENDANCE = {"请假", "休息日", "缺卡"}


def _policy(template: PerformanceTemplate) -> dict[str, Any]:
    raw = template.eligibility_policy_json
    if not raw:
        return {"min_days_in_period": DEFAULT_MIN_DAYS, "include_probation": False}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"min_days_in_period": DEFAULT_MIN_DAYS, "include_probation": False}
    if not isinstance(data, dict):
        return {"min_days_in_period": DEFAULT_MIN_DAYS, "include_probation": False}
    return {
        "min_days_in_period": int(data.get("min_days_in_period") or data.get("minDays") or DEFAULT_MIN_DAYS),
        "include_probation": bool(data.get("include_probation") or data.get("includeProbation") or False),
    }


def _employment_type(user: User) -> str:
    status = (user.employment_status or "").strip()
    if status in ("试用", "probation", "trial"):
        return "probation"
    if status in ("正式", "regular", "active", ""):
        return "regular"
    if "试用" in status:
        return "probation"
    return "regular"


def _is_inactive(user: User) -> bool:
    if not user.is_active:
        return True
    status = (user.employment_status or "").strip()
    return status in ("离职", "待入职", "resigned", "inactive")


def _is_long_leave(db: Session, user: User, start: date, end: date) -> bool:
    status = (user.employment_status or "").strip()
    if status in ("长期休假", "long_leave") or "休假" in status:
        return True
    leaves = (
        db.query(HrLeaveRequest)
        .filter(
            HrLeaveRequest.employee_id == user.id,
            HrLeaveRequest.status.in_(("approved", "已批准")),
            HrLeaveRequest.start_date <= end,
            HrLeaveRequest.end_date >= start,
        )
        .all()
    )
    period_days = (end - start).days + 1
    for leave in leaves:
        overlap_start = max(leave.start_date, start)
        overlap_end = min(leave.end_date, end)
        days = (overlap_end - overlap_start).days + 1
        if days >= max(15, period_days // 2) or (leave.leave_type or "").find("长") >= 0:
            return True
    return False


def _days_in_period(db: Session, user: User, start: date, end: date) -> int:
    hire = user.hire_date or start
    effective_start = max(start, hire)
    estimated = 0 if effective_start > end else (end - effective_start).days + 1

    rows = (
        db.query(FeishuAttendanceDaily)
        .filter(
            FeishuAttendanceDaily.user_id == user.id,
            FeishuAttendanceDaily.work_date >= start,
            FeishuAttendanceDaily.work_date <= end,
        )
        .all()
    )
    if not rows:
        # 无考勤事实时：按入职日与周期交集估算在岗自然日
        return estimated

    present = sum(1 for r in rows if r.status not in ABSENT_ATTENDANCE)
    period_days = (end - start).days + 1
    # 只同步了少量天且出勤为 0：视为考勤未齐，回退估算，避免「两条休息日 → 整月 0 天」
    if present == 0 and len(rows) < max(5, period_days // 3):
        return estimated
    return present


def _existing_assessment(
    db: Session,
    *,
    cycle_id: int,
    user_id: int,
    template: PerformanceTemplate,
) -> Optional[PerformanceAssessment]:
    family = template.family_code or template.code
    kind = template.assessment_kind or "monthly"
    q = (
        db.query(PerformanceAssessment)
        .filter(
            PerformanceAssessment.cycle_id == cycle_id,
            PerformanceAssessment.user_id == user_id,
            PerformanceAssessment.assessment_kind == kind,
        )
    )
    for row in q.all():
        if row.template_id == template.id:
            return row
        if row.template_id:
            other = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == row.template_id).first()
            if other and (other.family_code or other.code) == family:
                return row
    return None


def match_personnel(db: Session, *, cycle_id: int, template_id: int) -> dict[str, Any]:
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
    if cycle is None:
        raise HTTPException(status_code=404, detail="考核周期不存在")
    template = require_published_for_launch(db, template_id, cycle=cycle)
    scopes = (
        db.query(PerformanceTemplateScope)
        .filter(PerformanceTemplateScope.template_id == template.id)
        .all()
    )
    if not scopes:
        raise HTTPException(status_code=422, detail="模板未配置适用部门/岗位范围")

    start, end = cycle_window(cycle)
    policy = _policy(template)
    min_days = int(policy["min_days_in_period"])
    include_probation = bool(policy["include_probation"])

    scope_out = []
    candidates: list[User] = []
    seen_ids: set[int] = set()
    for scope in scopes:
        dept = db.query(Department).filter(Department.id == scope.department_id).first()
        scope_out.append(
            {
                "department_id": scope.department_id,
                "department_name": dept.name if dept else None,
                "job_title": scope.job_title,
            }
        )
        users = (
            db.query(User)
            .filter(
                User.department_id == scope.department_id,
                User.job_title == scope.job_title,
            )
            .all()
        )
        for u in users:
            if u.id not in seen_ids:
                seen_ids.add(u.id)
                candidates.append(u)

    people = []
    for user in candidates:
        dept = db.query(Department).filter(Department.id == user.department_id).first() if user.department_id else None
        manager = db.query(User).filter(User.id == user.manager_id).first() if user.manager_id else None
        days = _days_in_period(db, user, start, end)
        emp_type = _employment_type(user)
        existing = _existing_assessment(db, cycle_id=cycle.id, user_id=user.id, template=template)

        match_status = "matched"
        reason_code = "scope_and_policy_matched"
        reason = "部门、岗位及在岗条件均符合"
        allowed_action = "include_or_exclude"

        if existing is not None:
            match_status = "blocked"
            reason_code = "duplicate_assessment"
            reason = "本周期已存在相同模板考核"
            allowed_action = "none"
        elif not user.manager_id or manager is None:
            match_status = "blocked"
            reason_code = "missing_manager"
            reason = "缺少直属主管，不能生成无人处理的考核"
            allowed_action = "none"
        elif _is_inactive(user):
            match_status = "excluded"
            reason_code = "inactive_employment"
            status = (user.employment_status or "").strip()
            # 离职/停用不可手动纳入；待入职等仍允许手动纳入（由发起接口最终校验）
            if (not user.is_active) or status in ("离职", "resigned", "inactive"):
                reason = "离职或停用人员不可纳入考核"
                allowed_action = "none"
            else:
                reason = "非在职状态"
                allowed_action = "manual_include"
        elif _is_long_leave(db, user, start, end):
            match_status = "excluded"
            reason_code = "long_leave"
            reason = "长期休假"
            allowed_action = "manual_include"
        elif emp_type == "probation" and not include_probation:
            match_status = "excluded"
            reason_code = "probation"
            reason = "试用期不参加月度考核"
            allowed_action = "manual_include"
        elif days < min_days:
            match_status = "excluded"
            reason_code = "insufficient_days"
            reason = f"本月在岗{days}天，少于{min_days}天"
            allowed_action = "manual_include"

        people.append(
            {
                "user_id": user.id,
                "name": user.real_name or user.username,
                "department_id": user.department_id,
                "department_name": dept.name if dept else None,
                "job_title": user.job_title,
                "manager_id": user.manager_id,
                "manager_name": (manager.real_name or manager.username) if manager else None,
                "employment_type": emp_type,
                "employment_status": user.employment_status,
                "days_in_period": days,
                "match_status": match_status,
                "reason_code": reason_code,
                "reason": reason,
                "allowed_action": allowed_action,
                "existing_assessment_id": existing.id if existing else None,
            }
        )

    summary = {
        "matched": sum(1 for p in people if p["match_status"] == "matched"),
        "excluded": sum(1 for p in people if p["match_status"] == "excluded"),
        "blocked": sum(1 for p in people if p["match_status"] == "blocked"),
    }
    return {
        "template": {
            "id": template.id,
            "name": template.name,
            "version": template.version,
            "code": template.code,
            "family_code": template.family_code,
        },
        "cycle": {"id": cycle.id, "period_label": cycle.period_label},
        "scope": scope_out,
        "policy": policy,
        "summary": summary,
        "people": people,
    }


def template_all_blocked(db: Session, *, cycle_id: int, template_id: int) -> bool:
    """范围内有人，且每个人都是阻断（重复考核或缺主管）时为 True。无人或未发布则 False。"""
    try:
        data = match_personnel(db, cycle_id=cycle_id, template_id=template_id)
    except HTTPException:
        return False
    people = data["people"]
    return bool(people) and all(p["match_status"] == "blocked" for p in people)


def seed_attendance_days(db: Session, user_id: int, start: date, days: int, *, status: str = "正常") -> None:
    """测试辅助：写入在岗考勤日。"""
    for i in range(days):
        db.add(
            FeishuAttendanceDaily(
                user_id=user_id,
                work_date=start + timedelta(days=i),
                status=status,
                source="测试",
            )
        )
