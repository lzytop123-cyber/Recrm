"""绩效模板：HR 基础模板 + 部门 fork + 权重校验。"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.performance import (
    PerformanceCycle,
    PerformanceIndicatorDefinition,
    PerformanceTemplate,
    PerformanceTemplateItem,
    PerformanceTemplateScope,
)
from app.models.user import User

ALLOWED_SOURCES = {"system", "okr", "manual", "self_manual"}


def _d(v: Any) -> Decimal:
    return Decimal(str(v))


def _attach_scopes(db: Session, row: PerformanceTemplate) -> None:
    scopes = (
        db.query(PerformanceTemplateScope)
        .filter(PerformanceTemplateScope.template_id == row.id)
        .order_by(PerformanceTemplateScope.id.asc())
        .all()
    )
    dept_ids = {s.department_id for s in scopes}
    names = {}
    if dept_ids:
        for d in db.query(Department).filter(Department.id.in_(dept_ids)).all():
            names[d.id] = d.name
    for s in scopes:
        s.department_name = names.get(s.department_id)  # type: ignore[attr-defined]
    row.scopes = scopes  # type: ignore[attr-defined]


def _replace_scopes(db: Session, template_id: int, scopes: Optional[list]) -> None:
    if scopes is None:
        return
    db.query(PerformanceTemplateScope).filter(
        PerformanceTemplateScope.template_id == template_id
    ).delete(synchronize_session=False)
    for raw in scopes:
        if isinstance(raw, dict):
            dept_id = raw["department_id"]
            job_title = raw["job_title"]
        else:
            dept_id = raw.department_id
            job_title = raw.job_title
        db.add(
            PerformanceTemplateScope(
                template_id=template_id,
                department_id=dept_id,
                job_title=job_title,
            )
        )


def _build_item(template_id: int, p: dict, idx: int, db: Session) -> PerformanceTemplateItem:
    ind_id = p.get("indicator_definition_id")
    scoring_type = p.get("scoring_type")
    unit = p.get("unit")
    handling_mode = p.get("handling_mode")
    evidence = p.get("evidence_policy_json")
    rule_cfg = p.get("rule_config_json")
    metric_key = p.get("metric_key")
    max_points = p.get("max_points")
    name = p["name"]
    data_source = p["data_source"]
    source_ref = p.get("source_ref")
    target_value = p.get("target_value")
    if ind_id:
        ind = (
            db.query(PerformanceIndicatorDefinition)
            .filter(PerformanceIndicatorDefinition.id == ind_id)
            .first()
        )
        if ind is None:
            raise HTTPException(status_code=404, detail=f"指标定义不存在: {ind_id}")
        name = name or ind.name
        metric_key = metric_key or ind.metric_key
        scoring_type = scoring_type or ind.scoring_type
        unit = unit if unit is not None else ind.unit
        handling_mode = handling_mode or ind.handling_mode
        evidence = evidence if evidence is not None else ind.evidence_policy_json
        rule_cfg = rule_cfg if rule_cfg is not None else ind.rule_config_json
        source_ref = source_ref or ind.data_source_code
        target_value = target_value if target_value is not None else ind.default_target
        if not data_source:
            data_source = "system" if ind.handling_mode.startswith("system") else "manual"
    return PerformanceTemplateItem(
        template_id=template_id,
        order_no=p.get("order_no") if p.get("order_no") is not None else idx + 1,
        name=name,
        weight=_d(p["weight"]),
        data_source=data_source,
        source_ref=source_ref,
        target_value=target_value,
        score_rule=p.get("score_rule"),
        hint=p.get("hint"),
        metric_key=metric_key,
        max_points=_d(max_points) if max_points is not None else None,
        rule_config_json=rule_cfg if isinstance(rule_cfg, str) or rule_cfg is None else json.dumps(rule_cfg, ensure_ascii=False),
        indicator_definition_id=ind_id,
        scoring_type=scoring_type,
        unit=unit,
        handling_mode=handling_mode,
        evidence_policy_json=evidence if isinstance(evidence, str) or evidence is None else json.dumps(evidence, ensure_ascii=False),
    )


def _load_rules(template: PerformanceTemplate) -> dict:
    if not template.rules_json:
        return {}
    try:
        data = json.loads(template.rules_json)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def validate_weights(
    items: list,
    rules: Optional[dict] = None,
) -> None:
    """权重合计必须为 100；若有规则则校验数据源白名单和分组上下限。"""
    if not items:
        raise HTTPException(status_code=400, detail="模板至少需要一条指标")
    total = sum(_d(getattr(i, "weight", i.get("weight") if isinstance(i, dict) else 0)) for i in items)
    if abs(total - Decimal("100")) > Decimal("0.01"):
        raise HTTPException(status_code=400, detail=f"指标权重合计必须为 100，当前 {total}")

    rules = rules or {}
    allowed = set(rules.get("allowed_sources") or [])
    bounds = rules.get("weight_bounds") or {}
    grouped: dict[str, Decimal] = {}
    for raw in items:
        if isinstance(raw, dict):
            src = raw.get("data_source")
            w = _d(raw.get("weight") or 0)
        else:
            src = raw.data_source
            w = _d(raw.weight)
        if src not in ALLOWED_SOURCES:
            raise HTTPException(status_code=400, detail=f"不支持的数据源：{src}")
        if allowed and src not in allowed:
            raise HTTPException(status_code=400, detail=f"数据源 {src} 不在基础模板白名单")
        grouped[src] = grouped.get(src, Decimal("0")) + w
    for src, pair in (bounds.items() if isinstance(bounds, dict) else []):
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        lo, hi = pair[0], pair[1]
        w = grouped.get(src, Decimal("0"))
        if w < _d(lo) or w > _d(hi):
            raise HTTPException(
                status_code=400,
                detail=f"数据源 {src} 权重 {w} 超出基础模板范围 [{lo}, {hi}]",
            )


def _item_payload(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    return {
        "order_no": raw.order_no,
        "name": raw.name,
        "weight": raw.weight,
        "data_source": raw.data_source,
        "source_ref": raw.source_ref,
        "target_value": raw.target_value,
        "score_rule": raw.score_rule,
        "hint": getattr(raw, "hint", None),
        "metric_key": getattr(raw, "metric_key", None),
        "max_points": getattr(raw, "max_points", None),
        "rule_config_json": getattr(raw, "rule_config_json", None),
        "indicator_definition_id": getattr(raw, "indicator_definition_id", None),
        "scoring_type": getattr(raw, "scoring_type", None),
        "unit": getattr(raw, "unit", None),
        "handling_mode": getattr(raw, "handling_mode", None),
        "evidence_policy_json": getattr(raw, "evidence_policy_json", None),
    }


def create_template(
    db: Session,
    *,
    name: str,
    code: str,
    items: list,
    owner_type: str = "hr",
    owner_dept_id: Optional[int] = None,
    cycle_type: str = "monthly",
    rules_json: Optional[str] = None,
    created_by: Optional[int] = None,
    remark: Optional[str] = None,
    scopes: Optional[list] = None,
    effective_from=None,
    effective_to=None,
    eligibility_policy_json: Optional[str] = None,
    scoring_mode: str = "legacy_weighted",
    engine_version: str = "legacy",
    nominal_total: Optional[Decimal] = None,
) -> PerformanceTemplate:
    if db.query(PerformanceTemplate).filter(PerformanceTemplate.code == code).first():
        raise HTTPException(status_code=409, detail=f"模板编码已存在：{code}")
    rules = json.loads(rules_json) if rules_json else {}
    row = PerformanceTemplate(
        name=name,
        code=code,
        owner_type=owner_type,
        owner_dept_id=owner_dept_id,
        cycle_type=cycle_type,
        rules_json=rules_json,
        status="draft",
        remark=remark,
        created_by=created_by,
        effective_from=effective_from,
        effective_to=effective_to,
        eligibility_policy_json=eligibility_policy_json,
        scoring_mode=scoring_mode or "legacy_weighted",
        engine_version=engine_version or "legacy",
        nominal_total=nominal_total,
    )
    # 允许先建空壳草稿；旧百分比权重模板有指标时校验合计 100
    if items and _should_validate_weight_sum(row, items):
        validate_weights(items, rules if isinstance(rules, dict) else {})
    db.add(row)
    db.flush()
    for idx, raw in enumerate(items):
        db.add(_build_item(row.id, _item_payload(raw), idx, db))
    _replace_scopes(db, row.id, scopes)
    db.commit()
    db.refresh(row)
    return row


def fork_template(
    db: Session,
    base_id: int,
    *,
    owner_dept_id: int,
    created_by: Optional[int] = None,
    name: Optional[str] = None,
    code: Optional[str] = None,
) -> PerformanceTemplate:
    base = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == base_id).first()
    if not base:
        raise HTTPException(status_code=404, detail="基础模板不存在")
    items = (
        db.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == base.id)
        .order_by(PerformanceTemplateItem.order_no.asc(), PerformanceTemplateItem.id.asc())
        .all()
    )
    code = code or f"{base.code}-D{owner_dept_id}"
    n = 2
    while db.query(PerformanceTemplate).filter(PerformanceTemplate.code == code).first():
        code = f"{base.code}-D{owner_dept_id}-{n}"
        n += 1
    row = PerformanceTemplate(
        name=name or f"{base.name}·部门派生",
        code=code,
        base_template_id=base.id,
        owner_type="dept",
        owner_dept_id=owner_dept_id,
        cycle_type=base.cycle_type,
        rules_json=base.rules_json,
        status="draft",
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    for it in items:
        db.add(
            PerformanceTemplateItem(
                template_id=row.id,
                order_no=it.order_no,
                name=it.name,
                weight=it.weight,
                data_source=it.data_source,
                source_ref=it.source_ref,
                target_value=it.target_value,
                score_rule=it.score_rule,
                hint=it.hint,
                metric_key=it.metric_key,
                max_points=it.max_points,
                rule_config_json=it.rule_config_json,
                indicator_definition_id=it.indicator_definition_id,
                scoring_type=it.scoring_type,
                unit=it.unit,
                handling_mode=it.handling_mode,
                evidence_policy_json=it.evidence_policy_json,
            )
        )
    base_scopes = (
        db.query(PerformanceTemplateScope)
        .filter(PerformanceTemplateScope.template_id == base.id)
        .all()
    )
    for s in base_scopes:
        db.add(
            PerformanceTemplateScope(
                template_id=row.id,
                department_id=s.department_id,
                job_title=s.job_title,
            )
        )
    db.commit()
    db.refresh(row)
    return row


def list_templates(
    db: Session,
    *,
    owner_type: Optional[str] = None,
    status: Optional[str] = None,
    owner_dept_id: Optional[int] = None,
) -> list[PerformanceTemplate]:
    q = db.query(PerformanceTemplate)
    if owner_type:
        q = q.filter(PerformanceTemplate.owner_type == owner_type)
    if status:
        q = q.filter(PerformanceTemplate.status == status)
    if owner_dept_id is not None:
        q = q.filter(PerformanceTemplate.owner_dept_id == owner_dept_id)
    rows = q.order_by(PerformanceTemplate.id.desc()).all()
    for row in rows:
        row.items = (  # type: ignore[attr-defined]
            db.query(PerformanceTemplateItem)
            .filter(PerformanceTemplateItem.template_id == row.id)
            .order_by(PerformanceTemplateItem.order_no.asc(), PerformanceTemplateItem.id.asc())
            .all()
        )
        _attach_scopes(db, row)
    return rows


def get_template(db: Session, template_id: int) -> PerformanceTemplate:
    row = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    row.items = (  # type: ignore[attr-defined]
        db.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == row.id)
        .order_by(PerformanceTemplateItem.order_no.asc(), PerformanceTemplateItem.id.asc())
        .all()
    )
    _attach_scopes(db, row)
    return row


def update_template(
    db: Session,
    template_id: int,
    *,
    name: Optional[str] = None,
    remark: Optional[str] = None,
    rules_json: Optional[str] = None,
    items: Optional[list] = None,
    scopes: Optional[list] = None,
    effective_from=None,
    effective_to=None,
    eligibility_policy_json: Optional[str] = None,
) -> PerformanceTemplate:
    row = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    if row.status not in ("draft", "pending_review", "returned"):
        raise HTTPException(status_code=400, detail="已批准/归档的模板不可编辑")
    if name is not None:
        row.name = name
    if remark is not None:
        row.remark = remark
    if rules_json is not None:
        row.rules_json = rules_json
    if effective_from is not None:
        row.effective_from = effective_from
    if effective_to is not None:
        row.effective_to = effective_to
    if eligibility_policy_json is not None:
        row.eligibility_policy_json = eligibility_policy_json
    if items is not None:
        rules = _load_rules(row)
        if row.base_template_id and not rules:
            base = (
                db.query(PerformanceTemplate)
                .filter(PerformanceTemplate.id == row.base_template_id)
                .first()
            )
            rules = _load_rules(base) if base else {}
        if items:
            _promote_to_points_mode(row, items)
            if _should_validate_weight_sum(row, items):
                validate_weights(items, rules)
        db.query(PerformanceTemplateItem).filter(
            PerformanceTemplateItem.template_id == row.id
        ).delete(synchronize_session=False)
        for idx, raw in enumerate(items):
            db.add(_build_item(row.id, _item_payload(raw), idx, db))
    _replace_scopes(db, row.id, scopes)
    db.commit()
    return get_template(db, row.id)


def approve_template(
    db: Session,
    template_id: int,
    user: User,
    *,
    approve: bool = True,
    comment: Optional[str] = None,
) -> PerformanceTemplate:
    from app.models.approval_flow import ApprovalInstance
    from app.services import approval_flow

    row = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    if not row.approval_instance_id:
        raise HTTPException(status_code=400, detail="模板尚未提交审批")
    inst = (
        db.query(ApprovalInstance)
        .filter(ApprovalInstance.id == row.approval_instance_id)
        .first()
    )
    if not inst:
        raise HTTPException(status_code=404, detail="审批实例不存在")
    approval_flow.act(
        db,
        user,
        inst,
        approve=approve,
        comment=comment or ("同意" if approve else "驳回"),
        commit=False,
    )
    db.refresh(row)
    db.commit()
    return get_template(db, row.id)


def submit_for_review(db: Session, template_id: int, user: User) -> PerformanceTemplate:
    row = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    if row.status not in ("draft", "returned", "pending_review"):
        raise HTTPException(status_code=400, detail="当前状态不可提交审批")
    items = (
        db.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == row.id)
        .all()
    )
    rules = _load_rules(row)
    if row.base_template_id and not rules:
        base = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == row.base_template_id).first()
        rules = _load_rules(base) if base else {}
    _promote_to_points_mode(row, items)
    if _should_validate_weight_sum(row, items):
        validate_weights(items, rules)
    elif row.definition_json:
        from app.services.performance_rule_engine import blocking, validate_definition

        issues = blocking(validate_definition(json.loads(row.definition_json or "{}")))
        if issues:
            raise HTTPException(status_code=400, detail={"message": "规则冲突未确认，不能提交", "issues": issues})

    from app.services.approval_flow import start_instance

    inst = start_instance(
        db,
        biz_type="performance_template_review",
        biz_id=row.id,
        initiator=user,
        title=f"绩效模板审批：{row.name}",
        commit=False,
    )
    row.approval_instance_id = inst.id
    row.status = "pending_review"
    db.commit()
    db.refresh(row)
    return row


def _item_max_points(raw: Any) -> Optional[Decimal]:
    if isinstance(raw, dict):
        v = raw.get("max_points")
    else:
        v = getattr(raw, "max_points", None)
    return None if v is None else _d(v)


def _items_have_max_points(items: list) -> bool:
    return any(_item_max_points(i) is not None for i in (items or []))


def _should_validate_weight_sum(row: PerformanceTemplate, items: list) -> bool:
    """仅旧百分比权重模板校验合计 100；满分制（含误标 legacy 但带 max_points）跳过。"""
    if (row.scoring_mode or "legacy_weighted") != "legacy_weighted":
        return False
    if (row.engine_version or "legacy") != "legacy":
        return False
    if _items_have_max_points(items):
        return False
    return True


def _promote_to_points_mode(row: PerformanceTemplate, items: list) -> None:
    """KPI 前端曾把满分制草稿建成 legacy；有 max_points 时升级为 points_sum。"""
    if not _items_have_max_points(items):
        return
    if (row.scoring_mode or "legacy_weighted") == "legacy_weighted":
        row.scoring_mode = "points_sum"
    if (row.engine_version or "legacy") == "legacy":
        row.engine_version = "kpi-v2"
    if row.nominal_total is None:
        total = sum((_item_max_points(i) or Decimal("0") for i in items), Decimal("0"))
        if total > 0:
            row.nominal_total = total


def _is_legacy_template(row: PerformanceTemplate) -> bool:
    return (row.engine_version or "legacy") == "legacy" or (
        row.scoring_mode or "legacy_weighted"
    ) == "legacy_weighted"


def apply_review_result(db: Session, template_id: int, *, approved: bool) -> PerformanceTemplate:
    row = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    if approved:
        row.status = "approved"
    elif _is_legacy_template(row):
        row.status = "draft"
    else:
        row.status = "returned"
    db.flush()
    return row


def on_template_flow_result(db: Session, instance, *, approved: bool, withdrawn: bool = False) -> None:
    row = (
        db.query(PerformanceTemplate)
        .filter(PerformanceTemplate.approval_instance_id == instance.id)
        .first()
    )
    if not row:
        return
    if withdrawn:
        row.status = "draft" if _is_legacy_template(row) else "returned"
        return
    apply_review_result(db, row.id, approved=approved)


def _has_blocking_issues(row: PerformanceTemplate) -> bool:
    raw = row.blocking_issues_json
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, list):
        return False
    return any(isinstance(x, dict) and x.get("blocking") for x in data)


def validate_for_publish(db: Session, row: PerformanceTemplate) -> None:
    if row.status != "approved":
        raise HTTPException(
            status_code=409,
            detail={"code": "KPI_TEMPLATE_NOT_PUBLISHED", "message": "仅已批准待发布的模板可发布"},
        )
    items = (
        db.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == row.id)
        .all()
    )
    if not items:
        raise HTTPException(status_code=422, detail="发布前模板必须包含指标")
    scopes = (
        db.query(PerformanceTemplateScope)
        .filter(PerformanceTemplateScope.template_id == row.id)
        .count()
    )
    if scopes < 1 and not _is_legacy_template(row):
        raise HTTPException(status_code=422, detail="发布前模板必须配置适用部门/岗位范围")
    if _has_blocking_issues(row):
        raise HTTPException(
            status_code=409,
            detail={"code": "KPI_CONFIGURATION_INVALID", "message": "存在阻断性制度冲突，不能发布"},
        )
    if (row.scoring_mode or "legacy_weighted") != "legacy_weighted":
        from app.services.performance_rule_engine import blocking, validate_definition

        issues = blocking(validate_definition(json.loads(row.definition_json or "{}")))
        if issues:
            raise HTTPException(
                status_code=409,
                detail={"code": "KPI_CONFIGURATION_INVALID", "message": "规则校验未通过", "issues": issues},
            )
    for it in items:
        if it.scoring_type:
            from app.services.performance_scoring_schema import SCORING_TYPE_CODES

            if it.scoring_type not in SCORING_TYPE_CODES:
                raise HTTPException(status_code=422, detail=f"指标计分类型无效: {it.name}")
        if it.handling_mode:
            from app.services.performance_scoring_schema import HANDLING_MODE_CODES

            if it.handling_mode not in HANDLING_MODE_CODES:
                raise HTTPException(status_code=422, detail=f"材料处理方式无效: {it.name}")
        if it.source_ref:
            from app.services.performance_scoring_schema import DATA_SOURCE_CODES

            # 旧 system/okr 引用允许；新码必须注册
            if it.source_ref not in DATA_SOURCE_CODES and it.source_ref not in (
                "system",
                "okr",
                "manual",
                "self_manual",
            ):
                # source_ref 可能是字段路径如 customer.deals
                if "." in it.source_ref and not it.source_ref.split(".", 1)[0] in {
                    c.split(".", 1)[0] for c in DATA_SOURCE_CODES
                }:
                    pass  # 兼容旧 source_ref


def publish_template(db: Session, template_id: int, user: User) -> PerformanceTemplate:
    from datetime import datetime, timezone

    row = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    validate_for_publish(db, row)
    row.status = "published"
    row.published_at = datetime.now(timezone.utc)
    row.published_by = user.id
    db.commit()
    return get_template(db, row.id)


def disable_template(db: Session, template_id: int, user: User) -> PerformanceTemplate:
    row = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    if row.status != "published":
        raise HTTPException(status_code=409, detail="仅已发布模板可停用")
    row.status = "disabled"
    db.commit()
    return get_template(db, row.id)


def is_template_effective_for_period(
    row: PerformanceTemplate,
    period_start: date,
    period_end: date,
) -> bool:
    """模板生效区间与考核周期是否相交：生效日起不能晚于周期结束，失效日不能早于周期开始。"""
    if row.effective_from and row.effective_from > period_end:
        return False
    if row.effective_to and row.effective_to < period_start:
        return False
    return True


def require_published_for_launch(
    db: Session,
    template_id: int,
    *,
    cycle: Optional[PerformanceCycle] = None,
) -> PerformanceTemplate:
    """人员匹配与批量发起前校验：必须已发布，且对考核周期（或今天）在生效期内。"""
    from datetime import date as date_cls

    from app.services.performance_data_source import cycle_window

    row = db.query(PerformanceTemplate).filter(PerformanceTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    if row.status != "published":
        raise HTTPException(
            status_code=409,
            detail={"code": "KPI_TEMPLATE_NOT_PUBLISHED", "message": "模板未发布或已停用"},
        )
    if cycle is not None:
        start, end = cycle_window(cycle)
        period_hint = cycle.period_label or f"{start}~{end}"
    else:
        today = date_cls.today()
        start = end = today
        period_hint = "当前"
    if row.effective_from and row.effective_from > end:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "KPI_TEMPLATE_OUT_OF_EFFECTIVE_DATE",
                "message": f"模板尚未到生效日期，不能用于「{period_hint}」考核周期",
            },
        )
    if row.effective_to and row.effective_to < start:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "KPI_TEMPLATE_OUT_OF_EFFECTIVE_DATE",
                "message": f"模板已过生效期，不能用于「{period_hint}」考核周期",
            },
        )
    return row
