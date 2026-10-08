"""七类考核计分与发布校验。"""
from decimal import Decimal

from app.services.performance_rule_engine import (
    apply_lead_override,
    band_gaps,
    band_points,
    brand_payroll,
    lecturer_incompetent,
    market_payroll,
    observation_release,
    per_project_target,
    personal_target,
    renewal_points,
    shortfall_points,
    sum_points,
    threshold_floor_points,
    validate_definition,
)


def test_market_signed_clients_not_weighted() -> None:
    assert shortfall_points(actual=Decimal(4), target=Decimal(4), per=Decimal(5), floor=Decimal(0), cap=Decimal(20)) == Decimal("20.00")
    assert shortfall_points(actual=Decimal(3), target=Decimal(4), per=Decimal(5), floor=Decimal(0), cap=Decimal(20)) == Decimal("15.00")
    assert shortfall_points(actual=Decimal(0), target=Decimal(4), per=Decimal(5), floor=Decimal(0), cap=Decimal(20)) == Decimal("0.00")


def test_market_leads_floor_and_missing() -> None:
    assert threshold_floor_points(actual=Decimal(3), target=Decimal(10), floor_count=Decimal(4), cap=Decimal(10)) == Decimal("0.00")
    assert threshold_floor_points(actual=Decimal(4), target=Decimal(10), floor_count=Decimal(4), cap=Decimal(10)) == Decimal("4.00")
    assert threshold_floor_points(actual=Decimal(9), target=Decimal(10), floor_count=Decimal(4), cap=Decimal(10)) == Decimal("9.00")
    assert threshold_floor_points(actual=Decimal(10), target=Decimal(10), floor_count=Decimal(4), cap=Decimal(10)) == Decimal("10.00")
    assert threshold_floor_points(actual=None, target=Decimal(10), floor_count=Decimal(4), cap=Decimal(10)) is None


def test_ops_total_conflict_blocks_publish() -> None:
    issues = validate_definition({
        "scoring_mode": "points_sum",
        "nominal_total": "100",
        "total_conflict": "C01",
        "items": [{"metric_key": "ops.published", "max_points": "110"}],
    })
    assert any(x["code"] == "C01" and x["blocking"] for x in issues)


def test_content_band_max_conflict() -> None:
    issues = validate_definition({
        "scoring_mode": "points_sum",
        "nominal_total": "100",
        "items": [{
            "metric_key": "content.output",
            "max_points": "30",
            "conflict": "C03",
            "rule": {"type": "ratio_bands", "bands": [{"min": "1", "max": None, "points": "20"}]},
        }],
    })
    assert any(x["code"] == "C03" for x in issues)


def test_content_target_is_personal_not_per_project() -> None:
    assert personal_target(Decimal(120), 2) == Decimal(120)
    assert per_project_target(Decimal(25), 2) == Decimal(50)


def test_lead_override_marks_trace() -> None:
    lines = apply_lead_override(
        [
            {"metric_key": "ops.published", "max_points": "20", "awarded_points": "10", "data_state": "ok"},
            {"metric_key": "ops.views", "max_points": "20", "awarded_points": "10", "data_state": "ok"},
            {"metric_key": "ops.leads", "max_points": "25", "awarded_points": "25", "qualified": True, "data_state": "ok"},
        ],
        "ops.leads",
        ["ops.published", "ops.views"],
    )
    assert lines[0]["awarded_points"] == Decimal("20.00")
    assert "ops.leads" in lines[0]["trace"]


def test_renewal_zero_due_is_not_default_full() -> None:
    bands = [{"min": "0.8", "max": None, "points": "15"}]
    assert renewal_points(has_project=False, due_count=0, ratio=None, bands=bands, default_full=Decimal(15)) == Decimal("15.00")
    assert renewal_points(has_project=True, due_count=0, ratio=None, bands=bands, default_full=Decimal(15)) is None


def test_live_edges_block_until_defined() -> None:
    bands = [{"min": "0", "max": "1", "points": "10"}]
    assert "1" in band_gaps(bands, [Decimal(1)])
    filled = [{"min": "0", "max": "1", "points": "10"}, {"min": "1", "max": None, "points": "20"}]
    assert band_points(Decimal(1), filled) == Decimal("20.00")
    assert band_points(Decimal("0.9"), filled) == Decimal("10.00")


def test_brand_keeps_105_and_fraud_fails() -> None:
    assert sum_points([
        {"awarded_points": "100", "data_state": "ok"},
        {"awarded_points": "5", "data_state": "ok"},
    ]) == Decimal("105.00")
    fraud = brand_payroll(Decimal(100), Decimal(2000), fraud=True)
    assert fraud["total_points"] == Decimal("74.00")
    assert fraud["forced_fail"] is True
    assert fraud["grade_label"] == "不合格"


def test_payroll_uses_base_not_5000() -> None:
    market = market_payroll(Decimal(85), Decimal(2000))
    assert market["amount"] == Decimal("1600.00")
    assert market_payroll(Decimal(85), None)["amount"] is None
    brand = brand_payroll(Decimal(65), Decimal(2000))
    assert brand["amount"] == Decimal("1600.00")
    assert brand["coefficient"] == Decimal("0.80")


def test_missing_blocks_formal_total() -> None:
    assert sum_points([{"awarded_points": None, "data_state": "missing"}]) is None


def test_lecturer_threshold_and_observation() -> None:
    assert lecturer_incompetent(3) is False
    assert lecturer_incompetent(4) is True
    assert observation_release(end_score=Decimal(80), retriggered=True) == "hr_todo"
    assert observation_release(end_score=Decimal(80), retriggered=False) == "release"


def test_parse_ratio_percent_and_score_bands() -> None:
    from app.services.performance_rule_engine import parse_metric_value, score_rule_actual

    rule = {
        "type": "ratio_bands",
        "unit": "%",
        "bands": [
            {"min": "0.9", "max": None, "points": "20"},
            {"min": "0.8", "max": "0.9", "points": "18"},
            {"min": "0.6", "max": "0.8", "points": "15"},
            {"min": "0", "max": "0.6", "points": "5"},
        ],
    }
    assert parse_metric_value("90", rule) == Decimal("0.9")
    assert parse_metric_value("90%", rule) == Decimal("0.9")
    assert parse_metric_value("1", rule) == Decimal("0.01")
    assert parse_metric_value("100", rule) == Decimal("1")
    assert parse_metric_value("0.85", rule) == Decimal("0.85")
    assert score_rule_actual(rule, Decimal("0.9")) == Decimal("20.00")
    assert score_rule_actual(rule, Decimal("0.85")) == Decimal("18.00")
    assert score_rule_actual(rule, Decimal("0.5")) == Decimal("5.00")


def test_count_bands_score() -> None:
    from app.services.performance_rule_engine import score_rule_actual

    rule = {
        "type": "count_bands",
        "bands": [
            {"min": "0", "max": "1", "points": "10"},
            {"min": "1", "max": "4", "points": "5"},
            {"min": "4", "max": None, "points": "0"},
        ],
    }
    assert score_rule_actual(rule, Decimal("0")) == Decimal("10.00")
    assert score_rule_actual(rule, Decimal("2")) == Decimal("5.00")
    assert score_rule_actual(rule, Decimal("4")) == Decimal("0.00")
