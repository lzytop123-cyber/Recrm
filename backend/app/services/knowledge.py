"""
AI 知识库业务：工作台、添加知识源、检索增强问答（RAG）。
配置 DeepSeek LLM_API_KEY 后，基于命中资料调用大模型生成答案；否则回退检索拼接。
"""
from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.rbac import user_can
from app.models.knowledge import (
    ARTICLE_STATUS_PENDING_REVIEW,
    ARTICLE_STATUS_PUBLISHED,
    SOURCE_STATUS_ACTIVE,
    SOURCE_STATUS_FAILED,
    SOURCE_STATUS_PENDING,
    SOURCE_TYPE_FEISHU_CHAT,
    SOURCE_TYPE_FEISHU_DOC,
    SOURCE_TYPE_MANUAL,
    SOURCE_TYPES,
    KnowledgeArticle,
    KnowledgeSource,
    KnowledgeSpace,
)
from app.models.user import User
from app.schemas.knowledge import KnowledgeAskRequest, KnowledgeSourceCreate
from app.services import llm as llm_service

logger = logging.getLogger(__name__)

ANSWER_MODE_LLM = "llm"
ANSWER_MODE_RETRIEVE = "retrieve"

_SYSTEM_PROMPT = (
    "你是中泰旭鼎 CRM 企业知识库助手。只能依据用户提供的「已授权知识资料」作答，"
    "不得编造资料中没有的流程、数字或制度。"
    "若资料不足以回答，明确说明依据不足并建议查阅相关知识源。"
    "用简体中文回答，条理清晰，控制在 200 字以内。"
    "只输出纯文本段落，不要 Markdown 标题、列表符号或 HTML 标签；段与段之间用空行分隔。"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def can_manage_knowledge(user: User) -> bool:
    return user_can(user, "knowledge:manage")


def _ensure_seed(db: Session) -> None:
    if db.query(KnowledgeSpace).count() > 0:
        return

    spaces = [
        KnowledgeSpace(code="all", name="全部知识", icon="全", sort_order=0, description="汇总全部空间"),
        KnowledgeSpace(code="sales", name="销售方法与产品", icon="销", sort_order=1),
        KnowledgeSpace(code="delivery", name="项目交付规范", icon="项", sort_order=2),
        KnowledgeSpace(code="media", name="新媒体运营", icon="媒", sort_order=3),
        KnowledgeSpace(code="policy", name="制度与流程", icon="制", sort_order=4),
    ]
    db.add_all(spaces)
    db.flush()

    by_code = {s.code: s for s in spaces}
    sources = [
        KnowledgeSource(
            name="项目交付规范云文档目录",
            source_type=SOURCE_TYPE_FEISHU_DOC,
            space_id=by_code["delivery"].id,
            external_ref="wiki/delivery",
            status=SOURCE_STATUS_ACTIVE,
            authorized=True,
            last_sync_at=_now(),
        ),
        KnowledgeSource(
            name="星河制造项目周会群",
            source_type=SOURCE_TYPE_FEISHU_CHAT,
            space_id=by_code["delivery"].id,
            external_ref="chat/xinghe-weekly",
            status=SOURCE_STATUS_ACTIVE,
            authorized=True,
            last_sync_at=_now(),
        ),
        KnowledgeSource(
            name="销售方法知识库",
            source_type=SOURCE_TYPE_FEISHU_DOC,
            space_id=by_code["sales"].id,
            external_ref="wiki/sales",
            status=SOURCE_STATUS_ACTIVE,
            authorized=True,
            last_sync_at=_now(),
        ),
        KnowledgeSource(
            name="新媒体运营规范",
            source_type=SOURCE_TYPE_FEISHU_DOC,
            space_id=by_code["media"].id,
            status=SOURCE_STATUS_FAILED,
            authorized=True,
            sync_error="云文档权限变更，待重新授权",
        ),
        KnowledgeSource(
            name="制度流程待授权目录",
            source_type=SOURCE_TYPE_FEISHU_DOC,
            space_id=by_code["policy"].id,
            status=SOURCE_STATUS_PENDING,
            authorized=False,
        ),
    ]
    db.add_all(sources)
    db.flush()

    articles = [
        KnowledgeArticle(
            title="项目变更与基线管理规范",
            space_id=by_code["delivery"].id,
            source_id=sources[0].id,
            content=(
                "项目预计延期时，需要先提交项目变更申请，不能直接修改原计划。"
                "项目负责人应说明延期原因、受影响的里程碑、交付物、人员和成本，并提交新的计划基线。"
                "涉及客户承诺变化时，需要同步商务责任人和客户确认。"
                "审批完成后，系统保存原基线和新版本，并重新计算项目健康度。"
                "如果延期已经触发跨部门协作或验收风险，还需要关联对应工单和风险事项。"
                "例外放行必须填写原因并获得授权。"
            ),
            summary="延期必须走变更申请并保留原基线与新版本。",
            keywords="延期,变更,基线,里程碑,审批,项目",
            version="V3.2",
            status=ARTICLE_STATUS_PUBLISHED,
            source_label="云文档",
            published_at=date(2026, 7, 18),
        ),
        KnowledgeArticle(
            title="星河制造项目周会纪要",
            space_id=by_code["delivery"].id,
            source_id=sources[1].id,
            content=(
                "星河制造二期本周确认：若联调里程碑继续延期，项目经理需在周五前提交基线变更申请，"
                "并同步商务王洋与客户侧对接人。变更获批前不得私自调整甘特计划。"
            ),
            summary="星河制造延期须周五前提交基线变更。",
            keywords="星河,延期,变更,周会,基线",
            version="2026-07-21",
            status=ARTICLE_STATUS_PUBLISHED,
            source_label="授权工作群",
            published_at=date(2026, 7, 21),
        ),
        KnowledgeArticle(
            title="客户交付异常处理流程",
            space_id=by_code["delivery"].id,
            source_id=sources[0].id,
            content=(
                "当延期触发跨部门协作或验收风险时，应关联协作工单和风险事项，"
                "由承接部门接单处理。例外放行需填写原因并获得授权角色批准。"
            ),
            summary="异常需关联工单与风险，例外放行需授权。",
            keywords="异常,验收,工单,风险,例外,延期",
            version="V2.1",
            status=ARTICLE_STATUS_PUBLISHED,
            source_label="云文档",
            published_at=date(2026, 7, 9),
        ),
        KnowledgeArticle(
            title="AI产品标准售前话术",
            space_id=by_code["sales"].id,
            source_id=sources[2].id,
            content="售前应区分授权交付与定制交付边界，金额承诺不得突破报价审批口径。",
            summary="售前话术与报价边界。",
            keywords="售前,话术,报价,AI产品",
            version="V1.4",
            status=ARTICLE_STATUS_PUBLISHED,
            source_label="云文档",
            published_at=date(2026, 7, 12),
        ),
        KnowledgeArticle(
            title="自媒体代运营内容审核清单",
            space_id=by_code["media"].id,
            source_id=None,
            content="发布前需完成合规、品牌口径与客户确认三道审核。",
            summary="发布前三道审核。",
            keywords="审核,发布,自媒体,合规",
            version="V2.0",
            status=ARTICLE_STATUS_PENDING_REVIEW,
            source_label="人工录入",
            published_at=None,
        ),
        KnowledgeArticle(
            title="员工请假与排期冲突处理制度",
            space_id=by_code["policy"].id,
            source_id=None,
            content="排期冲突应先请求协调，由组织者调整时间或替换人员。",
            summary="排期冲突协调规则。",
            keywords="请假,排期,冲突,协调",
            version="V1.1",
            status=ARTICLE_STATUS_PUBLISHED,
            source_label="云文档",
            published_at=date(2026, 6, 30),
        ),
    ]
    db.add_all(articles)
    db.commit()


def enrich_space(db: Session, space: KnowledgeSpace) -> KnowledgeSpace:
    if space.code == "all":
        cnt = (
            db.query(func.count(KnowledgeArticle.id))
            .filter(KnowledgeArticle.status == ARTICLE_STATUS_PUBLISHED)
            .scalar()
        )
    else:
        cnt = (
            db.query(func.count(KnowledgeArticle.id))
            .filter(
                KnowledgeArticle.space_id == space.id,
                KnowledgeArticle.status == ARTICLE_STATUS_PUBLISHED,
            )
            .scalar()
        )
    space.article_count = int(cnt or 0)  # type: ignore[attr-defined]
    return space


def enrich_source(db: Session, source: KnowledgeSource) -> KnowledgeSource:
    sp = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == source.space_id).first() if source.space_id else None
    source.space_name = sp.name if sp else None  # type: ignore[attr-defined]
    return source


