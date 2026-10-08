"""七类考核计分。只做结构化规则，不用自然语言决定分数。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional


def D(value) -> Decimal:
    return Decimal(str(value))


def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def shortfall_points(*, actual: Decimal, target: Decimal, per: Decimal, floor: Decimal, cap: Decimal) -> Decimal:
    missing = target - actual
    if missing < 0:
        missing = Decimal(0)
    score = cap - missing * per
    if score < floor:
        score = floor
    if score > cap:
        score = cap
    return q2(score)


def threshold_floor_points(*, actual: Optional[Decimal], target: Decimal, floor_count: Decimal, cap: Decimal) -> Optional[Decimal]:
    """少 1 扣 1；低于 floor_count 为 0。actual 为空表示待补，不是 0。"""
    if actual is None:
        return None
    if actual < floor_count:
        return q2(Decimal(0))
    return shortfall_points(actual=actual, target=target, per=Decimal(1), floor=Decimal(0), cap=cap)


def band_points(value: Decimal, bands: list[dict]) -> Optional[Decimal]:
    """区间左闭右开。命中不是恰好一档则返回 None。"""
    hits = []
    for band in bands:
        lo = D(band["min"]) if band.get("min") is not None else None
        hi = D(band["max"]) if band.get("max") is not None else None
        if lo is not None and value < lo:
            continue
        if hi is not None and value >= hi:
            continue
        hits.append(band)
    if len(hits) != 1:
        return None
    return q2(D(hits[0]["points"]))


def parse_metric_value(raw: Any, rule: Optional[dict] = None) -> Optional[Decimal]:
    """把员工/系统录入的实际值解析成可计分的 Decimal。空或无法解析返回 None。"""
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    if not text:
        return None
    as_percent = text.endswith("%")
    if as_percent:
        text = text[:-1].strip()
    if not text:
        return None
    try:
        val = D(text)
    except Exception:
        return None
    rule = rule or {}
    kind = rule.get("type")
    if kind == "ratio_bands":
        bands = rule.get("bands") or []
        edges = [
            D(b[k])
            for b in bands
            for k in ("min", "max")
            if b.get(k) is not None
        ]
        scale_max = max(edges) if edges else Decimal(1)
        # 区间在 0–1 时：>=1 或带 % 视为百分数（90 → 0.9，1 → 0.01）。
        # 已落在区间内的小数保持原值（0.85 → 0.85）；100% 写成 100 或 100%。
        if scale_max <= Decimal(1) and (as_percent or val >= Decimal(1)):
            val = val / Decimal(100)
    return val


def score_rule_actual(rule: dict, actual: Decimal) -> Optional[Decimal]:
    """按单条 rule_config 计分。manual_points 等需人工的返回 None。"""
    kind = (rule or {}).get("type")
    if kind in ("ratio_bands", "count_bands"):
        return band_points(actual, rule.get("bands") or [])
    if kind == "shortfall_deduction":
        return shortfall_points(
            actual=actual,
            target=D(rule["target"]),
            per=D(rule["points_per_missing"]),
            floor=D(rule.get("floor") or 0),
            cap=D(rule.get("cap") or rule.get("max_points") or 0),
        )
    if kind == "floor_shortfall":
        return threshold_floor_points(
            actual=actual,
            target=D(rule["target"]),
            floor_count=D(rule["floor_count"]),
            cap=D(rule.get("cap") or rule.get("max_points") or 0),
        )
    return None


def band_gaps(bands: list[dict], probes: list[Decimal]) -> list[str]:
    missing = []
    for probe in probes:
        if band_points(probe, bands) is None:
            missing.append(str(probe))
    return missing


def personal_target(per_person: Decimal, project_count: int) -> Decimal:
    """内容制作按人合计，不乘项目数。"""
    _ = project_count
    return per_person


def per_project_target(per_project: Decimal, project_count: int) -> Decimal:
    return per_project * Decimal(project_count)


def apply_lead_override(lines: list[dict], trigger_key: str, full_keys: list[str]) -> list[dict]:
    trigger = next((x for x in lines if x["metric_key"] == trigger_key), None)
    if not trigger or trigger.get("data_state") == "missing":
        return lines
    if not trigger.get("qualified"):
        return lines
    out = []
    for line in lines:
        if line["metric_key"] in full_keys and line.get("data_state") != "missing":
            copied = dict(line)
            copied["awarded_points"] = q2(D(copied["max_points"]))
            copied["trace"] = f"因 {trigger_key} 达标，按覆盖规则记满分"
            out.append(copied)
        else:
            out.append(line)
    return out


def sum_points(lines: list[dict]) -> Optional[Decimal]:
    if any(x.get("data_state") == "missing" or x.get("awarded_points") is None for x in lines):
        return None
    return q2(sum((D(x["awarded_points"]) for x in lines), Decimal(0)))


def renewal_points(*, has_project: bool, due_count: Optional[int], ratio: Optional[Decimal], bands: list[dict], default_full: Decimal) -> Optional[Decimal]:
    if not has_project:
        return q2(default_full)
    if due_count == 0 or ratio is None:
        return None
    return band_points(ratio, bands)


def market_payroll(score: Decimal, base: Optional[Decimal]) -> dict:
    if score >= 90:
        label, coeff = "优秀", D("1.00")
    elif score >= 80:
        label, coeff = "良好", D("0.80")
    elif score >= 60:
        label, coeff = "合格", D("0.60")
    else:
        label, coeff = "不合格", D("0")
    amount = None if base is None else q2(base * coeff)
    return {"grade_label": label, "coefficient": coeff, "amount": amount, "forced_fail": False}


def brand_payroll(score: Decimal, base: Optional[Decimal], *, fraud: bool = False) -> dict:
    adjusted = score
    forced = False
    if fraud:
        adjusted = q2(score - D(26))
        forced = True
    if forced:
        label, coeff = "不合格", D("0")
    elif adjusted >= 90:
        label, coeff = "优秀", None
    elif adjusted >= 70:
        label, coeff = "全额", D("1.00")
    elif adjusted >= 60:
        label, coeff = "八成", D("0.80")
    else:
        label, coeff = "五成", D("0.50")
    amount = None
    if coeff is not None and base is not None and not forced:
        amount = q2(base * coeff)
    if forced:
        amount = q2(Decimal(0)) if base is not None else None
    return {
        "grade_label": label,
        "coefficient": coeff,
        "amount": amount,
        "total_points": adjusted,
        "forced_fail": forced,
    }


def score_definition(defn: dict, actuals: dict) -> dict:
    """按模板规则试算。actual 为空是待补，不当成 0。"""
    lines = []
    for item in defn.get("items") or []:
        key = item["metric_key"]
        raw = actuals.get(key, None)
        rule = item.get("rule") or {}
        max_points = D(item.get("max_points") or 0)
        if raw is None or raw == "":
            lines.append({
                "metric_key": key,
                "name": item.get("name"),
                "max_points": q2(max_points),
                "awarded_points": None,
                "data_state": "missing",
                "trace": "待补",
            })
            continue
        kind = rule.get("type")
        parsed = parse_metric_value(raw, rule)
        if parsed is None:
            lines.append({
                "metric_key": key,
                "name": item.get("name"),
                "max_points": q2(max_points),
                "awarded_points": None,
                "data_state": "missing",
                "trace": "实际值无法解析",
            })
            continue
        actual = parsed
        if kind == "shortfall_deduction":
            awarded = shortfall_points(
                actual=actual,
                target=D(rule["target"]),
                per=D(rule["points_per_missing"]),
                floor=D(rule.get("floor") or 0),
                cap=D(rule.get("cap") or item["max_points"]),
            )
            trace = f"目标 {rule['target']}，实际 {actual}，每少 1 扣 {rule['points_per_missing']}"
        elif kind == "floor_shortfall":
            awarded = threshold_floor_points(
                actual=actual,
                target=D(rule["target"]),
                floor_count=D(rule["floor_count"]),
                cap=D(rule.get("cap") or item["max_points"]),
            )
            trace = f"低于 {rule['floor_count']} 记 0，否则按缺口扣分"
        elif kind in ("ratio_bands", "count_bands"):
            awarded = band_points(actual, rule.get("bands") or [])
            trace = f"{kind} 实际 {actual}"
        else:
            awarded = actual if actual <= max_points else max_points
            trace = "按录入分计入，不超过满分"
        lines.append({
            "metric_key": key,
            "name": item.get("name"),
            "max_points": q2(max_points),
            "awarded_points": None if awarded is None else q2(awarded),
            "data_state": "ok",
            "qualified": key in {"ops.leads", "content.leads"} and awarded == max_points,
            "trace": trace,
        })
    lines = apply_lead_override(lines, "ops.leads", ["ops.published", "ops.views"])
    lines = apply_lead_override(lines, "content.leads", ["content.output", "content.views"])
    total = sum_points(lines)
    return {"lines": lines, "total_points": total, "formal": total is not None}


def lecturer_incompetent(valid_complaints: int) -> bool:
    """原文是超过 3 次，3 次不触发。"""
    return valid_complaints > 3


def observation_release(*, end_score: Optional[Decimal], retriggered: bool) -> str:
    if end_score is None:
        return "pending"
    if end_score >= 75 and not retriggered:
        return "release"
    return "hr_todo"


def validate_definition(defn: dict) -> list[dict]:
    issues: list[dict] = []
    items = defn.get("items") or []
    nominal = defn.get("nominal_total")
    if defn.get("scoring_mode") == "points_sum" and nominal is not None:
        total = sum((D(i.get("max_points") or 0) for i in items), Decimal(0))
        if total != D(nominal):
            issues.append({
                "code": defn.get("total_conflict") or "C01",
                "blocking": True,
                "message": f"分值合计 {total} 与标称满分 {nominal} 不一致",
            })
    for item in items:
        rule = item.get("rule") or {}
        if rule.get("type") == "ratio_bands":
            top = max((D(b["points"]) for b in rule.get("bands") or []), default=Decimal(0))
            if item.get("max_points") is not None and top != D(item["max_points"]):
                issues.append({
                    "code": item.get("conflict") or "C03",
                    "blocking": True,
                    "path": item.get("metric_key"),
                    "message": f"{item.get('metric_key')} 满分 {item.get('max_points')} 与最高档 {top} 不一致",
                })
            gaps = band_gaps(rule.get("bands") or [], [D(x) for x in rule.get("required_edges") or []])
            if gaps:
                issues.append({
                    "code": "C06",
                    "blocking": True,
                    "path": item.get("metric_key"),
                    "message": f"{item.get('metric_key')} 区间未覆盖 {', '.join(gaps)}",
                })
    for code in defn.get("open_issues") or []:
        issues.append({"code": code, "blocking": True, "message": f"{code} 待业务确认"})
    return issues


def blocking(issues: list[dict]) -> list[dict]:
    return [x for x in issues if x.get("blocking")]
