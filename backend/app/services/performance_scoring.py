"""绩效评分：等级、系数、加权分与考核单分数缓存。"""
from __future__ import annotations

from decimal import Decimal

from app.models.performance import PerformanceAssessment, PerformanceAssessmentItem


def _grade_and_coeff(score: int) -> tuple[str, Decimal]:
    if score >= 90:
        return "A+", Decimal("1.20")
    if score >= 85:
        return "A", Decimal("1.10")
    if score >= 70:
        return "B", Decimal("1.00")
    if score >= 60:
        return "C", Decimal("0.85")
    return "D", Decimal("0.70")


def _bonus(coeff: Decimal) -> Decimal:
    return (Decimal("5000") * coeff).quantize(Decimal("0.01"))


GRADE_COEFF = {
    "A+": Decimal("1.20"),
    "A": Decimal("1.10"),
    "B": Decimal("1.00"),
    "C": Decimal("0.85"),
    "D": Decimal("0.70"),
}


def resolve_grade(score) -> str:
    s = Decimal(str(score or 0))
    if s >= 95:
        return "A+"
    if s >= 85:
        return "A"
    if s >= 75:
        return "B"
    if s >= 65:
        return "C"
    return "D"


def _item_effective_score(item) -> Decimal:
    for attr in ("final_score", "leader_score", "system_score", "self_score"):
        v = getattr(item, attr, None)
        if v is not None:
            return Decimal(str(v))
    return Decimal("0")


def compute_weighted_score(items) -> Decimal:
    """加权平均，权重合计为分母。空列表返回 0。"""
    rows = list(items or [])
    total_w = sum(Decimal(str(getattr(i, "weight", 0) or 0)) for i in rows)
    if total_w <= 0:
        return Decimal("0.00")
    acc = sum(_item_effective_score(i) * Decimal(str(i.weight)) for i in rows)
    return (acc / total_w).quantize(Decimal("0.01"))


def _as_int_score(val: Decimal) -> int:
    return int(val.quantize(Decimal("1")))


def _fill_score_caches(assessment: PerformanceAssessment, items: list[PerformanceAssessmentItem]) -> None:
    if getattr(assessment, "engine_version", None) not in (None, "", "legacy"):
        return
    okr = [i for i in items if i.data_source == "okr"]
    kpi = [i for i in items if i.data_source == "system"]
    behavior = [i for i in items if i.data_source == "manual"]
    self_items = [i for i in items if i.data_source in ("self_manual", "manual")]
    if okr:
        assessment.okr_score = _as_int_score(compute_weighted_score(okr))
    if kpi:
        assessment.kpi_score = _as_int_score(compute_weighted_score(kpi))
    if behavior:
        assessment.behavior_score = _as_int_score(compute_weighted_score(behavior))
    if self_items and any(i.self_score is not None for i in self_items):
        assessment.self_score = _as_int_score(compute_weighted_score(self_items))
    if any(i.leader_score is not None or i.system_score is not None for i in items):
        total = compute_weighted_score(items)
        assessment.manager_score = _as_int_score(total)
        assessment.grade = resolve_grade(total)
        assessment.coefficient = GRADE_COEFF[assessment.grade]
        assessment.bonus_amount = _bonus(assessment.coefficient)


def _freeze_actuals(db, assessment: PerformanceAssessment, items: list[PerformanceAssessmentItem]) -> None:
    from app.services.performance_data_source import resolve_actual

    for item in items:
        actual, _score = resolve_actual(item, assessment, db)
        item.actual_value = actual
        item.system_score = None


def _archive_item_finals(items: list[PerformanceAssessmentItem]) -> None:
    for item in items:
        if item.leader_score is not None:
            item.final_score = item.leader_score
        elif item.system_score is not None:
            item.final_score = item.system_score
        elif item.self_score is not None:
            item.final_score = item.self_score
