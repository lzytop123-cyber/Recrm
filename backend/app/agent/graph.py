"""LangGraph：agent ↔ confirm(写操作) ↔ tools。"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app.agent.llm import get_llm
from app.agent.prompts import build_system_prompt
from app.agent.runtime import agent_runtime
from app.agent.state import AgentState
from app.agent.tools import ALL_TOOLS
from app.agent.tools.base import confirmation_prompt, required_permission, requires_confirmation
from app.config import get_settings
from app.core.rbac import user_can
from app.services.agent_memory import load_memory

TOOLS_MAP = {t.name: t for t in ALL_TOOLS}

# 由 init_agent_app() 懒加载（AsyncPostgresSaver 需事件循环）
agent_app: Any = None
_checkpointer_cm: Any = None
_init_lock = asyncio.Lock()


def _postgres_conninfo(database_url: str) -> str | None:
    """SQLAlchemy DATABASE_URL → psycopg conninfo；非 Postgres 返回 None。"""
    url = (database_url or "").strip()
    for prefix in ("postgresql+psycopg://", "postgresql+asyncpg://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix) :]
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url
    return None


def _dept_name(user) -> str:
    # 避免 Session 已关闭时懒加载 department 抛 DetachedInstanceError
    try:
        from sqlalchemy import inspect as sa_inspect

        insp = sa_inspect(user)
        if insp.detached or "department" in insp.unloaded:
            return "未知"
        dept = user.department
    except Exception:  # noqa: BLE001
        return "未知"
    return getattr(dept, "name", None) or "未知"


def _runtime_from_config(config: RunnableConfig):
    conf = (config or {}).get("configurable") or {}
    db = conf.get("db")
    user = conf.get("user")
    if db is None or user is None:
        raise RuntimeError("agent config 缺少 db/user")
    return db, user


def _first_write_call(state: AgentState):
    last = state["messages"][-1]
    for call in getattr(last, "tool_calls", None) or []:
        fn = TOOLS_MAP.get(call["name"])
        if fn and requires_confirmation(fn):
            return call, fn
    return None, None


def agent_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    db, user = _runtime_from_config(config)
    with agent_runtime(db, user):
        system_msg = SystemMessage(
            content=build_system_prompt(
                user_name=user.real_name or user.username,
                department=_dept_name(user),
                page_context=state.get("page_context"),
                memory=load_memory(db, user.id),
            )
        )
        try:
            llm = get_llm(tools=ALL_TOOLS)
            response = llm.invoke([system_msg, *state["messages"]])
        except Exception as exc:  # noqa: BLE001 — 模型超时/网络错误回传给用户
            return {
                "messages": [
                    AIMessage(
                        content=f"大模型暂时不可用：{exc}。请稍后重试，或检查 LLM_API_KEY / 网络。"
                    )
                ]
            }
        return {"messages": [response]}


def confirm_node(state: AgentState) -> dict[str, Any]:
    """写操作确认：interrupt 挂起，等待 /confirm 恢复。"""
    call, fn = _first_write_call(state)
    if call is None or fn is None:
        return {}

    choice = interrupt(
        {
            "type": "confirm_write",
            "tool_name": call["name"],
            "action_desc": confirmation_prompt(fn),
            "args": call.get("args") or {},
        }
    )
    if choice == "confirmed":
        return {}

    last = state["messages"][-1]
    cancels = [
        ToolMessage(content="用户已取消操作", tool_call_id=c["id"])
        for c in (getattr(last, "tool_calls", None) or [])
    ]
    return {"messages": cancels}


def tool_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    db, user = _runtime_from_config(config)
    last = state["messages"][-1]
    out: list[ToolMessage] = []
    with agent_runtime(db, user):
        for call in getattr(last, "tool_calls", None) or []:
            fn = TOOLS_MAP.get(call["name"])
            if fn is None:
                result: Any = {"error": f"未知工具: {call['name']}"}
            else:
                perm = required_permission(fn)
                if perm and not user_can(user, perm):
                    result = {"error": f"当前用户无权限执行 {call['name']}（需要 {perm}）"}
                else:
                    try:
                        result = fn.invoke(call.get("args") or {})
                    except Exception as exc:  # noqa: BLE001
                        result = {"error": str(exc)}
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False, default=str)
            out.append(ToolMessage(content=result, tool_call_id=call["id"]))
    return {"messages": out}


def route_after_agent(state: AgentState) -> str:
    last = state["messages"][-1]
    if not (isinstance(last, AIMessage) and last.tool_calls):
        return END
    _, fn = _first_write_call(state)
    if fn is not None:
        return "confirm"
    return "tools"


def route_after_confirm(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, ToolMessage) and "取消" in (last.content or ""):
        return "agent"
    return "tools"


def build_graph(checkpointer: Any):
    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.add_node("confirm", confirm_node)
    g.set_entry_point("agent")
    g.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "confirm": "confirm", END: END},
    )
    g.add_conditional_edges(
        "confirm",
        route_after_confirm,
        {"tools": "tools", "agent": "agent"},
    )
    g.add_edge("tools", "agent")
    return g.compile(checkpointer=checkpointer)


async def init_agent_app() -> None:
    """懒加载：Postgres 时用 AsyncPostgresSaver（与业务库同库）；否则 MemorySaver。"""
    global agent_app, _checkpointer_cm
    if agent_app is not None:
        return

    async with _init_lock:
        if agent_app is not None:
            return

        conninfo = _postgres_conninfo(get_settings().database_url)
        if conninfo:
            try:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            except ImportError:
                agent_app = build_graph(MemorySaver())
                return
            _checkpointer_cm = AsyncPostgresSaver.from_conn_string(conninfo)
            checkpointer = await _checkpointer_cm.__aenter__()
            await checkpointer.setup()
            agent_app = build_graph(checkpointer)
            return

        agent_app = build_graph(MemorySaver())


async def get_agent_app():
    if agent_app is None:
        await init_agent_app()
    if agent_app is None:
        raise RuntimeError("智能体初始化失败")
    return agent_app


async def shutdown_agent_app() -> None:
    global agent_app, _checkpointer_cm
    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer_cm = None
    agent_app = None
