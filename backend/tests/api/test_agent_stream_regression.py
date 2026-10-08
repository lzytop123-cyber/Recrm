"""Agent streaming protocol, account checks and write permission regressions."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessage

from app.api.v1 import agent as agent_api
from app.core.security import create_access_token


def test_confirmation_event_keeps_wire_type(monkeypatch):
    payload = {
        "type": "confirm_write", "tool_name": "create_lead",
        "action_desc": "创建线索", "args": {"name": "test"},
    }

    class Graph:
        async def astream_events(self, *args, **kwargs):
            if False:
                yield {}

        async def aget_state(self, config):
            return SimpleNamespace(values={"messages": []}, interrupts=[SimpleNamespace(value=payload)])

    async def get_graph():
        return Graph()

    monkeypatch.setattr(agent_api, "get_agent_app", get_graph)

    async def collect():
        return [event async for event in agent_api._stream_graph({}, {}, "conversation")]

    events = asyncio.run(collect())
    data = json.loads(events[0].split("data: ", 1)[1])
    assert data["type"] == "need_confirm"
    assert data["conversation_id"] == "conversation"
    assert data["tool_name"] == "create_lead"
    assert events[-1] == "event: done\ndata: [DONE]\n\n"


def test_stream_user_reload_rejects_disabled_account(db_session, disabled_user):
    with pytest.raises(HTTPException) as exc:
        agent_api._load_agent_user(db_session, disabled_user.id)
    assert exc.value.status_code == 401


@pytest.mark.parametrize("method,url,body", [
    ("post", "/api/v1/agent/chat", {"message": "hello"}),
    ("post", "/api/v1/agent/confirm", {"conversation_id": "conversation", "confirmed": True}),
    ("get", "/api/v1/agent/conversations", None),
    ("get", "/api/v1/agent/history/conversation", None),
])
def test_disabled_account_cannot_use_agent(client, disabled_user, method, url, body):
    token = create_access_token(str(disabled_user.id))
    kwargs = {"headers": {"Authorization": f"Bearer {token}"}}
    if body is not None:
        kwargs["json"] = body
    assert getattr(client, method)(url, **kwargs).status_code == 401


def test_tool_execution_requires_permission(monkeypatch, db_session, active_user):
    from app.agent import graph

    class Tool:
        _required_permission = "project:manage"

        def invoke(self, args):
            pytest.fail("unauthorized tool must not run")

    monkeypatch.setitem(graph.TOOLS_MAP, "restricted_test_tool", Tool())
    result = graph.tool_node({"messages": [AIMessage(content="", tool_calls=[{
        "name": "restricted_test_tool", "id": "call", "args": {}, "type": "tool_call",
    }])]}, {"configurable": {"db": db_session, "user": active_user}})
    assert "project:manage" in json.loads(result["messages"][0].content)["error"]


def test_confirmation_discloses_every_write_action_and_cancel_skips_tools(monkeypatch):
    from app.agent import graph

    class WriteTool:
        _requires_confirmation = True

        def __init__(self, prompt):
            self._confirmation_prompt = prompt

    monkeypatch.setitem(graph.TOOLS_MAP, "write_one", WriteTool("first write"))
    monkeypatch.setitem(graph.TOOLS_MAP, "write_two", WriteTool("second write"))
    state = {"messages": [AIMessage(content="", tool_calls=[
        {"name": "write_one", "id": "one", "args": {"name": "first"}, "type": "tool_call"},
        {"name": "write_two", "id": "two", "args": {"name": "second"}, "type": "tool_call"},
    ])]}
    prompts = []

    def cancel(payload):
        prompts.append(payload)
        return "cancelled"

    monkeypatch.setattr(graph, "interrupt", cancel)
    result = graph.confirm_node(state)
    assert prompts[0]["actions"] == [
        {"tool_name": "write_one", "action_desc": "first write", "args": {"name": "first"}},
        {"tool_name": "write_two", "action_desc": "second write", "args": {"name": "second"}},
    ]
    assert {message.tool_call_id for message in result["messages"]} == {"one", "two"}
    assert graph.route_after_confirm(result) == "agent"


def test_model_failure_does_not_expose_exception(monkeypatch, db_session, active_user):
    from app.agent import graph

    def fail_llm(**kwargs):
        raise RuntimeError("secret-api-key http://private-host/debug")

    monkeypatch.setattr(graph, "get_llm", fail_llm)
    result = graph.agent_node({"messages": []}, {
        "configurable": {"db": db_session, "user": active_user},
    })
    text = result["messages"][0].content
    assert "secret-api-key" not in text
    assert "private-host" not in text
    assert text
