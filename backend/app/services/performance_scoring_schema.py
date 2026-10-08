"""计分类型与材料处理方式的统一 schema（配置接口与保存校验共用）。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import HTTPException

CONFIGURATION_VERSION = "2026-09-22.1"

ALLOWED_INPUT_TYPES = frozenset(
    {"text", "decimal", "boolean", "select", "data_field", "score_bands", "dimension_list"}
)

HANDLING_MODES: list[dict[str, str]] = [
    {"code": "system_auto", "name": "系统自动获取，员工核对"},
    {"code": "system_supplement", "name": "系统缺失时员工补充"},
    {"code": "employee_submit", "name": "员工主动提交"},
    {"code": "manager_score", "name": "主管评分，无需员工提交"},
]

SCORING_TYPES: list[dict[str, Any]] = [
    {
        "code": "quantity",
        "name": "数量型",
        "description": "按实际完成数量、目标数量和封顶规则计分",
        "field_schema": [
            {"key": "target_value", "label": "目标值", "input_type": "decimal", "required": True, "min": "0"},
            {"key": "unit", "label": "单位", "input_type": "text", "required": True},
            {
                "key": "calculation",
                "label": "计分方式",
                "input_type": "select",
                "required": True,
                "options": [
                    {"value": "proportional", "label": "按完成比例"},
                    {"value": "shortfall_deduction", "label": "按未完成数量扣分"},
                ],
            },
            {"key": "floor_points", "label": "最低分", "input_type": "decimal", "required": True, "min": "0"},
            {"key": "cap_at_max", "label": "是否封顶", "input_type": "boolean", "required": True},
        ],
    },
    {
        "code": "ratio",
        "name": "比例型",
        "description": "按分子、分母和目标比例计分",
        "field_schema": [
            {"key": "numerator_source", "label": "分子来源", "input_type": "data_field", "required": True},
            {"key": "denominator_source", "label": "分母来源", "input_type": "data_field", "required": True},
            {"key": "target_ratio", "label": "目标比例", "input_type": "decimal", "required": True, "min": "0"},
            {
                "key": "zero_denominator_policy",
                "label": "分母为0时",
                "input_type": "select",
                "required": True,
                "options": [
                    {"value": "missing", "label": "标记待补数据"},
                    {"value": "full_points", "label": "按制度记满分"},
                    {"value": "zero_points", "label": "按制度记0分"},
                ],
            },
        ],
    },
    {
        "code": "tier",
        "name": "分档型",
        "description": "配置连续且不重叠的分数区间",
        "field_schema": [
            {"key": "bands", "label": "分档规则", "input_type": "score_bands", "required": True},
        ],
    },
    {
        "code": "subjective",
        "name": "主观评分型",
        "description": "由指定角色按评分维度评价",
        "field_schema": [
            {
                "key": "reviewer_type",
                "label": "评分人",
                "input_type": "select",
                "required": True,
                "options": [
                    {"value": "manager", "label": "直属主管"},
                    {"value": "business_owner", "label": "业务负责人"},
                    {"value": "multi_reviewer", "label": "多人评分"},
                ],
            },
            {"key": "dimensions", "label": "评分维度", "input_type": "dimension_list", "required": True},
        ],
    },
    {
        "code": "bonus",
        "name": "加减分型",
        "description": "按已核实事件产生加分或扣分",
        "field_schema": [
            {"key": "event_type", "label": "事件类型", "input_type": "text", "required": True},
            {"key": "points_per_event", "label": "单次分值", "input_type": "decimal", "required": True},
            {"key": "monthly_cap", "label": "月度累计上限", "input_type": "decimal", "required": True},
        ],
    },
    {
        "code": "veto",
        "name": "一票否决型",
        "description": "满足经核实的触发条件后执行强制结果",
        "field_schema": [
            {"key": "trigger_condition", "label": "触发条件", "input_type": "text", "required": True},
            {
                "key": "result",
                "label": "触发结果",
                "input_type": "select",
                "required": True,
                "options": [
                    {"value": "metric_zero", "label": "本指标0分"},
                    {"value": "assessment_failed", "label": "考核结果不合格"},
                ],
            },
        ],
    },
]

# 已注册数据源（仅返回真实可用来源，不伪造）
DATA_SOURCES: list[dict[str, Any]] = [
    {
        "code": "crm_lead",
        "name": "CRM客户与线索",
        "supported_scoring_types": ["quantity", "ratio", "tier"],
        "handling_modes": ["system_auto", "system_supplement"],
        "available_fields": [
            {"code": "lead_count", "name": "线索数量", "value_type": "decimal"},
            {"code": "customer_industry", "name": "客户行业", "value_type": "text"},
            {"code": "signed_customer_count", "name": "签约客户数", "value_type": "decimal"},
        ],
    },
    {
        "code": "ledger.manual",
        "name": "手工台账",
        "supported_scoring_types": ["quantity", "ratio", "tier", "bonus"],
        "handling_modes": ["system_auto", "system_supplement", "employee_submit"],
        "available_fields": [
            {"code": "value", "name": "台账数值", "value_type": "decimal"},
        ],
    },
    {
        "code": "manager_review",
        "name": "主管评分",
        "supported_scoring_types": ["subjective"],
        "handling_modes": ["manager_score"],
        "available_fields": [],
    },
]

SCORING_TYPE_CODES = {x["code"] for x in SCORING_TYPES}
HANDLING_MODE_CODES = {x["code"] for x in HANDLING_MODES}
DATA_SOURCE_CODES = {x["code"] for x in DATA_SOURCES}


def scoring_types_payload() -> list[dict[str, Any]]:
    return deepcopy(SCORING_TYPES)


def handling_modes_payload() -> list[dict[str, str]]:
    return deepcopy(HANDLING_MODES)


def data_sources_payload() -> list[dict[str, Any]]:
    return deepcopy(DATA_SOURCES)


def assert_configuration_integrity() -> None:
    """配置自身不完整时禁止对外返回。"""
    if {x["code"] for x in SCORING_TYPES} != {
        "quantity",
        "ratio",
        "tier",
        "subjective",
        "bonus",
        "veto",
    }:
        raise HTTPException(status_code=500, detail={"code": "KPI_CONFIGURATION_INVALID", "message": "计分类型不完整"})
    for st in SCORING_TYPES:
        for field in st["field_schema"]:
            if field.get("input_type") not in ALLOWED_INPUT_TYPES:
                raise HTTPException(
                    status_code=500,
                    detail={"code": "KPI_CONFIGURATION_INVALID", "message": f"非法 input_type: {field.get('input_type')}"},
                )
            if field.get("input_type") == "select" and not field.get("options"):
                raise HTTPException(
                    status_code=500,
                    detail={
                        "code": "KPI_CONFIGURATION_INVALID",
                        "message": f"{st['code']}.{field['key']} 缺少 options",
                    },
                )


def validate_rule_config(scoring_type: str, rule_config: dict[str, Any] | None) -> None:
    if scoring_type not in SCORING_TYPE_CODES:
        raise HTTPException(status_code=422, detail=f"不支持的计分类型: {scoring_type}")
    if not rule_config:
        return
    schema = next(x for x in SCORING_TYPES if x["code"] == scoring_type)
    fields = {f["key"]: f for f in schema["field_schema"]}
    for key, field in fields.items():
        if field.get("required") and key not in rule_config:
            raise HTTPException(status_code=422, detail=f"计分规则缺少字段: {key}")
        if key in rule_config and field.get("input_type") == "select":
            allowed = {o["value"] for o in field.get("options") or []}
            if rule_config[key] not in allowed:
                raise HTTPException(status_code=422, detail=f"字段 {key} 取值无效")


def validate_handling_mode(mode: str) -> None:
    if mode not in HANDLING_MODE_CODES:
        raise HTTPException(status_code=422, detail=f"不支持的材料处理方式: {mode}")


def validate_data_source(code: str, scoring_type: str | None = None, handling_mode: str | None = None) -> None:
    if code not in DATA_SOURCE_CODES:
        raise HTTPException(status_code=422, detail=f"未注册的数据来源: {code}")
    src = next(x for x in DATA_SOURCES if x["code"] == code)
    if scoring_type and scoring_type not in src["supported_scoring_types"]:
        raise HTTPException(status_code=422, detail=f"数据来源 {code} 不支持计分类型 {scoring_type}")
    if handling_mode and handling_mode not in src["handling_modes"]:
        raise HTTPException(status_code=422, detail=f"数据来源 {code} 不支持处理方式 {handling_mode}")
