"""企业知识检索：Agent 问答走已发布知识，禁止编造。"""
from __future__ import annotations

from langchain_core.tools import tool

from app.agent.runtime import require_db, require_user
from app.core.rbac import user_can
from app.schemas.knowledge import KnowledgeAskRequest
from app.services import knowledge as knowledge_service


@tool
def search_knowledge(question: str) -> dict:
    """检索公司已发布知识库文档：制度、规范、流程、需求说明、产品/业务资料等。
    问报销、请假、审批规则、交付规范、员工制度，以及「某某需求是什么」「查一下小程序需求」这类知识库标题时必须先调此工具；不要当成项目搜索。
    found=false 时必须明确告知没有依据，禁止猜测。回答时必须列出 citations 里的来源标题和版本。
    content 是命中文档的正文。正文里有几个阶段或步骤就要答全，不要只复述开头。
    正文末尾如果写了「只返回前一部分」，再说明后面没有带回来。"""
    db, user = require_db(), require_user()
    if not user_can(user, "knowledge:view"):
        return {"error": "无权检索知识库", "found": False}
    result = knowledge_service.ask(db, user, KnowledgeAskRequest(question=question))
    citations = result.get("citations") or []
    return {
        "ask_id": result.get("ask_id"),
        "found": int(result.get("matched_count") or 0) > 0,
        "citations": [
            {
                "title": c.get("title"),
                "source": c.get("source_label"),
                "version": c.get("version"),
                "content": c.get("excerpt") or c.get("snippet") or "",
                "source_url": c.get("source_url"),
            }
            for c in citations
        ],
    }
