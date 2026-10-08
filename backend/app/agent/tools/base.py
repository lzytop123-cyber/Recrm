"""工具标记：写操作需人工确认 + 权限兜底。"""
from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def write_operation(
    confirmation_prompt: str, *, permission: Optional[str] = None
) -> Callable[[F], F]:
    """标记为写操作；LangGraph 在执行前 interrupt 等待确认。
    permission 非空则在执行前查 RBAC，越权直接返回 error。
    """

    def decorator(func: F) -> F:
        func._requires_confirmation = True  # type: ignore[attr-defined]
        func._confirmation_prompt = confirmation_prompt  # type: ignore[attr-defined]
        func._required_permission = permission  # type: ignore[attr-defined]
        return func

    return decorator


def requires_confirmation(tool: Any) -> bool:
    return bool(getattr(tool, "_requires_confirmation", False))


def confirmation_prompt(tool: Any) -> str:
    return str(getattr(tool, "_confirmation_prompt", "确认执行该写操作？"))


def required_permission(tool: Any) -> Optional[str]:
    return getattr(tool, "_required_permission", None)
