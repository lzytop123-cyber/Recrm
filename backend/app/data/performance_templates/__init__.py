"""幂等加载考核模板草稿。"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.data.performance_templates.catalog import FAMILIES
from app.models.department import Department
from app.models.performance import (
    PerformanceIndicatorDefinition,
    PerformanceTemplate,
    PerformanceTemplateItem,
    PerformanceTemplateScope,
)
from app.services.performance_rule_engine import validate_definition

# 日常七类（不含入职 ONBOARD_*）
DEPARTMENT_FAMILIES = (
    "MARKET_MONTHLY",
    "AI_OPS_MONTHLY",
    "CONTENT_MONTHLY",
    "BRAND_MONTHLY",
    "LIVE_HOST_MONTHLY",
    "LIVE_ADS_MONTHLY",
    "LECTURER_MONTHLY",
)

# 按组织部门名称匹配适用范围（名称变了需改这里）
FAMILY_SCOPES: dict[str, list[dict[str, str]]] = {
    "MARKET_MONTHLY": [{"department_name": "市场销售与客户中心", "job_title": "市场业务"}],
    "AI_OPS_MONTHLY": [{"department_name": "账号与客户运营组", "job_title": "AI运营"}],
    "CONTENT_MONTHLY": [{"department_name": "内容策划制作组", "job_title": "内容运营"}],
    "BRAND_MONTHLY": [{"department_name": "品宣与设计组", "job_title": "品牌宣传"}],
    "LIVE_HOST_MONTHLY": [{"department_name": "直播运营组", "job_title": "直播主播"}],
    "LIVE_ADS_MONTHLY": [{"department_name": "直播运营组", "job_title": "直播投放"}],
    "LECTURER_MONTHLY": [{"department_name": "讲师交付组", "job_title": "讲师"}],
}


def _infer_scoring_type(rule: dict | None, metric_key: str) -> str:
    if not rule:
        if metric_key.startswith("lecturer."):
            return "bonus"
        return "quantity"
    rtype = rule.get("type")
    mapping = {
        "shortfall_deduction": "quantity",
        "floor_shortfall": "quantity",
        "proportional": "quantity",
        "ratio_bands": "tier",
        "count_bands": "tier",
        "renewal_bands": "tier",
        "event_bonus": "bonus",
        "event_deduction": "bonus",
        "manual_points": "subjective",
        "event_deduction_base": "quantity",
    }
    if rtype == "event_deduction" and rule.get("base") is not None:
        return "quantity"
    if rtype in mapping:
        return mapping[rtype]
    if rule.get("reviewer") == "manager":
        return "subjective"
    return "quantity"


# 主管填：投诉/评价/规范/主观等员工不宜自报的项
_MANAGER_METRIC_KEYS = frozenset({
    "market.response_late", "market.collaboration", "market.sync", "market.reports",
    "market.solution", "market.sales_sop",
    "ops.complaints", "ops.service",
    "content.complaints",
    "brand.video_quality", "brand.attitude", "brand.compliance", "brand.ledger",
    "live.review", "live.violation", "live.drive", "live.optimize", "live.learn",
    "ads.review", "ads.drive", "ads.optimize", "ads.learn",
    "lecturer.talk_good", "lecturer.talk_excellent", "lecturer.internal_excellent",
    "lecturer.talk_bad", "lecturer.talk_complaint", "lecturer.internal_bad",
    "lecturer.internal_complaint", "lecturer.behavior", "lecturer.behavior_impact",
    "lecturer.etiquette", "lecturer.knowledge", "lecturer.absence",
})


def _infer_handling(scoring_type: str, rule: dict | None, metric_key: str = "") -> str:
    """谁填：主管专填项 / 主观分 → manager_score；其余默认员工自填（不走系统自动抓取）。"""
    if metric_key in _MANAGER_METRIC_KEYS:
        return "manager_score"
    if scoring_type == "subjective" or (rule or {}).get("reviewer") == "manager":
        return "manager_score"
    if scoring_type in ("bonus", "veto", "quantity", "tier"):
        return "employee_submit"
    return "employee_submit"


def _infer_data_source_code(scoring_type: str, metric_key: str) -> str:
    """与指标库 seed 对齐：不用 CRM 自动抓取，统一手工台账 / 主管评价。"""
    if scoring_type == "subjective" or metric_key in _MANAGER_METRIC_KEYS:
        return "manager_review"
    return "ledger.manual"


def _item_fields(item: dict[str, Any]) -> dict[str, Any]:
    rule = item.get("rule") or {}
    metric_key = item["metric_key"]
    scoring_type = _infer_scoring_type(rule, metric_key)
    handling = item.get("handling_mode") or _infer_handling(scoring_type, rule, metric_key)
    source_code = _infer_data_source_code(scoring_type, metric_key)
    # 主观 / 主管专填 → self_manual；其余员工自填 → manual（不标 system）
    if scoring_type == "subjective" or handling == "manager_score":
        data_source = "self_manual"
    elif handling.startswith("system"):
        data_source = "system"
    else:
        data_source = "manual"
    unit = rule.get("unit") or item.get("unit") or ""
    if not unit and scoring_type == "bonus":
        if rule.get("per_amount") is not None:
            unit = f"分/{rule['per_amount']}元"
        else:
            unit = "分/次"
    # 不要把 points_per_event 当成目标：那是单次加减分，仅 bonus 项下面单独写入
    target = (
        rule.get("target")
        or rule.get("target_personal")
        or rule.get("target_per_project")
        or rule.get("target_ratio")
        or rule.get("target_hours_per_day")
        or rule.get("target_note")
    )
    max_points = item.get("max_points")
    # 事件加减分：无单项满分，max_points 保持空；单次分值走 target_value / hint
    weight = Decimal(str(max_points)) if max_points is not None else Decimal("0")
    score_rule = rule.get("type") or ("event_ledger" if scoring_type == "bonus" else "points_sum")
    hint_parts = []
    if rule.get("points_per_event"):
        sign = "+" if rule.get("type") == "event_bonus" else "-"
        hint_parts.append(f"{sign}{rule['points_per_event']}分/次")
    if rule.get("points_per") and rule.get("per_amount"):
        hint_parts.append(f"+{rule['points_per']}分/{rule['per_amount']}元")
    if rule.get("points_min") and rule.get("points_max"):
        hint_parts.append(f"-{rule['points_min']}~{rule['points_max']}分/次")
    # 目标：纯事件加减分用单次分值；有单项满分的扣分项不把「每次扣几分」当目标
    if scoring_type == "bonus" and max_points is None:
        if rule.get("points_per_event") is not None:
            target = rule["points_per_event"]
        elif rule.get("points_per") is not None and rule.get("per_amount") is not None:
            target = f"{rule['points_per']}/{rule['per_amount']}"
        elif rule.get("points_min") is not None and rule.get("points_max") is not None:
            target = f"{rule['points_min']}~{rule['points_max']}"
    return {
        "name": item["name"],
        "weight": weight,
        "data_source": data_source,
        "source_ref": source_code,
        "metric_key": item["metric_key"],
        "max_points": Decimal(str(max_points)) if max_points is not None else None,
        "rule_config_json": json.dumps(rule, ensure_ascii=False) if rule else None,
        "score_rule": score_rule,
        "scoring_type": scoring_type,
        "handling_mode": handling,
        # 双评分：评分人（manager=直属主管 / training=培训部）。
        # 支持顶层 evaluator，也支持写在 rule 里（rule 会被持久化，重建指标时不丢）
        "evaluator": item.get("evaluator") or (rule.get("evaluator") if isinstance(rule, dict) else None),
        "unit": unit or None,
        "target_value": str(target) if target is not None else None,
        # 表体评分细则优先；无则退回自动生成的加减分摘要
        "hint": item.get("hint") or rule.get("note") or ("；".join(hint_parts) if hint_parts else None),
    }


def _metric_key_to_indicator_id(db: Session, keys: list[str]) -> dict[str, int]:
    if not keys:
        return {}
    rows = (
        db.query(PerformanceIndicatorDefinition)
        .filter(PerformanceIndicatorDefinition.metric_key.in_(keys))
        .all()
    )
    return {r.metric_key: r.id for r in rows}


def link_template_items_to_indicators(db: Session) -> int:
    """按 metric_key 回填 indicator_definition_id，并同步 data_source / source_ref。"""
    defs = {r.metric_key: r for r in db.query(PerformanceIndicatorDefinition).all() if r.metric_key}
    updated = 0
    rows = (
        db.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.metric_key.isnot(None))
        .all()
    )
    for row in rows:
        ind = defs.get(row.metric_key or "")
        if ind is None:
            continue
        changed = False
        if row.indicator_definition_id != ind.id:
            row.indicator_definition_id = ind.id
            changed = True
        # 与指标库 / from-indicator 对齐展示与取数
        want_source = "system" if (ind.handling_mode or "").startswith("system") else (
            "self_manual" if ind.scoring_type == "subjective" else "manual"
        )
        if row.data_source != want_source:
            row.data_source = want_source
            changed = True
        if row.source_ref != ind.data_source_code:
            row.source_ref = ind.data_source_code
            changed = True
        if changed:
            updated += 1
    if updated:
        db.flush()
    return updated


def _upsert_items(db: Session, template_id: int, items: list[dict[str, Any]]) -> None:
    db.query(PerformanceTemplateItem).filter(PerformanceTemplateItem.template_id == template_id).delete()
    key_map = _metric_key_to_indicator_id(
        db, [raw["metric_key"] for raw in items if raw.get("metric_key")]
    )
    for index, raw in enumerate(items):
        fields = _item_fields(raw)
        fields["indicator_definition_id"] = key_map.get(raw.get("metric_key") or "")
        db.add(
            PerformanceTemplateItem(
                template_id=template_id,
                order_no=index,
                **fields,
            )
        )


def _resolve_scopes(db: Session, family_code: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in FAMILY_SCOPES.get(family_code) or []:
        dept = db.query(Department).filter(Department.name == spec["department_name"]).first()
        if not dept:
            continue
        out.append({"department_id": dept.id, "job_title": spec["job_title"]})
    return out


def _upsert_scopes(db: Session, template_id: int, family_code: str) -> None:
    scopes = _resolve_scopes(db, family_code)
    db.query(PerformanceTemplateScope).filter(
        PerformanceTemplateScope.template_id == template_id
    ).delete()
    for raw in scopes:
        db.add(
            PerformanceTemplateScope(
                template_id=template_id,
                department_id=raw["department_id"],
                job_title=raw["job_title"],
            )
        )


def load_drafts(
    db: Session,
    *,
    dry_run: bool = False,
    family_codes: tuple[str, ...] | list[str] | None = None,
) -> list[str]:
    """加载/刷新草稿。family_codes 为空则加载全部 FAMILIES。"""
    allow = set(family_codes) if family_codes is not None else None
    codes = []
    if not dry_run:
        # 先写指标库，模板项才能按 metric_key 挂上 indicator_definition_id
        from app.services.performance_indicator_catalog import seed_indicators_from_drafts

        seed_indicators_from_drafts(db)
    for spec in FAMILIES:
        if allow is not None and spec["family_code"] not in allow:
            continue
        code = f"{spec['family_code']}_V1"
        codes.append(spec["family_code"])
        if dry_run:
            continue
        row = db.query(PerformanceTemplate).filter(PerformanceTemplate.code == code).first()
        issues = validate_definition(spec)
        if row is None:
            row = PerformanceTemplate(
                name=spec["name"],
                code=code,
                status="draft",
                family_code=spec["family_code"],
                version=1,
                engine_version="kpi-v2",
                assessment_kind=spec["assessment_kind"],
                scoring_mode=spec["scoring_mode"],
                nominal_total=spec["nominal_total"],
                definition_json=json.dumps(spec, ensure_ascii=False),
                blocking_issues_json=json.dumps(issues, ensure_ascii=False),
                cycle_type="monthly",
            )
            db.add(row)
            db.flush()
            _upsert_items(db, row.id, spec.get("items") or [])
            _upsert_scopes(db, row.id, spec["family_code"])
        else:
            row.name = spec["name"]
            row.assessment_kind = spec["assessment_kind"]
            row.scoring_mode = spec["scoring_mode"]
            row.nominal_total = spec["nominal_total"]
            row.definition_json = json.dumps(spec, ensure_ascii=False)
            row.blocking_issues_json = json.dumps(issues, ensure_ascii=False)
            row.status = "draft"
            row.engine_version = "kpi-v2"
            row.family_code = spec["family_code"]
            _upsert_items(db, row.id, spec.get("items") or [])
            _upsert_scopes(db, row.id, spec["family_code"])
    if not dry_run:
        link_template_items_to_indicators(db)
        db.commit()
    return codes
