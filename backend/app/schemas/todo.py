"""我的待办聚合。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TodoItemOut(BaseModel):
    id: str
    category: str
    category_label: str
    title: str
    subtitle: str = ""
    status_label: str = ""
    urgency: str = "normal"
    path: str
    due_at: Optional[datetime] = None


class TodoCounts(BaseModel):
    approval: int = 0
    ticket: int = 0
    lead: int = 0
    task: int = 0
    schedule: int = 0
    resource: int = 0


class TodoListOut(BaseModel):
    total: int = 0
    counts: TodoCounts = Field(default_factory=TodoCounts)
    items: list[TodoItemOut] = Field(default_factory=list)
    partial_errors: list[str] = Field(default_factory=list)
