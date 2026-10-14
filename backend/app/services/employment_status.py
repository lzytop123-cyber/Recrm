"""任职状态归一化：飞书同步、手工录入的中英文写法统一成固定枚举。"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class EmploymentState(str, Enum):
    REGULAR = "regular"
    PROBATION = "probation"
    PENDING = "pending"
    LONG_LEAVE = "long_leave"
    RESIGNED = "resigned"


_ALIASES: dict[EmploymentState, frozenset[str]] = {
    EmploymentState.REGULAR: frozenset({"", "正式", "正式员工", "在职", "regular", "active", "formal"}),
    EmploymentState.PROBATION: frozenset({"试用", "试用期", "实习", "probation", "trial", "intern"}),
    EmploymentState.PENDING: frozenset({"待入职", "pending", "onboarding"}),
    EmploymentState.LONG_LEAVE: frozenset({"长期休假", "休假", "停薪留职", "long_leave"}),
    EmploymentState.RESIGNED: frozenset({"离职", "已离职", "resigned", "inactive"}),
}

# 未命中精确写法时按关键字兜底；顺序即优先级
_KEYWORDS: tuple[tuple[str, EmploymentState], ...] = (
    ("离职", EmploymentState.RESIGNED),
    ("待入职", EmploymentState.PENDING),
    ("休假", EmploymentState.LONG_LEAVE),
    ("停薪", EmploymentState.LONG_LEAVE),
    ("试用", EmploymentState.PROBATION),
    ("实习", EmploymentState.PROBATION),
)


def employment_state(status: Optional[str], *, is_active: bool = True) -> EmploymentState:
    """账号停用一律视为离职；其余按状态文字映射，未知写法按正式处理。"""
    if not is_active:
        return EmploymentState.RESIGNED
    text = (status or "").strip().lower()
    for state, words in _ALIASES.items():
        if text in words:
            return state
    for keyword, state in _KEYWORDS:
        if keyword in text:
            return state
    return EmploymentState.REGULAR


def is_resigned(status: Optional[str], *, is_active: bool = True) -> bool:
    return employment_state(status, is_active=is_active) is EmploymentState.RESIGNED
