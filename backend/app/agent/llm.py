"""LLM 客户端（复用现有 DeepSeek 配置）。"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from langchain_openai import ChatOpenAI

from app.config import get_settings


def get_llm(*, tools: Optional[Sequence[Any]] = None) -> ChatOpenAI:
    settings = get_settings()
    if not settings.llm_enabled:
        raise RuntimeError("未配置 LLM_API_KEY，无法启动智能体")

    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0.1,
        streaming=True,
        max_tokens=2000,
        timeout=settings.llm_timeout_seconds,
        max_retries=1,
    )
    if tools:
        return llm.bind_tools(list(tools))
    return llm