def enrich_article(db: Session, article: KnowledgeArticle) -> KnowledgeArticle:
    sp = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == article.space_id).first()
    article.space_name = sp.name if sp else None  # type: ignore[attr-defined]
    return article


def get_workbench(db: Session, user: User) -> dict:
    _ensure_seed(db)
    spaces = db.query(KnowledgeSpace).order_by(KnowledgeSpace.sort_order.asc(), KnowledgeSpace.id.asc()).all()
    sources = db.query(KnowledgeSource).order_by(KnowledgeSource.id.desc()).all()
    articles = (
        db.query(KnowledgeArticle)
        .order_by(KnowledgeArticle.updated_at.desc())
        .limit(100)
        .all()
    )

    chats = sum(1 for s in sources if s.source_type == SOURCE_TYPE_FEISHU_CHAT and s.authorized)
    docs = sum(1 for s in sources if s.source_type == SOURCE_TYPE_FEISHU_DOC and s.authorized)
    pending = (
        db.query(func.count(KnowledgeArticle.id))
        .filter(KnowledgeArticle.status == ARTICLE_STATUS_PENDING_REVIEW)
        .scalar()
        or 0
    )
    failed = sum(1 for s in sources if s.status == SOURCE_STATUS_FAILED)
    published = (
        db.query(func.count(KnowledgeArticle.id))
        .filter(KnowledgeArticle.status == ARTICLE_STATUS_PUBLISHED)
        .scalar()
        or 0
    )

    return {
        "spaces": [enrich_space(db, s) for s in spaces],
        "sources": [enrich_source(db, s) for s in sources],
        "articles": [enrich_article(db, a) for a in articles],
        "sync_stats": {
            "authorized_chats": chats,
            "doc_dirs": docs,
            "pending_review": int(pending),
            "sync_failed": failed,
            "status": "异常" if failed else "正常",
        },
        "total_published": int(published),
        "can_manage": can_manage_knowledge(user),
    }


