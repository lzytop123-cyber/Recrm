"""智能体 SSE 对话 API。"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated, Any, AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from sqlalchemy.orm import Session, joinedload

from app.agent.graph import get_agent_app
from app.api.deps import _compute_dept_scope_ids, get_current_user
from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.agent import (
    ChatRequest,
    ConfirmRequest,
    ConversationOut,
    HistoryMessageOut,
)
from app.services import agent_conversation as conv_service
from app.services.agent_memory import note_user_message

router = APIRouter(prefix="/agent", tags=["智能体"])
logger = logging.getLogger(__name__)


def _sse(event: str, data: Any) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _load_agent_user(db: Session, user_id: int) -> User:
    """流式期间专用会话加载用户（含 department / roles），避免请求 Session 提前关闭。"""
    user = (
        db.query(User)
        .options(
            joinedload(User.department),
            joinedload(User.roles).joinedload(Role.permissions),
        )
        .filter(User.id == user_id)
        .first()
    )
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已失效")
    user.dept_scope_ids = _compute_dept_scope_ids(db, user.department_id)  # type: ignore[attr-defined]
    return user


def _thread_config(user_id: int, conversation_id: str, db: Session, user: User) -> dict:
    return {
        "configurable": {
            "thread_id": f"user-{user_id}-{conversation_id}",
            "db": db,
            "user": user,
        },
        "recursion_limit": get_settings().agent_max_iterations,
    }


async def _interrupt_payload(config: dict) -> Optional[dict]:
    app = await get_agent_app()
    snapshot = await app.aget_state(config)
    interrupts = getattr(snapshot, "interrupts", None) or ()
    if not interrupts:
        return None
    value = getattr(interrupts[0], "value", None)
    return value if isinstance(value, dict) else {"raw": value}


async def _latest_assistant_text(config: dict) -> str:
    app = await get_agent_app()
    snapshot = await app.aget_state(config)
    messages = (snapshot.values or {}).get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return str(msg.content)
    return ""


async def _stream_graph(
    input_data: Any, config: dict, conversation_id: str
) -> AsyncIterator[str]:
    # invoke 失败时 agent_node 会直接塞 AIMessage，不会走 on_chat_model_stream
    had_content = False
    try:
        app = await get_agent_app()
        async for event in app.astream_events(input_data, config=config, version="v2"):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                text = getattr(chunk, "content", None) if chunk is not None else None
                if text:
                    had_content = True
                    yield _sse("message", {"type": "content", "text": text})
            elif kind == "on_tool_start":
                yield _sse(
                    "message",
                    {
                        "type": "tool_start",
                        "name": event.get("name"),
                        "args": (event.get("data") or {}).get("input", {}),
                    },
                )
            elif kind == "on_tool_end":
                raw = (event.get("data") or {}).get("output", "")
                yield _sse(
                    "message",
                    {
                        "type": "tool_end",
                        "name": event.get("name"),
                        "result": str(raw)[:500],
                    },
                )

        if not had_content:
            fallback = await _latest_assistant_text(config)
            if fallback:
                yield _sse("message", {"type": "content", "text": fallback})

        need = await _interrupt_payload(config)
        if need:
            yield _sse(
                "message",
                {
                    **need,
                    "type": "need_confirm",
                    "conversation_id": conversation_id,
                },
            )
        yield _sse("done", "[DONE]")
    except Exception:  # noqa: BLE001
        logger.exception("Agent graph stream failed")
        yield _sse("error", {"error": "智能助手处理失败，请稍后重试"})


@router.post("/chat", summary="SSE 流式对话")
async def chat(
    req: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if not get_settings().llm_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置 LLM_API_KEY，智能体不可用",
        )

    user_id = user.id
    conversation_id = req.conversation_id or str(uuid.uuid4())
    conv = conv_service.get_or_create(db, user_id, conversation_id, title=req.message[:40])
    conv_service.append_message(db, conv, role="user", content=req.message)
    note_user_message(db, user_id, req.message)
    db.commit()

    initial_state = {
        "messages": [HumanMessage(content=req.message)],
        "page_context": req.page_context,
        "conversation_id": conversation_id,
    }

    async def event_stream() -> AsyncIterator[str]:
        # StreamingResponse 返回后请求级 Session 会关闭，流内单独开会话
        stream_db = SessionLocal()
        try:
            stream_user = _load_agent_user(stream_db, user_id)
            config = _thread_config(user_id, conversation_id, stream_db, stream_user)
            yield _sse("message", {"type": "meta", "conversation_id": conversation_id})
            async for chunk in _stream_graph(initial_state, config, conversation_id):
                yield chunk
            text = await _latest_assistant_text(config)
            if text and not await _interrupt_payload(config):
                conv_row = conv_service.get_or_create(
                    stream_db, user_id, conversation_id, title=req.message[:40]
                )
                conv_service.append_message(
                    stream_db, conv_row, role="assistant", content=text
                )
                stream_db.commit()
        except HTTPException as exc:
            yield _sse("error", {"error": exc.detail})
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/confirm", summary="确认或取消写操作（SSE 续流）")
async def confirm(
    req: ConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if not get_settings().llm_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置 LLM_API_KEY，智能体不可用",
        )

    user_id = user.id
    conv_service.get_or_create(db, user_id, req.conversation_id)
    db.commit()
    resume_value = "confirmed" if req.confirmed else "cancelled"

    async def event_stream() -> AsyncIterator[str]:
        stream_db = SessionLocal()
        try:
            stream_user = _load_agent_user(stream_db, user_id)
            config = _thread_config(user_id, req.conversation_id, stream_db, stream_user)
            yield _sse("message", {"type": "meta", "conversation_id": req.conversation_id})
            async for chunk in _stream_graph(
                Command(resume=resume_value), config, req.conversation_id
            ):
                yield chunk
            text = await _latest_assistant_text(config)
            if text:
                conv_row = conv_service.get_or_create(stream_db, user_id, req.conversation_id)
                conv_service.append_message(
                    stream_db, conv_row, role="assistant", content=text
                )
                stream_db.commit()
        except HTTPException as exc:
            yield _sse("error", {"error": exc.detail})
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations", response_model=list[ConversationOut], summary="会话列表")
def list_conversations(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    items = conv_service.list_by_user(db, user.id)
    return [
        ConversationOut(
            id=c.public_id,
            title=c.title,
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
        )
        for c in items
    ]


@router.get(
    "/history/{conversation_id}",
    response_model=list[HistoryMessageOut],
    summary="会话历史",
)
def history(
    conversation_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    msgs = conv_service.get_messages(db, user.id, conversation_id)
    return [
        HistoryMessageOut(
            role=m.role,
            content=m.content,
            tool_calls=m.tool_calls,
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in msgs
    ]
