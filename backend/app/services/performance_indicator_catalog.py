"""部门指标库：查询、创建、停用、模板项快照与草稿导入。"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.rbac import DataScope, resolve_data_scope, user_dept_scope
from app.data.performance_templates.catalog import FAMILIES
from app.models.department import Department
from app.models.performance import (
    PerformanceAssessmentItem,
    PerformanceIndicatorDefinition,
    PerformanceTemplate,
    PerformanceTemplateItem,
)
from app.models.user import User
from app.services.performance_scoring_schema import (
    CONFIGURATION_VERSION,
    assert_configuration_integrity,
    data_sources_payload,
    handling_modes_payload,
    scoring_types_payload,
    validate_data_source,
    validate_handling_mode,
    validate_rule_config,
)

_FAMILY_JOB = {
    "MARKET_MONTHLY": "市场业务",
    "AI_OPS_MONTHLY": "AI运营",
    "CONTENT_MONTHLY": "内容运营",
    "BRAND_MONTHLY": "品牌宣传",
    "LIVE_HOST_MONTHLY": "直播主播",
    "LIVE_ADS_MONTHLY": "直播投放",
    "LECTURER_MONTHLY": "讲师",
}

_FAMILY_DEPT_NAME = {
    "MARKET_MONTHLY": "市场销售与客户中心",
    "AI_OPS_MONTHLY": "账号与客户运营组",
    "CONTENT_MONTHLY": "内容策划制作组",
    "BRAND_MONTHLY": "品宣与设计组",
    "LIVE_HOST_MONTHLY": "直播运营组",
    "LIVE_ADS_MONTHLY": "直播运营组",
    "LECTURER_MONTHLY": "讲师交付组",
}


def _dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _loads(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _infer_scoring_type(rule: dict | None, metric_key: str) -> str:
    if not rule:
        if metric_key.startswith("lecturer") or "complaint" in metric_key:
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
        "band": "tier",
        "threshold_floor": "quantity",
        "event_bonus": "bonus",
        "event_deduction": "bonus",
        "manual_points": "subjective",
    }
    if rtype in mapping:
        return mapping[rtype]
    if rule.get("reviewer") == "manager":
        return "subjective"
    return "quantity"

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


def _infer_handling(scoring_type: str, metric_key: str = "") -> str:
    """主管专填 / 主观 → manager_score；数量与加减分默认员工自填（不走系统自动）。"""
    # 入职维度：员工先自述，再由主管/培训部评分
    if metric_key.startswith("onboard."):
        return "employee_submit"
    if metric_key in _MANAGER_METRIC_KEYS:
        return "manager_score"
    if scoring_type == "subjective":
        return "manager_score"
    if scoring_type in ("bonus", "veto", "quantity", "tier"):
        return "employee_submit"
    return "employee_submit"


_SOURCE_ALIAS = {
    "system": "ledger.manual",
    "manual": "ledger.manual",
    "self_manual": "ledger.manual",
    "okr": "ledger.manual",
    "crm_lead": "ledger.manual",
}


def _normalize_source(code: str) -> str:
    """旧页面会传 system/manual；现统一手工台账 / 主管评价，不再默认 CRM 自动抓取。"""
    return _SOURCE_ALIAS.get((code or "").strip(), (code or "").strip()) or "ledger.manual"


def _infer_data_source(scoring_type: str, metric_key: str) -> str:
    if scoring_type == "subjective" or metric_key in _MANAGER_METRIC_KEYS:
        return "manager_review"
    return "ledger.manual"


def list_indicators(
    db: Session,
    *,
    department_id: Optional[int] = None,
    job_title: Optional[str] = None,
    status: Optional[str] = "active",
) -> list[PerformanceIndicatorDefinition]:
    q = db.query(PerformanceIndicatorDefinition)
    if status:
        q = q.filter(PerformanceIndicatorDefinition.status == status)
    if department_id is not None:
        q = q.filter(
            or_(
                PerformanceIndicatorDefinition.department_id.is_(None),
                PerformanceIndicatorDefinition.department_id == department_id,
            )
        )
    if job_title:
        q = q.filter(
            or_(
                PerformanceIndicatorDefinition.job_title.is_(None),
                PerformanceIndicatorDefinition.job_title == job_title,
            )
        )
    return q.order_by(PerformanceIndicatorDefinition.metric_key).all()


def get_indicator(db: Session, indicator_id: int) -> PerformanceIndicatorDefinition:
    row = (
        db.query(PerformanceIndicatorDefinition)
        .filter(PerformanceIndicatorDefinition.id == indicator_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="指标定义不存在")
    return row


def create_indicator(db: Session, user: User, payload: dict[str, Any]) -> PerformanceIndicatorDefinition:
    metric_key = (payload.get("metric_key") or "").strip()
    if not metric_key:
        raise HTTPException(status_code=422, detail="metric_key 必填")
    if db.query(PerformanceIndicatorDefinition).filter_by(metric_key=metric_key).first():
        raise HTTPException(status_code=409, detail="metric_key 已存在")
    scoring_type = payload["scoring_type"]
    handling_mode = payload["handling_mode"]
    data_source_code = _normalize_source(payload["data_source_code"])
    validate_handling_mode(handling_mode)
    validate_data_source(data_source_code)
    rule = payload.get("rule_config") or payload.get("rule_config_json")
    if isinstance(rule, str):
        rule = _loads(rule)
    validate_rule_config(scoring_type, rule)
    row = PerformanceIndicatorDefinition(
        metric_key=metric_key,
        name=payload["name"],
        department_id=payload.get("department_id"),
        job_title=payload.get("job_title"),
        scoring_type=scoring_type,
        default_target=payload.get("default_target"),
        unit=payload.get("unit") or "",
        data_source_code=data_source_code,
        handling_mode=handling_mode,
        rule_config_json=_dumps(rule),
        evidence_policy_json=_dumps(payload.get("evidence_policy") or payload.get("evidence_policy_json")),
        status=payload.get("status") or "draft",
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_indicator(db: Session, indicator_id: int, payload: dict[str, Any]) -> PerformanceIndicatorDefinition:
    row = get_indicator(db, indicator_id)
    if "name" in payload and payload["name"] is not None:
        row.name = payload["name"]
    if "department_id" in payload:
        row.department_id = payload["department_id"]
    if "job_title" in payload:
        row.job_title = payload["job_title"]
    if "default_target" in payload:
        row.default_target = payload["default_target"]
    if "unit" in payload and payload["unit"] is not None:
        row.unit = payload["unit"]
    scoring_type = payload.get("scoring_type", row.scoring_type)
    handling_mode = payload.get("handling_mode", row.handling_mode)
    data_source_code = _normalize_source(payload.get("data_source_code", row.data_source_code))
    if "scoring_type" in payload or "handling_mode" in payload or "data_source_code" in payload:
        validate_handling_mode(handling_mode)
        validate_data_source(data_source_code)
        row.scoring_type = scoring_type
        row.handling_mode = handling_mode
        row.data_source_code = data_source_code
    if "rule_config" in payload or "rule_config_json" in payload:
        rule = payload.get("rule_config")
        if rule is None:
            rule = payload.get("rule_config_json")
        if isinstance(rule, str):
            rule = _loads(rule)
        validate_rule_config(scoring_type, rule)
        row.rule_config_json = _dumps(rule)
    if "evidence_policy" in payload or "evidence_policy_json" in payload:
        ev = payload.get("evidence_policy")
        if ev is None:
            ev = payload.get("evidence_policy_json")
        row.evidence_policy_json = _dumps(ev)
    if "status" in payload and payload["status"]:
        row.status = payload["status"]
    db.commit()
    db.refresh(row)
    return row


def disable_indicator(db: Session, indicator_id: int) -> PerformanceIndicatorDefinition:
    return update_indicator(db, indicator_id, {"status": "disabled"})


def delete_indicator(db: Session, indicator_id: int) -> None:
    """删除指标定义。未进入考核的模板行一并移除；已进入考核的行保留快照并解开关联。"""
    row = get_indicator(db, indicator_id)
    items = (
        db.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.indicator_definition_id == row.id)
        .all()
    )
    item_ids = [it.id for it in items]
    referenced: set[int] = set()
    if item_ids:
        referenced = {
            tid
            for (tid,) in db.query(PerformanceAssessmentItem.template_item_id)
            .filter(PerformanceAssessmentItem.template_item_id.in_(item_ids))
            .distinct()
            if tid is not None
        }
    for it in items:
        if it.id in referenced:
            it.indicator_definition_id = None
        else:
            db.delete(it)
    db.flush()
    db.delete(row)
    db.commit()


def add_indicator_to_template(
    db: Session,
    *,
    template_id: int,
    indicator_id: int,
    weight: Decimal,
    order_no: int = 0,
) -> PerformanceTemplateItem:
    tpl = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if tpl is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    ind = get_indicator(db, indicator_id)
    rule = _loads(ind.rule_config_json) or {}
    # 满分：优先规则 cap / base；否则用请求 weight
    max_raw = rule.get("cap") or rule.get("base")
    max_points = Decimal(str(max_raw)) if max_raw is not None else weight
    score_rule = rule.get("type") or ("event_ledger" if ind.scoring_type == "bonus" else "points_sum")
    hint = rule.get("hint") or rule.get("note")
    item = PerformanceTemplateItem(
        template_id=tpl.id,
        order_no=order_no,
        name=ind.name,
        weight=max_points,
        data_source="system" if ind.handling_mode.startswith("system") else "manual",
        source_ref=ind.data_source_code,
        target_value=ind.default_target,
        score_rule=score_rule,
        hint=hint,
        metric_key=ind.metric_key,
        max_points=max_points if ind.scoring_type != "bonus" or max_raw is not None else None,
        rule_config_json=ind.rule_config_json,
        indicator_definition_id=ind.id,
        scoring_type=ind.scoring_type,
        unit=ind.unit or None,
        handling_mode=ind.handling_mode,
        evidence_policy_json=ind.evidence_policy_json,
    )
    # 讲师纯事件项：无单项满分
    if ind.scoring_type == "bonus" and max_raw is None:
        item.max_points = None
        item.weight = Decimal("0")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def seed_indicators_from_drafts(db: Session, *, created_by: Optional[int] = None) -> int:
    """将草稿中的指标幂等导入/刷新指标库，预置项状态为 active 可供模板选用。"""
    created = 0
    seen: set[str] = set()
    dept_cache: dict[str, Optional[int]] = {}
    for spec in FAMILIES:
        job = _FAMILY_JOB.get(spec["family_code"])
        if spec["family_code"].startswith("ONBOARD_"):
            job = "入职考核"
        dept_name = _FAMILY_DEPT_NAME.get(spec["family_code"])
        if dept_name and dept_name not in dept_cache:
            d = db.query(Department).filter(Department.name == dept_name).first()
            dept_cache[dept_name] = d.id if d else None
        department_id = dept_cache.get(dept_name) if dept_name else None
        for item in spec.get("items") or []:
            key = item["metric_key"]
            if key in seen:
                continue
            seen.add(key)
            rule = dict(item.get("rule") or {})
            if item.get("hint") and "hint" not in rule:
                rule["hint"] = item["hint"]
            scoring_type = _infer_scoring_type(rule, key)
            handling = _infer_handling(scoring_type, key)
            source = _infer_data_source(scoring_type, key)
            unit = rule.get("unit") or ""
            if not unit and scoring_type == "bonus":
                # 收入提成：+1分/100元；其余事件项：分/次
                if rule.get("per_amount") is not None:
                    unit = f"分/{rule['per_amount']}元"
                else:
                    unit = "分/次"
            # 加减分项：default_target 存情形文案，不要把单次分值当目标
            if scoring_type == "bonus":
                target = rule.get("event_type") or item.get("hint") or rule.get("target_note")
            else:
                target = (
                    rule.get("target")
                    or rule.get("target_personal")
                    or rule.get("target_per_project")
                    or rule.get("target_ratio")
                    or rule.get("target_note")
                )
            existing = db.query(PerformanceIndicatorDefinition).filter_by(metric_key=key).first()
            if existing:
                existing.name = item["name"]
                existing.job_title = job
                existing.department_id = department_id
                existing.scoring_type = scoring_type
                existing.default_target = str(target) if target is not None else None
                existing.unit = unit
                existing.data_source_code = source
                existing.handling_mode = handling
                existing.rule_config_json = _dumps(rule) if rule else None
                existing.status = "active"
                continue
            db.add(
                PerformanceIndicatorDefinition(
                    metric_key=key,
                    name=item["name"],
                    department_id=department_id,
                    job_title=job,
                    scoring_type=scoring_type,
                    default_target=str(target) if target is not None else None,
                    unit=unit,
                    data_source_code=source,
                    handling_mode=handling,
                    rule_config_json=_dumps(rule) if rule else None,
                    evidence_policy_json=None,
                    status="active",
                    created_by=created_by,
                )
            )
            created += 1
    if created or seen:
        db.flush()
    return created


def indicator_out(row: PerformanceIndicatorDefinition) -> dict[str, Any]:
    rule = _loads(row.rule_config_json) or {}
    max_raw = rule.get("cap") or rule.get("base")
    return {
        "id": row.id,
        "metric_key": row.metric_key,
        "name": row.name,
        "department_id": row.department_id,
        "job_title": row.job_title,
        "scoring_type": row.scoring_type,
        "default_target": row.default_target,
        "unit": row.unit or None,
        "max_points": str(max_raw) if max_raw is not None else None,
        "score_rule": rule.get("type"),
        "hint": rule.get("hint") or rule.get("note"),
        "data_source_code": row.data_source_code,
        "handling_mode": row.handling_mode,
        "rule_config": rule or None,
        "evidence_policy": _loads(row.evidence_policy_json),
        "status": row.status,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _job_title_code(name: str) -> str:
    mapping = {
        "市场业务": "market_sales",
        "讲师": "lecturer",
        "AI运营": "ai_ops",
        "内容运营": "content_ops",
        "品牌宣传": "brand",
        "直播主播": "live_host",
        "直播投放": "live_ads",
        "入职考核": "onboarding",
    }
    return mapping.get(name, name)


def build_configuration(db: Session, user: User) -> dict[str, Any]:
    assert_configuration_integrity()
    scope = resolve_data_scope(user, "kpi")
    q = db.query(Department)
    if scope == DataScope.COMPANY.value:
        depts = q.order_by(Department.id).all()
    elif scope == DataScope.DEPARTMENT.value:
        allowed = user_dept_scope(user)
        depts = q.filter(Department.id.in_(allowed or {-1})).order_by(Department.id).all()
    else:
        depts = []
        if user.department_id:
            d = db.query(Department).filter(Department.id == user.department_id).first()
            if d:
                depts = [d]

    departments = []
    for dept in depts:
        titles = (
            db.query(User.job_title)
            .filter(User.department_id == dept.id, User.job_title.isnot(None), User.job_title != "")
            .distinct()
            .all()
        )
        job_titles = [{"code": _job_title_code(t[0]), "name": t[0]} for t in titles if t[0]]
        departments.append({"id": dept.id, "name": dept.name, "job_titles": job_titles})

    return {
        "version": CONFIGURATION_VERSION,
        "departments": departments,
        "scoring_types": scoring_types_payload(),
        "data_sources": data_sources_payload(),
        "handling_modes": handling_modes_payload(),
    }
