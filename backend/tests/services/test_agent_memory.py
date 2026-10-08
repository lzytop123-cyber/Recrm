"""跨会话记忆。"""
from app.agent.prompts import build_system_prompt
from app.services.agent_memory import load_memory, note_user_message
from app.models.user import User
from sqlalchemy.orm import Session


def test_memory_survives_and_replaces(db_session: Session, active_user: User) -> None:
    assert note_user_message(db_session, active_user.id, "帮我看下今天的待办") == ""
    note_user_message(db_session, active_user.id, "我负责华东区，日报我习惯先写工时")
    note_user_message(db_session, active_user.id, "请记住：不要用表情")
    text = load_memory(db_session, active_user.id)
    assert "我负责华东区" in text
    assert "我习惯先写工时" in text
    assert "不要用表情" in text
    note_user_message(db_session, active_user.id, "我负责华北区")
    text = load_memory(db_session, active_user.id)
    assert "我负责华北区" in text
    assert "我负责华东区" not in text
    prompt = build_system_prompt(user_name="爱丽丝", department="销售", page_context=None, memory=text)
    assert "我负责华北区" in prompt
    assert "仍必须调工具" in prompt
