"""请求级运行时：把当前 db/user 注入工具（不必让 LLM 填 user_id）。"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.models.user import User

_db: ContextVar[Optional[Session]] = ContextVar("agent_db", default=None)
_user: ContextVar[Optional[User]] = ContextVar("agent_user", default=None)


@contextmanager
def agent_runtime(db: Session, user: User) -> Iterator[None]:
    tok_db = _db.set(db)
    tok_user = _user.set(user)
    try:
        yield
    finally:
        _db.reset(tok_db)
        _user.reset(tok_user)


def require_db() -> Session:
    db = _db.get()
    if db is None:
        raise RuntimeError("agent runtime: db 未设置")
    return db


def require_user() -> User:
    user = _user.get()
    if user is None:
        raise RuntimeError("agent runtime: user 未设置")
    return user
