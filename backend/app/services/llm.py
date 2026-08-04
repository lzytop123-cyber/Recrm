"""
DeepSeek 云 API 客户端（OpenAI 兼容 Chat Completions）。
Key 未配置时由调用方走检索回退，本模块不默认启用。
"""
from __future__ import annotations

from typing import Any, List, Mapping

import httpx

from app.config import get_settings


class LlmError(Exception):
    """大模型调用失败（超时、非 2xx、空内容等）。"""


def is_llm_configured() -> bool:
    return get_settings().llm_enabled


def chat_completion(messages: List[Mapping[str, str]], *, temperature: float = 0.2) -> str:
    """调用 chat/completions，返回 assistant 文本。失败抛 LlmError。"""
    settings = get_settings()
    if not settings.llm_enabled:
        raise LlmError("未配置 LLM_API_KEY")

    base = settings.llm_base_url.rstrip("/")
    url = f"{base}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": list(messages),
        "temperature": temperature,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key.strip()}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise LlmError("大模型请求超时") from exc
    except httpx.HTTPError as exc:
        raise LlmError(f"大模型网络错误: {exc}") from exc

    if resp.status_code >= 400:
        detail = (resp.text or "")[:200]
        raise LlmError(f"大模型返回 {resp.status_code}: {detail}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LlmError("大模型响应格式无效") from exc

    text = (content or "").strip()
    if not text:
        raise LlmError("大模型返回空内容")
    return text
