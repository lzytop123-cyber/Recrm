"""跨会话记忆：从用户原话里摘稳定事实，下次任何会话都放进系统提示。"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.agent import AgentMemory

_MAX = 20
# ponytail: 只认用户原话里的固定说法，不让模型自己总结，避免把编造写进记忆。
_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("记住", re.compile(r"(?:请)?记住[：:\s]*([^。！？\n]{2,80})")),
    ("我负责", re.compile(r"(我负责[^。！？\n]{1,40})")),
    ("我习惯", re.compile(r"(我习惯[^。！？\n]{1,40})")),
    ("我偏好", re.compile(r"(我偏好[^。！？\n]{1,40})")),
    ("我希望", re.compile(r"(我希望[^。！？\n]{1,40})")),
    ("我是", re.compile(r"(我是(?![不否])[^。！？\n]{1,20})")),
]


def extract_facts(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for key, pattern in _RULES:
        for match in pattern.finditer(text or ""):
            fact = match.group(1).strip(" ，,。")
            item = (fact if key == "记住" else key, fact)
            if fact and item not in found:
                found.append(item)
    return found


def merge_facts(old: str, incoming: list[tuple[str, str]]) -> str:
    rows: list[tuple[str, str]] = []
    for line in (old or "").splitlines():
        text = line.strip()
        if text:
            rows.append((_key_of(text), text))
    for key, fact in incoming:
        rows = [(k, v) for k, v in rows if k != key]
        rows.append((key, fact))
    return "\n".join(fact for _, fact in rows[-_MAX:])


def _key_of(fact: str) -> str:
    for key, _ in _RULES:
        if key != "记住" and fact.startswith(key):
            return key
    return fact


def load_memory(db: Session, user_id: int) -> str:
    row = db.query(AgentMemory).filter(AgentMemory.user_id == user_id).first()
    return (row.content or "").strip() if row else ""


def note_user_message(db: Session, user_id: int, text: str) -> str:
    incoming = extract_facts(text)
    if not incoming:
        return load_memory(db, user_id)
    row = db.query(AgentMemory).filter(AgentMemory.user_id == user_id).first()
    content = merge_facts(row.content if row else "", incoming)
    if row is None:
        row = AgentMemory(user_id=user_id, content=content)
        db.add(row)
    else:
        row.content = content
    db.commit()
    return content
