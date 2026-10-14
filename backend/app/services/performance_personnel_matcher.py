"""按模板范围匹配考核人员：资格、在岗天数、重复考核。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import and_, or_
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
from app.services.employment_status import EmploymentState, employment_state
from app.services.performance_data_source import cycle_window
from app.services.performance_template import require_published_for_launch

DEFAULT_MIN_DAYS = 15
# 只有这些考勤状态算缺勤；休息日、缺卡、迟到、异常都不扣在岗天数
ABSENT_ATTENDANCE = frozenset({"请假", "旷工"})
_APPROVED_LEAVE = ("approved", "已批准")


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


def _template_family(template: PerformanceTemplate) -> str:
    return template.family_code or template.code


@dataclass
class _PeopleContext:
    departments: dict[int, Department] = field(default_factory=dict)
    managers: dict[int, User] = field(default_factory=dict)
    assessments: dict[int, list[PerformanceAssessment]] = field(default_factory=dict)
    templates: dict[int, PerformanceTemplate] = field(default_factory=dict)
    leaves: dict[int, list[HrLeaveRequest]] = field(default_factory=dict)
    attendance: dict[int, list[FeishuAttendanceDaily]] = field(default_factory=dict)


def _load_context(
    db: Session,
    users: list[User],
    *,
    cycle_id: int,
    start: date,
    end: date,
    with_details: bool = True,
) -> _PeopleContext:
    """一次性批量加载候选人的部门、主管、本周期考核单、请假与考勤，避免逐人查库。"""
    ctx = _PeopleContext()
    if not users:
        return ctx
    user_ids = [u.id for u in users]

    manager_ids = {u.manager_id for u in users if u.manager_id}
    if manager_ids:
        ctx.managers = {m.id: m for m in db.query(User).filter(User.id.in_(manager_ids)).all()}

    for row in (
        db.query(PerformanceAssessment)
        .filter(
            PerformanceAssessment.cycle_id == cycle_id,
            PerformanceAssessment.user_id.in_(user_ids),
        )
        .order_by(PerformanceAssessment.id.asc())
        .all()
    ):
        ctx.assessments.setdefault(row.user_id, []).append(row)
    tpl_ids = {r.template_id for rows in ctx.assessments.values() for r in rows if r.template_id}
    if tpl_ids:
        ctx.templates = {
            t.id: t for t in db.query(PerformanceTemplate).filter(PerformanceTemplate.id.in_(tpl_ids)).all()
        }

    if not with_details:
        return ctx

    dept_ids = {u.department_id for u in users if u.department_id}
    if dept_ids:
        ctx.departments = {d.id: d for d in db.query(Department).filter(Department.id.in_(dept_ids)).all()}

    for leave in (
        db.query(HrLeaveRequest)
        .filter(
            HrLeaveRequest.employee_id.in_(user_ids),
            HrLeaveRequest.status.in_(_APPROVED_LEAVE),
            HrLeaveRequest.start_date <= end,
            HrLeaveRequest.end_date >= start,
        )
        .all()
    ):
        ctx.leaves.setdefault(leave.employee_id, []).append(leave)

    if end < date.today():
        for row in (
            db.query(FeishuAttendanceDaily)
            .filter(
                FeishuAttendanceDaily.user_id.in_(user_ids),
                FeishuAttendanceDaily.work_date >= start,
                FeishuAttendanceDaily.work_date <= end,
            )
            .all()
        ):
            ctx.attendance.setdefault(row.user_id, []).append(row)
    return ctx


def _is_long_leave(state: EmploymentState, leaves: list[HrLeaveRequest], start: date, end: date) -> bool:
    if state is EmploymentState.LONG_LEAVE:
        return True
    period_days = (end - start).days + 1
    for leave in leaves:
        overlap_start = max(leave.start_date, start)
        overlap_end = min(leave.end_date, end)
        days = (overlap_end - overlap_start).days + 1
        if days >= max(15, period_days // 2) or "长" in (leave.leave_type or ""):
            return True
    return False


def _leave_dates(leaves: list[HrLeaveRequest], start: date, end: date) -> set[date]:
    out: set[date] = set()
    for leave in leaves:
        day = max(leave.start_date, start)
        last = min(leave.end_date, end)
        while day <= last:
            out.add(day)
            day += timedelta(days=1)
    return out


def _days_in_period(
    user: User,
    start: date,
    end: date,
    *,
    leaves: Optional[list[HrLeaveRequest]] = None,
    attendance: Optional[list[FeishuAttendanceDaily]] = None,
) -> int:
    """在岗自然日 = 入职日与周期的交集。

    周期未结束时只按入职日估算；周期结束后再扣除已批准请假日，
    若该员工考勤已同步到周期最后一天，再扣除考勤里的请假/旷工日。
    """
    hire = user.hire_date or start
    effective_start = max(start, hire)
    if effective_start > end:
        return 0
    days = (end - effective_start).days + 1
    if end >= date.today():
        return days

    absent = {d for d in _leave_dates(leaves or [], start, end) if d >= effective_start}
    rows = attendance or []
    if rows and max(r.work_date for r in rows) >= end:
        absent |= {r.work_date for r in rows if r.status in ABSENT_ATTENDANCE and r.work_date >= effective_start}
    return max(0, days - len(absent))


def _split_assessments(
    rows: list[PerformanceAssessment],
    *,
    template: PerformanceTemplate,
    templates: dict[int, PerformanceTemplate],
) -> tuple[Optional[PerformanceAssessment], list[dict[str, Any]]]:
    """拆成「同模板/同系列且同类型的已有考核单」与「其它模板考核单（只提醒）」。"""
    family = _template_family(template)
    kind = template.assessment_kind or "monthly"
    existing: Optional[PerformanceAssessment] = None
    others: list[dict[str, Any]] = []
    for row in rows:
        other = templates.get(row.template_id) if row.template_id else None
        same_family = row.template_id == template.id or (
            other is not None and _template_family(other) == family
        )
        if same_family:
            if existing is None and row.assessment_kind == kind:
                existing = row
            continue
        others.append(
            {
                "assessment_id": row.id,
                "template_id": row.template_id,
                "template_name": other.name if other else None,
                "template_code": other.code if other else None,
                "assessment_kind": row.assessment_kind,
            }
        )
    return existing, others


def _resolve_template(db: Session, cycle: PerformanceCycle, template_id: int) -> PerformanceTemplate:
    template = require_published_for_launch(db, template_id, cycle=cycle)
    # 入职考核按「人 + 阶段」开案，不参与部门/岗位匹配，给出明确业务提示
    if (template.assessment_kind or "").strip() == "onboarding":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "KPI_ONBOARDING_NOT_MATCHABLE",
                "message": "入职考核模板按「人 + 阶段」开案，不通过部门/岗位匹配；请在入职阶段考核中开案",
            },
        )
    return template


def _scope_candidates(db: Session, template: PerformanceTemplate) -> tuple[list[dict[str, Any]], list[User]]:
    """模板适用范围内的人员（含下级部门；岗位留空 = 整部门）。"""
    scopes = (
        db.query(PerformanceTemplateScope)
        .filter(PerformanceTemplateScope.template_id == template.id)
        .all()
    )
    if not scopes:
        raise HTTPException(status_code=422, detail="模板未配置适用部门/岗位范围")

    dept_rows = db.query(Department.id, Department.parent_id, Department.name).all()
    names = {d_id: name for d_id, _, name in dept_rows}
    children: dict[Optional[int], list[int]] = {}
    for d_id, parent_id, _ in dept_rows:
        children.setdefault(parent_id, []).append(d_id)

    def descendants(root: int) -> list[int]:
        out, stack = [], [root]
        while stack:
            cur = stack.pop()
            out.append(cur)
            stack.extend(children.get(cur, []))
        return out

    scope_out: list[dict[str, Any]] = []
    conditions = []
    for scope in scopes:
        job = (scope.job_title or "").strip()
        scope_out.append(
            {
                "department_id": scope.department_id,
                "department_name": names.get(scope.department_id),
                "job_title": job or None,
            }
        )
        cond = User.department_id.in_(descendants(scope.department_id))
        conditions.append(and_(cond, User.job_title == job) if job else cond)

    users = db.query(User).filter(or_(*conditions)).order_by(User.id.asc()).all()
    return scope_out, users


def match_personnel(
    db: Session,
    *,
    cycle_id: int,
    template_id: int,
    extra_user_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    """按模板适用范围匹配人员。

    extra_user_ids：**手动添加的范围外人员**（部门/岗位不符），
    会以 match_status='excluded' / allowed_action='manual_include' 进入名单，
    发起时必须填写原因；离职/停用、无主管、本周期已有同模板考核的仍被 blocked。
    """
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
    if cycle is None:
        raise HTTPException(status_code=404, detail="考核周期不存在")
    template = _resolve_template(db, cycle, template_id)
    scope_out, candidates = _scope_candidates(db, template)

    start, end = cycle_window(cycle)
    policy = _policy(template)
    min_days = int(policy["min_days_in_period"])
    include_probation = bool(policy["include_probation"])

    # 手动添加的范围外人员（部门/岗位不符）也纳入候选，便于发起时按"手动纳入+原因"处理
    seen_ids = {u.id for u in candidates}
    extra_ids: set[int] = set()
    for uid in extra_user_ids or []:
        try:
            extra_ids.add(int(uid))
        except (TypeError, ValueError):
            continue
    out_of_scope_ids = extra_ids - seen_ids
    if out_of_scope_ids:
        candidates.extend(
            db.query(User).filter(User.id.in_(out_of_scope_ids)).order_by(User.id.asc()).all()
        )

    ctx = _load_context(db, candidates, cycle_id=cycle.id, start=start, end=end)

    people = []
    for user in candidates:
        dept = ctx.departments.get(user.department_id) if user.department_id else None
        manager = ctx.managers.get(user.manager_id) if user.manager_id else None
        state = employment_state(user.employment_status, is_active=bool(user.is_active))
        emp_type = "probation" if state is EmploymentState.PROBATION else "regular"
        leaves = ctx.leaves.get(user.id, [])
        days = _days_in_period(user, start, end, leaves=leaves, attendance=ctx.attendance.get(user.id))
        existing, other_assessments = _split_assessments(
            ctx.assessments.get(user.id, []), template=template, templates=ctx.templates
        )

        match_status = "matched"
        reason_code = "scope_and_policy_matched"
        reason = "部门、岗位及在岗条件均符合"
        allowed_action = "include_or_exclude"

        if existing is not None:
            match_status = "blocked"
            reason_code = "duplicate_assessment"
            reason = "本周期已存在相同模板考核"
            allowed_action = "none"
        elif manager is None:
            match_status = "blocked"
            reason_code = "missing_manager"
            reason = "缺少直属主管，不能生成无人处理的考核"
            allowed_action = "none"
        elif state is EmploymentState.RESIGNED:
            match_status = "excluded"
            reason_code = "inactive_employment"
            reason = "离职或停用人员不可纳入考核"
            allowed_action = "none"
        elif state is EmploymentState.PENDING:
            match_status = "excluded"
            reason_code = "inactive_employment"
            reason = "非在职状态"
            allowed_action = "manual_include"
        elif _is_long_leave(state, leaves, start, end):
            match_status = "excluded"
            reason_code = "long_leave"
            reason = "长期休假"
            allowed_action = "manual_include"
        elif state is EmploymentState.PROBATION and not include_probation:
            match_status = "excluded"
            reason_code = "probation"
            reason = "试用期不参加月度考核"
            allowed_action = "manual_include"
        elif days < min_days:
            match_status = "excluded"
            reason_code = "insufficient_days"
            reason = f"本月在岗{days}天，少于{min_days}天"
            allowed_action = "manual_include"

        # 手动添加的范围外人员：部门/岗位不符（无其它阻断原因时），需填原因后纳入
        if user.id in out_of_scope_ids and match_status == "matched":
            match_status = "excluded"
            reason_code = "out_of_scope"
            reason = "不在模板适用范围内（部门/岗位不符），属手动添加"
            allowed_action = "manual_include"

        warnings: list[dict[str, Any]] = []
        if other_assessments and match_status != "blocked":
            names = "、".join(
                a["template_name"] or a["template_code"] or f"模板{a['template_id']}"
                for a in other_assessments
            )
            warnings.append(
                {
                    "code": "other_template_assessment",
                    "message": f"本周期已有其它模板考核：{names}",
                    "assessments": other_assessments,
                }
            )

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
                "is_active": bool(user.is_active),
                "days_in_period": days,
                "match_status": match_status,
                "reason_code": reason_code,
                "reason": reason,
                "allowed_action": allowed_action,
                "existing_assessment_id": existing.id if existing else None,
                "warnings": warnings,
                "has_other_template_assessment": bool(warnings),
            }
        )

    summary = {
        "matched": sum(1 for p in people if p["match_status"] == "matched"),
        "excluded": sum(1 for p in people if p["match_status"] == "excluded"),
        "blocked": sum(1 for p in people if p["match_status"] == "blocked"),
        "warned": sum(1 for p in people if p["has_other_template_assessment"]),
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
        "in_scope_user_ids": sorted(seen_ids),
    }


def template_all_blocked(db: Session, *, cycle_id: int, template_id: int) -> bool:
    """范围内有人，且每个人都是阻断（重复考核或缺主管）时为 True。无人或未发布则 False。

    只判断阻断条件，不计算在岗天数、请假与提醒，供模板列表批量调用。
    """
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
    if cycle is None:
        return False
    try:
        template = _resolve_template(db, cycle, template_id)
        _, candidates = _scope_candidates(db, template)
    except HTTPException:
        return False
    if not candidates:
        return False
    start, end = cycle_window(cycle)
    ctx = _load_context(db, candidates, cycle_id=cycle.id, start=start, end=end, with_details=False)
    for user in candidates:
        if not user.manager_id or user.manager_id not in ctx.managers:
            continue
        existing, _ = _split_assessments(
            ctx.assessments.get(user.id, []), template=template, templates=ctx.templates
        )
        if existing is None:
            return False
    return True


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