def create_source(db: Session, user: User, payload: KnowledgeSourceCreate) -> KnowledgeSource:
    if not can_manage_knowledge(user):
        raise HTTPException(status_code=403, detail="无权添加知识源")
    if payload.source_type not in SOURCE_TYPES:
        raise HTTPException(status_code=400, detail="无效的知识源类型")
    if payload.space_id:
        sp = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == payload.space_id).first()
        if not sp or sp.code == "all":
            raise HTTPException(status_code=400, detail="请选择有效知识空间")

    source = KnowledgeSource(
        name=payload.name.strip(),
        source_type=payload.source_type,
        space_id=payload.space_id,
        external_ref=(payload.external_ref or "").strip() or None,
        status=SOURCE_STATUS_PENDING,
        authorized=payload.source_type == SOURCE_TYPE_MANUAL,
        creator_id=user.id,
        remark=(payload.remark or "").strip() or None,
    )
    if payload.source_type == SOURCE_TYPE_MANUAL:
        source.status = SOURCE_STATUS_ACTIVE
        source.authorized = True
        source.last_sync_at = _now()
    db.add(source)
    db.commit()
    db.refresh(source)
    return enrich_source(db, source)


def authorize_source(db: Session, user: User, source_id: int) -> KnowledgeSource:
    if not can_manage_knowledge(user):
        raise HTTPException(status_code=403, detail="无权授权知识源")
    source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="知识源不存在")
    source.authorized = True
    source.status = SOURCE_STATUS_ACTIVE
    source.sync_error = None
    source.last_sync_at = _now()
    db.commit()
    db.refresh(source)
    return enrich_source(db, source)


def _tokenize(question: str) -> list[str]:
    """中文按连续片段 + 2/3 字切词，避免整句粘连导致命中失败。"""
    q = question.lower().strip()
    runs = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]{2,}", q)
    tokens: set[str] = set(runs)
    for run in runs:
        if re.fullmatch(r"[\u4e00-\u9fff]+", run):
            for n in (2, 3):
                if len(run) < n:
                    continue
                for i in range(len(run) - n + 1):
                    tokens.add(run[i : i + n])
    return [t for t in tokens if t] or ([q] if q else [])


def _score_article(article: KnowledgeArticle, tokens: list[str]) -> int:
    blob = f"{article.title} {article.keywords or ''} {article.summary or ''} {article.content}".lower()
    score = 0
    for t in tokens:
        if t and t in blob:
            score += 2 if t in (article.title or "").lower() else 1
            if article.keywords and t in article.keywords.lower():
                score += 2
    return score


def _build_citations(articles: list[KnowledgeArticle]) -> list[dict]:
    citations = []
    for art in articles:
        updated = art.published_at.isoformat() if art.published_at else (
            art.updated_at.strftime("%Y-%m-%d") if art.updated_at else None
        )
        citations.append(
            {
                "article_id": art.id,
                "title": art.title,
                "source_label": art.source_label or "知识条目",
                "version": art.version,
                "updated_at": updated,
                "snippet": (art.summary or art.content[:100]),
            }
        )
    return citations


