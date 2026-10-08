"""加权算分与评级阈值。"""
from decimal import Decimal
from types import SimpleNamespace

from app.services.performance import compute_weighted_score, resolve_grade


def _item(**kwargs):
    base = dict(
        weight=0,
        final_score=None,
        leader_score=None,
        system_score=None,
        self_score=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_weighted_score_uses_weights() -> None:
    items = [
        _item(weight=40, leader_score=Decimal("80")),
        _item(weight=60, leader_score=Decimal("100")),
    ]
    assert compute_weighted_score(items) == Decimal("92.00")


def test_weighted_prefers_final_then_leader() -> None:
    items = [_item(weight=100, final_score=Decimal("70"), leader_score=Decimal("90"))]
    assert compute_weighted_score(items) == Decimal("70.00")


def test_weighted_empty_is_zero() -> None:
    assert compute_weighted_score([]) == Decimal("0.00")


def test_resolve_grade_thresholds() -> None:
    assert resolve_grade(95) == "A+"
    assert resolve_grade(94) == "A"
    assert resolve_grade(85) == "A"
    assert resolve_grade(84) == "B"
    assert resolve_grade(75) == "B"
    assert resolve_grade(74) == "C"
    assert resolve_grade(65) == "C"
    assert resolve_grade(64) == "D"
    assert resolve_grade(0) == "D"
