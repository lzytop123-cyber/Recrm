"""考核批次进度看板与往期考核名单（只读查询）。"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.rbac import collect_permission_codes
from app.models.department import Department
from app.models.performance import (
    ASSESS_APPEAL_PENDING,
    ASSESS_COMPLETED,
    ASSESS_EMPLOYEE_CONFIRM_PENDING,
    ASSESS_EMPLOYEE_PENDING,
    ASSESS_HR_REVIEW_PENDING,
    ASSESS_MANAGER_PENDING,
    PerformanceAssessment,
    PerformanceAssessmentBatch,
    PerformanceCycle,
    PerformanceTemplate,
    PerformanceTemplateScope,
)
from app.models.user import User


def _status_counts(rows: list[PerformanceAssessment]) -> dict[str, int]:
    counts = {
        "total": len(rows),
        "pending_employee": 0,
        "pending_manager": 0,
        "pending_hr_review": 0,
        "pending_confirm": 0,
        "appealing": 0,
        "completed": 0,
        "other": 0,
    }
    for r in rows:
        s = r.status
        if s == ASSESS_EMPLOYEE_PENDING:
            counts["pending_employee"] += 1
        elif s == ASSESS_MANAGER_PENDING:
            counts["pending_manager"] += 1
        elif s == ASSESS_HR_REVIEW_PENDING:
            counts["pending_hr_review"] += 1
        elif s == ASSESS_EMPLOYEE_CONFIRM_PENDING:
            counts["pending_confirm"] += 1
        elif s == ASSESS_APPEAL_PENDING:
            counts["appealing"] += 1
        elif s == ASSESS_COMPLETED:
            counts["completed"] += 1
        else:
            counts["other"] += 1
    return counts


def _template_scope_label(db: Session, template_id: int) -> dict[str, Any]:
    scope = (
        db.query(PerformanceTemplateScope)
        .filter(PerformanceTemplateScope.template_id == template_id)
        .order_by(PerformanceTemplateScope.id.asc())
        .first()
    )
    if not scope:
        return {"department_id": None, "department_name": None, "job_title": None}
    dept = db.query(Department).filter(Department.id == scope.department_id).first()
    return {
        "department_id": scope.department_id,
        "department_name": dept.name if dept else None,
        "job_title": scope.job_title,
    }


def _person_snapshot(assessment: PerformanceAssessment) -> dict[str, Any]:
    try:
        data = json.loads(assessment.person_snapshot_json or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _people_out(db: Session, assessments: list[PerformanceAssessment]) -> list[dict[str, Any]]:
    """批次人员，含发起时的直属主管。"""
    snaps = [_person_snapshot(a) for a in assessments]
    missing = {
        a.manager_id or s.get("manager_id")
        for a, s in zip(assessments, snaps)
        if (a.manager_id or s.get("manager_id")) and not s.get("manager_name")
    }
    managers = (
        {u.id: u for u in db.query(User).filter(User.id.in_(missing)).all()} if missing else {}
    )
    people = []
    for assessment, snap in zip(assessments, snaps):
        manager_id = assessment.manager_id or snap.get("manager_id")
        manager_name = snap.get("manager_name")
        if manager_id and not manager_name and manager_id in managers:
            manager = managers[manager_id]
            manager_name = manager.real_name or manager.username
        people.append(
            {
                "assessment_id": assessment.id,
                "user_id": assessment.user_id,
                "name": snap.get("name"),
                "department_name": snap.get("department_name"),
                "job_title": snap.get("job_title"),
                "manager_id": manager_id,
                "manager_name": manager_name,
                "status": "hr_review" if assessment.status == ASSESS_HR_REVIEW_PENDING else assessment.status,
                "current_handler_type": assessment.current_handler_type,
                "current_handler_id": assessment.current_handler_id,
            }
        )
    return people


def batch_progress_out(db: Session, batch: PerformanceAssessmentBatch) -> dict[str, Any]:
    assessments = (
        db.query(PerformanceAssessment)
        .filter(PerformanceAssessment.batch_id == batch.id)
        .order_by(PerformanceAssessment.id.asc())
        .all()
    )
    tpl = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == batch.template_id).first()
    scope = _template_scope_label(db, batch.template_id)
    # 若范围缺失，回退人员快照部门
    if not scope["department_name"] and assessments:
        try:
            snap = json.loads(assessments[0].person_snapshot_json or "{}")
            scope = {
                "department_id": snap.get("department_id"),
                "department_name": snap.get("department_name"),
                "job_title": snap.get("job_title"),
            }
        except json.JSONDecodeError:
            pass
    counts = _status_counts(assessments)
    people = _people_out(db, assessments)
    manager_ids = {p["manager_id"] for p in people if p["manager_id"]}
    manager_id = next(iter(manager_ids)) if len(manager_ids) == 1 else None
    manager_name = next((p["manager_name"] for p in people if p["manager_id"] == manager_id), None) if manager_id else None
    base = batch_out(db, batch, assessment_ids=[a.id for a in assessments])
    base.update(
        {
            "template_name": tpl.name if tpl else None,
            "template_version": tpl.version if tpl else None,
            "department_id": scope["department_id"],
            "department_name": scope["department_name"],
            "job_title": scope["job_title"],
            "manager_id": manager_id,
            "manager_name": manager_name,
            "people": people,
            **counts,
        }
    )
    return base


def current_month_cycle_id(db: Session) -> Optional[int]:
    """当前自然月对应的周期。同月有多条时取 id 最大的一条。"""
    from app.services.performance_data_source import _parse_year_month

    today = date.today()
    target = (today.year, today.month)
    rows = db.query(PerformanceCycle).order_by(PerformanceCycle.id.desc()).all()
    for row in rows:
        if _parse_year_month(row.period_label or "") == target:
            return row.id
    return None


def resolve_list_cycle_id(db: Session, cycle_id: Optional[int] = None) -> Optional[int]:
    """列表默认周期：优先本月；没有本月时回退到最近一条。"""
    if cycle_id is not None:
        return cycle_id
    return current_month_cycle_id(db) or (
        db.query(PerformanceCycle.id).order_by(PerformanceCycle.id.desc()).limit(1).scalar()
    )


def _sees_all_batches(user: User) -> bool:
    if "admin" in {r.code for r in (user.roles or [])}:
        return True
    codes = collect_permission_codes(user)
    return "*" in codes or "kpi:template:manage" in codes


def _visible_batch_ids(db: Session, user: User, cycle_id: Optional[int] = None) -> Optional[set[int]]:
    """模板管理员看全部；其他人只看本人或直属下属所在批次。"""
    if _sees_all_batches(user):
        return None
    subordinate_ids = db.query(User.id).filter(User.manager_id == user.id)
    q = db.query(PerformanceAssessment.batch_id).filter(
        PerformanceAssessment.batch_id.isnot(None),
        (PerformanceAssessment.user_id == user.id) | (PerformanceAssessment.user_id.in_(subordinate_ids)),
    )
    if cycle_id is not None:
        q = q.filter(PerformanceAssessment.cycle_id == cycle_id)
    return {row[0] for row in q.all() if row[0] is not None}


def list_cycle_batch_progress(db: Session, cycle_id: int, user: Optional[User] = None) -> dict[str, Any]:
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == cycle_id).first()
    if cycle is None:
        raise HTTPException(status_code=404, detail="考核周期不存在")
    batches = (
        db.query(PerformanceAssessmentBatch)
        .filter(PerformanceAssessmentBatch.cycle_id == cycle_id)
        .order_by(PerformanceAssessmentBatch.id.asc())
        .all()
    )
    if user is not None:
        visible = _visible_batch_ids(db, user, cycle_id)
        if visible is not None:
            batches = [b for b in batches if b.id in visible]
    rows = [batch_progress_out(db, b) for b in batches]
    totals = {
        "batch_count": len(rows),
        "total": sum(r["total"] for r in rows),
        "pending_employee": sum(r["pending_employee"] for r in rows),
        "pending_manager": sum(r["pending_manager"] for r in rows),
        "pending_hr_review": sum(r["pending_hr_review"] for r in rows),
        "pending_confirm": sum(r["pending_confirm"] for r in rows),
        "appealing": sum(r["appealing"] for r in rows),
        "completed": sum(r["completed"] for r in rows),
    }
    # 按部门名聚合（同名多模板 / 多 department_id 合并成一行）
    by_dept: dict[str, dict[str, Any]] = {}
    for r in rows:
        name = (r.get("department_name") or "").strip() or "未分组"
        key = name
        if key not in by_dept:
            by_dept[key] = {
                "department_id": r.get("department_id"),
                "department_name": name,
                "batch_ids": [],
                "template_names": [],
                "total": 0,
                "pending_employee": 0,
                "pending_manager": 0,
                "pending_hr_review": 0,
                "pending_confirm": 0,
                "appealing": 0,
                "completed": 0,
            }
        d = by_dept[key]
        if d.get("department_id") is None and r.get("department_id") is not None:
            d["department_id"] = r.get("department_id")
        d["batch_ids"].append(r["id"])
        if r.get("template_name"):
            d["template_names"].append(r["template_name"])
        for k in (
            "total",
            "pending_employee",
            "pending_manager",
            "pending_hr_review",
            "pending_confirm",
            "appealing",
            "completed",
        ):
            d[k] += r[k]
    return {
        "cycle_id": cycle_id,
        "period_label": cycle.period_label,
        "hr_review_required": all(bool(r.get("hr_review_required")) for r in rows) if rows else False,
        "batches": rows,
        "departments": list(by_dept.values()),
        "totals": totals,
    }


def _history_score(assessment: PerformanceAssessment) -> Optional[Decimal]:
    if assessment.total_points is not None:
        return Decimal(assessment.total_points)
    if assessment.final_score is not None:
        return Decimal(assessment.final_score)
    return None


def _history_person(assessment: PerformanceAssessment) -> dict[str, Any]:
    try:
        data = json.loads(assessment.person_snapshot_json or "{}")
    except json.JSONDecodeError:
        data = {}
    return data if isinstance(data, dict) else {}


def list_assessment_history(
    db: Session,
    user: User,
    *,
    cycle_id: Optional[int] = None,
    department: Optional[str] = None,
    q: Optional[str] = None,
    sort: str = "default",
) -> dict[str, Any]:
    """往期考核名单：只含已完成考核单。HR 看全部；其他人看自己以及自己当考核主管的下属。"""
    from app.services.performance_data_source import _parse_year_month

    query = db.query(PerformanceAssessment).filter(
        PerformanceAssessment.status == ASSESS_COMPLETED
    )
    if not _sees_all_batches(user):
        query = query.filter(
            (PerformanceAssessment.user_id == user.id)
            | (PerformanceAssessment.manager_id == user.id)
        )
    visible = query.all()
    if _sees_all_batches(user):
        scope = "all"
    elif any(row.manager_id == user.id and row.user_id != user.id for row in visible):
        scope = "manager"
    else:
        scope = "self"

    cycle_ids = list({row.cycle_id for row in visible})
    cycles = {
        row.id: row
        for row in db.query(PerformanceCycle).filter(PerformanceCycle.id.in_(cycle_ids or [0])).all()
    }

    def _cycle_sort_key(cid: int) -> tuple:
        label = cycles[cid].period_label if cid in cycles else ""
        ym = _parse_year_month(label or "")
        # 新→旧；解析不出的排后面，再用 id 兜底
        return (0 if ym else 1, -(ym[0] if ym else 0), -(ym[1] if ym else 0), -cid)

    cycle_ids.sort(key=_cycle_sort_key)
    periods = [
        {"cycle_id": cid, "period_label": cycles[cid].period_label if cid in cycles else None}
        for cid in cycle_ids
    ]
    selected = cycle_id if cycle_id is not None else (cycle_ids[0] if cycle_ids else None)
    if selected is not None and selected not in cycles and cycle_id is not None:
        found = db.query(PerformanceCycle).filter(PerformanceCycle.id == selected).first()
        if found is None:
            raise HTTPException(status_code=404, detail="考核周期不存在")
        cycles[selected] = found
    in_cycle = [row for row in visible if row.cycle_id == selected]
    departments = sorted({
        (_history_person(row).get("department_name") or "")
        for row in in_cycle
        if _history_person(row).get("department_name")
    })
    needle = (q or "").strip().lower()
    dept = (department or "").strip()
    filtered = []
    for row in in_cycle:
        person = _history_person(row)
        name = person.get("name") or ""
        job = person.get("job_title") or ""
        manager = person.get("manager_name") or ""
        department_name = person.get("department_name") or ""
        if dept and department_name != dept:
            continue
        if needle and needle not in f"{name} {job} {manager}".lower():
            continue
        filtered.append(row)

    # periods 已按新→旧排；当前项的下一条即上期
    previous_id = None
    if selected in cycle_ids:
        idx = cycle_ids.index(selected)
        if idx + 1 < len(cycle_ids):
            previous_id = cycle_ids[idx + 1]
    previous_scores = {
        row.user_id: _history_score(row)
        for row in visible
        if row.cycle_id == previous_id
    }

    def _sort_key(row: PerformanceAssessment):
        score = _history_score(row)
        if sort == "high":
            return (score is None, -(score or 0))
        if sort == "low":
            return (score is None, score or 0)
        return (0, row.id)

    filtered.sort(key=_sort_key)
    items = []
    for row in filtered:
        person = _history_person(row)
        score = _history_score(row)
        previous = previous_scores.get(row.user_id)
        delta = None if score is None or previous is None else (score - previous)
        items.append({
            "assessment_id": row.id,
            "user_id": row.user_id,
            "name": person.get("name"),
            "department_name": person.get("department_name"),
            "job_title": person.get("job_title"),
            "manager_id": row.manager_id,
            "manager_name": person.get("manager_name"),
            "score": None if score is None else str(score.quantize(Decimal("0.01"))),
            "status": row.status,
            "previous_score": None if previous is None else str(previous.quantize(Decimal("0.01"))),
            "score_delta": None if delta is None else str(delta.quantize(Decimal("0.01"))),
        })
    numbers = [Decimal(item["score"]) for item in items if item["score"] is not None]
    return {
        "cycle_id": selected,
        "period_label": cycles[selected].period_label if selected in cycles else None,
        "scope": scope,
        "periods": periods,
        "departments": departments,
        "stats": {
            "count": len(items),
            "average": None if not numbers else str((sum(numbers) / len(numbers)).quantize(Decimal("0.1"))),
            "max_score": None if not numbers else str(max(numbers).quantize(Decimal("0.01"))),
            "department_count": len({item["department_name"] for item in items if item["department_name"]}),
        },
        "rows": items,
    }


def get_batch_progress(db: Session, batch_id: int, user: Optional[User] = None) -> dict[str, Any]:
    batch = db.query(PerformanceAssessmentBatch).filter(PerformanceAssessmentBatch.id == batch_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="考核批次不存在")
    if user is not None:
        visible = _visible_batch_ids(db, user)
        if visible is not None and batch_id not in visible:
            raise HTTPException(status_code=403, detail="无权查看该考核批次")
    return batch_progress_out(db, batch)


def batch_out(
    db: Session,
    batch: PerformanceAssessmentBatch,
    *,
    idempotent: bool = False,
    assessment_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    if assessment_ids is None:
        assessment_ids = [
            r.id
            for r in db.query(PerformanceAssessment)
            .filter(PerformanceAssessment.batch_id == batch.id)
            .order_by(PerformanceAssessment.id.asc())
            .all()
        ]
    return {
        "id": batch.id,
        "cycle_id": batch.cycle_id,
        "template_id": batch.template_id,
        "status": batch.status,
        "hr_review_required": batch.hr_review_required,
        "idempotency_key": batch.idempotency_key,
        "employee_due_at": batch.employee_due_at.isoformat() if batch.employee_due_at else None,
        "manager_due_at": batch.manager_due_at.isoformat() if batch.manager_due_at else None,
        "hr_review_due_at": batch.hr_review_due_at.isoformat() if batch.hr_review_due_at else None,
        "confirm_due_at": batch.confirm_due_at.isoformat() if batch.confirm_due_at else None,
        "created_by": batch.created_by,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "assessment_ids": assessment_ids,
        "idempotent": idempotent,
    }


def multi_batch_out(
    db: Session,
    batches: list[PerformanceAssessmentBatch],
    *,
    group_key: str,
    idempotent: bool = False,
    assessment_ids_by_batch: Optional[dict[int, list[int]]] = None,
) -> dict[str, Any]:
    items = []
    for b in batches:
        row = batch_progress_out(db, b)
        if assessment_ids_by_batch is not None and b.id in assessment_ids_by_batch:
            row["assessment_ids"] = assessment_ids_by_batch[b.id]
        row["idempotent"] = idempotent
        items.append(row)
    return {
        "group_key": group_key,
        "cycle_id": batches[0].cycle_id if batches else None,
        "hr_review_required": all(bool(b.hr_review_required) for b in batches) if batches else False,
        "batch_count": len(items),
        "batches": items,
        "assessment_count": sum(int(x.get("total") or 0) for x in items),
        "idempotent": idempotent,
    }