def _stitch_answer_html(articles: list[KnowledgeArticle]) -> str:
    lead = articles[0].summary or articles[0].content[:80]
    paragraphs = [f"<p><strong>{html.escape(lead)}</strong></p>"]
    for art in articles:
        text = art.content.replace("。", "。\n").split("\n")
        if art is articles[0]:
            body = "".join(f"<p>{html.escape(t)}</p>" for t in text[1:3] if t.strip())
        else:
            body = "".join(f"<p>{html.escape(t)}</p>" for t in text[:2] if t.strip())
        if body:
            paragraphs.append(body)
    return "".join(paragraphs)


def _text_to_safe_html(text: str) -> str:
    """将模型纯文本转为仅含 <p>/<strong> 的安全 HTML。"""
    cleaned = text.replace("\r\n", "\n").strip()
    # 去掉模型偶尔吐出的简单标签，再整体转义
    cleaned = re.sub(r"</?(?:p|strong|br|div|span)[^>]*>", "", cleaned, flags=re.I)
    blocks = [b.strip() for b in re.split(r"\n\s*\n", cleaned) if b.strip()]
    if not blocks:
        blocks = [cleaned] if cleaned else ["（模型未返回有效内容）"]
    parts: list[str] = []
    for i, block in enumerate(blocks):
        lines = " ".join(line.strip() for line in block.split("\n") if line.strip())
        esc = html.escape(lines)
        if i == 0:
            parts.append(f"<p><strong>{esc}</strong></p>")
        else:
            parts.append(f"<p>{esc}</p>")
    return "".join(parts)


def _generate_llm_answer(question: str, articles: list[KnowledgeArticle]) -> str:
    docs = []
    for i, art in enumerate(articles, start=1):
        docs.append(
            f"[{i}] 标题：{art.title}\n"
            f"来源：{art.source_label or '知识条目'} · 版本：{art.version}\n"
            f"摘要：{art.summary or ''}\n"
            f"正文：{art.content}"
        )
    user_content = (
        f"问题：{question}\n\n"
        f"已授权知识资料：\n\n" + "\n\n---\n\n".join(docs)
    )
    raw = llm_service.chat_completion(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
    )
    return _text_to_safe_html(raw)


def ask(db: Session, user: User, payload: KnowledgeAskRequest) -> dict:
    _ensure_seed(db)
    q = payload.question.strip()
    tokens = _tokenize(q)

    query = db.query(KnowledgeArticle).filter(KnowledgeArticle.status == ARTICLE_STATUS_PUBLISHED)
    if payload.space_id:
        sp = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == payload.space_id).first()
        if sp and sp.code != "all":
            query = query.filter(KnowledgeArticle.space_id == payload.space_id)

    candidates: list[tuple[int, KnowledgeArticle]] = []
    for art in query.all():
        s = _score_article(art, tokens)
        if s > 0:
            candidates.append((s, art))
    candidates.sort(key=lambda x: -x[0])
    top = [a for _, a in candidates[:3]]

    # 延期变更类问题：优先原型固定三篇
    delay_tokens = {"延期", "变更", "基线"}
    if delay_tokens & set(tokens) or any(k in q for k in delay_tokens):
        preferred_titles = [
            "项目变更与基线管理规范",
            "星河制造项目周会纪要",
            "客户交付异常处理流程",
        ]
        preferred = (
            db.query(KnowledgeArticle)
            .filter(
                KnowledgeArticle.status == ARTICLE_STATUS_PUBLISHED,
                KnowledgeArticle.title.in_(preferred_titles),
            )
            .all()
        )
        if preferred:
            order = {t: i for i, t in enumerate(preferred_titles)}
            preferred.sort(key=lambda a: order.get(a.title, 99))
            top = preferred[:3]

    if not top:
        return {
            "question": q,
            "answer_html": (
                "<p><strong>未在你有权访问的已发布知识中找到足够依据。</strong></p>"
                "<p>请尝试更换关键词，或联系管理员检查知识源授权与同步状态。</p>"
            ),
            "citations": [],
            "retrieved_at": _now().strftime("%H:%M"),
            "matched_count": 0,
            "answer_mode": ANSWER_MODE_RETRIEVE,
        }

    citations = _build_citations(top)
    answer_mode = ANSWER_MODE_RETRIEVE
    answer_html = _stitch_answer_html(top)

    if llm_service.is_llm_configured():
        try:
            answer_html = _generate_llm_answer(q, top)
            answer_mode = ANSWER_MODE_LLM
        except llm_service.LlmError as exc:
            logger.warning("knowledge RAG LLM fallback: %s", exc)

    return {
        "question": q,
        "answer_html": answer_html,
        "citations": citations,
        "retrieved_at": _now().strftime("%H:%M"),
        "matched_count": len(citations),
        "answer_mode": answer_mode,
    }
