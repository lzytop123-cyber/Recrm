"""我的待办。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.todo import TodoListOut
from app.services import todo as todo_service

router = APIRouter(prefix="/todos", tags=["我的待办"])


@router.get("", response_model=TodoListOut, summary="我的待办聚合")
def list_todos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return todo_service.list_my_todos(db, current_user)
