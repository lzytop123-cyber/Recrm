"""绩效指标数据源：系统聚合 / OKR / 手填。"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.okr import OKR_LEVEL_PERSONAL, OKR_STATUS_TERMINATED, KeyResult, Okr
from app.models.opportunity import OPP_STAGE_WON, Opportunity
from app.models.payment import PAYMENT_STATUS_CONFIRMED, Payment
from app.models.performance import PerformanceAssessment, PerformanceAssessmentItem, PerformanceCycle

CAP = Decimal("120")


def _parse_year_month(label: str) -> Optional[tuple[int, int]]:
    """解析 YYYY-MM / 2026年9月 / 2026年09月考核周期 → (year, month)。"""
    text = (label or "").strip()
    if not text:
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})\b", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def cycle_window(cycle: PerformanceCycle) -> tuple[date, date]:
    """从 period_label + cycle_type 推周期起止日（周期表没有独立日期字段）。"""
    label = cycle.period_label or ""
    ctype = cycle.cycle_type or "monthly"
    try:
        if ctype == "yearly":
            year = int(label[:4])
            return date(year, 1, 1), date(year, 12, 31)
        if ctype == "quarterly" or "-Q" in label.upper():
            if "-Q" in label.upper():
                year_s, q_s = label.upper().split("-Q", 1)
                year, q = int(year_s), int(q_s)
            else:
                ym = _parse_year_month(label)
                if ym is None:
                    raise ValueError(f"unparseable quarterly label: {label}")
                year, month = ym
                q = (month - 1) // 3 + 1
            start_m = (q - 1) * 3 + 1
            end_m = start_m + 2
            return date(year, start_m, 1), date(year, end_m, calendar.monthrange(year, end_m)[1])
        ym = _parse_year_month(label)
        if ym is None:
            raise ValueError(f"unparseable period_label: {label}")
        year, month = ym
        if month < 1 or month > 12:
            raise ValueError(f"invalid month in period_label: {label}")
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    except (ValueError, TypeError):
        today = date.today()
        return today, today


def _parse_target(raw: Optional[str]) -> Optional[Decimal]:
    if not raw:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", raw.replace(",", ""))
    if not m:
        return None
    return Decimal(m.group(1))


def _score_from_ratio(actual: Decimal, target: Optional[Decimal]) -> Decimal:
    if target is None or target == 0:
        return Decimal("0")
    ratio = (actual / target) * Decimal("100")
    if ratio < 0:
        return Decimal("0")
    return min(CAP, ratio.quantize(Decimal("0.01")))


def _fmt(v: Decimal) -> str:
    return format(v.quantize(Decimal("0.01")), "f")


def resolve_actual(
    item: PerformanceAssessmentItem,
    assessment: PerformanceAssessment,
    db: Session,
) -> tuple[Optional[str], Optional[Decimal]]:
    """返回 (实际值显示串, 系统得分)。手填项返回 (None, None)。"""
    src = item.data_source
    if src == "system":
        return _resolve_system(item, assessment, db)
    if src == "okr":
        return _resolve_okr(item, assessment, db)
    return None, None


def _resolve_system(
    item: PerformanceAssessmentItem,
    assessment: PerformanceAssessment,
    db: Session,
) -> tuple[Optional[str], Optional[Decimal]]:
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == assessment.cycle_id).first()
    if not cycle:
        return None, None
    start, end = cycle_window(cycle)
    ref = item.source_ref or ""
    if ref == "customer.deals":
        start_dt = datetime.combine(start, time.min)
        end_dt = datetime.combine(end, time.max)
        total = (
            db.query(func.coalesce(func.sum(Opportunity.expected_amount), 0))
            .filter(
                Opportunity.owner_id == assessment.user_id,
                Opportunity.stage == OPP_STAGE_WON,
                Opportunity.won_at.isnot(None),
                Opportunity.won_at >= start_dt,
                Opportunity.won_at <= end_dt,
            )
            .scalar()
        )
        actual = Decimal(str(total or 0))
        score = _score_from_ratio(actual, _parse_target(item.target_value))
        return _fmt(actual), score
    if ref == "customer.payments":
        plan = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .join(Contract, Contract.id == Payment.contract_id)
            .filter(
                Contract.owner_id == assessment.user_id,
                Payment.due_date >= start,
                Payment.due_date <= end,
            )
            .scalar()
        )
        paid = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .join(Contract, Contract.id == Payment.contract_id)
            .filter(
                Contract.owner_id == assessment.user_id,
                Payment.status == PAYMENT_STATUS_CONFIRMED,
                Payment.paid_date >= start,
                Payment.paid_date <= end,
            )
            .scalar()
        )
        plan_amt = Decimal(str(plan or 0))
        paid_amt = Decimal(str(paid or 0))
        rate = (paid_amt / plan_amt * Decimal("100")) if plan_amt else Decimal("0")
        target = _parse_target(item.target_value) or Decimal("100")
        score = _score_from_ratio(rate, target)
        return f"{_fmt(rate)}%", score
    return None, None


def _okr_labels(cycle: PerformanceCycle) -> list[str]:
    label = cycle.period_label
    labels = [label]
    try:
        year_s, month_s = label.split("-", 1)
        year, month = int(year_s), int(month_s)
        mapped = f"{year}-Q{(month - 1) // 3 + 1}"
        if mapped not in labels:
            labels.append(mapped)
    except (ValueError, TypeError):
        pass
    return labels


def _resolve_okr(
    item: PerformanceAssessmentItem,
    assessment: PerformanceAssessment,
    db: Session,
) -> tuple[Optional[str], Optional[Decimal]]:
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.id == assessment.cycle_id).first()
    if not cycle:
        return None, None
    labels = _okr_labels(cycle)
    okrs = (
        db.query(Okr)
        .filter(
            Okr.owner_id == assessment.user_id,
            Okr.level == OKR_LEVEL_PERSONAL,
            Okr.period_label.in_(labels),
            Okr.status != OKR_STATUS_TERMINATED,
        )
        .all()
    )
    if not okrs:
        return "0", Decimal("0")
    krs = (
        db.query(KeyResult)
        .filter(KeyResult.okr_id.in_([o.id for o in okrs]))
        .all()
    )
    if krs:
        percents: list[Decimal] = []
        for kr in krs:
            target = Decimal(str(kr.target_value or 0))
            current = Decimal(str(kr.current_value or 0))
            if target <= 0:
                continue
            percents.append((current / target) * Decimal("100"))
        avg = sum(percents) / len(percents) if percents else Decimal("0")
    else:
        avg = Decimal(str(round(sum((o.progress or 0) for o in okrs) / len(okrs))))
    avg = max(Decimal("0"), min(Decimal("100"), avg)).quantize(Decimal("0.01"))
    return f"{_fmt(avg)}%", avg
