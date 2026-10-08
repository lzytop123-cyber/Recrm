"""
AI 知识库业务：工作台、添加知识源、检索增强问答（RAG）。
配置 DeepSeek LLM_API_KEY 后，基于命中资料调用大模型生成答案；否则回退检索拼接。
"""
from __future__ import annotations

import html
import json
import logging
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.rbac import user_can
from app.models.knowledge import (
    ARTICLE_ACTION_DRAFT,
    ARTICLE_ACTION_PUBLISH,
    ARTICLE_ACTION_SUBMIT,
    ARTICLE_ACTIONS,
    ARTICLE_ORIGIN_AI,
    ARTICLE_ORIGIN_FEISHU_CHAT,
    ARTICLE_ORIGIN_FEISHU_DOC,
    ARTICLE_ORIGIN_MANUAL,
    ARTICLE_STATUS_ARCHIVED,
    ARTICLE_STATUS_DISABLED,
    ARTICLE_STATUS_DRAFT,
    ARTICLE_STATUS_PENDING_REVIEW,
    ARTICLE_STATUS_PUBLISHED,
    ARTICLE_STATUS_REJECTED,
    ARTICLE_STATUS_REVIEWED,
    CRAWL_CONFIG_KEY,
    DOC_TYPES,
    DOC_TYPE_QA,
    ENTRY_SORTS,
    FEEDBACK_ACCEPTED,
    FEEDBACK_CORRECTION,
    FEEDBACK_PENDING,
    FEEDBACK_REJECTED,
    FEEDBACK_USEFUL,
    FEEDBACK_USELESS,
    JOB_STATUS_DONE,
    JOB_STATUS_FAILED,
    JOB_STATUS_RUNNING,
    SORT_RECENT,
    SORT_TITLE,
    SOURCE_STATUS_ACTIVE,
    SOURCE_STATUS_FAILED,
    SOURCE_STATUS_PENDING,
    SOURCE_STATUS_REVOKED,
    SOURCE_TYPE_FEISHU_CHAT,
    SOURCE_TYPE_FEISHU_DOC,
    SOURCE_TYPE_MANUAL,
    VISIBILITIES,
    VISIBILITY_DEPARTMENT,
    VISIBILITY_INHERIT,
    KnowledgeArticle,
    KnowledgeArticleVersion,
    KnowledgeAsk,
    KnowledgeFeedback,
    KnowledgeGap,
    KnowledgeJob,
    KnowledgeSource,
    KnowledgeSpace,
)
from app.models.platform import SystemConfig
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeApproveIn,
    KnowledgeArticleCreate,
    KnowledgeArticlePatch,
    KnowledgeAskRequest,
    KnowledgeCorrectionIn,
    KnowledgeFeedbackIn,
    KnowledgeFeedbackPatch,
    KnowledgeSourceCreate,
    KnowledgeSpaceCreate,
    KnowledgeWhitelistCreate,
)
from app.services import llm as llm_service
from app.services.feishu_auth import FeishuAuthError
from app.services.feishu_client import get_feishu_client

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


_FEISHU_DOC_RE = re.compile(
    r"(?:https?://[^\s/]+)?/(docx|docs|sheets|wiki|mindnote|base|doc)/([A-Za-z0-9]+)",
    re.I,
)
_FEISHU_KIND = {"docs": "doc", "sheets": "sheet", "base": "bitable"}
_READABLE_KINDS = {"docx", "doc", "mindnote", "sheet", "bitable"}
_SHEET_MAX_ROWS = 200
_SHEET_MAX_COLS = 20
_BITABLE_MAX_RECORDS = 200
_DEMO_SOURCE_REFS = frozenset({"wiki/delivery", "chat/xinghe-weekly", "wiki/sales"})
_DEMO_SOURCE_NAMES = frozenset(
    {
        "项目交付规范云文档目录",
        "星河制造项目周会群",
        "销售方法知识库",
        "新媒体运营规范",
        "制度流程待授权目录",
    }
)
_DEMO_ARTICLE_TITLES = frozenset(
    {
        "项目变更与基线管理规范",
        "星河制造项目周会纪要",
        "客户交付异常处理流程",
        "AI产品标准售前话术",
        "自媒体代运营内容审核清单",
        "员工请假与排期冲突处理制度",
    }
)


_SPACES = (
    {"code": "all", "name": "全部文档", "icon": "全", "sort_order": 0, "description": "汇总全部空间"},
    {"code": "compliance", "name": "合规知识", "icon": "合", "sort_order": 1},
    {"code": "sales", "name": "销售方法与产品", "icon": "销", "sort_order": 2},
    {"code": "delivery", "name": "项目交付规范", "icon": "项", "sort_order": 3},
    {"code": "media", "name": "新媒体运营", "icon": "媒", "sort_order": 4},
    {"code": "policy", "name": "制度与流程", "icon": "制", "sort_order": 5},
)


def _ensure_spaces(db: Session) -> None:
    existing = {s.code: s for s in db.query(KnowledgeSpace).all()}
    changed = False
    for spec in _SPACES:
        row = existing.get(spec["code"])
        if row is None:
            db.add(KnowledgeSpace(**spec))
            changed = True
        else:
            if row.name != spec["name"] or row.sort_order != spec["sort_order"]:
                row.name = spec["name"]
                row.sort_order = spec["sort_order"]
                changed = True
    if changed:
        db.commit()


def _crawl_enabled(db: Session) -> bool:
    row = db.query(SystemConfig).filter(SystemConfig.key == CRAWL_CONFIG_KEY).first()
    if not row or row.value is None:
        return True
    return str(row.value).strip().lower() not in {"0", "false", "off", "no"}


def _set_crawl_enabled(db: Session, user: User, enabled: bool) -> None:
    value = "true" if enabled else "false"
    row = db.query(SystemConfig).filter(SystemConfig.key == CRAWL_CONFIG_KEY).first()
    if row is None:
        db.add(
            SystemConfig(
                key=CRAWL_CONFIG_KEY,
                value=value,
                description="关闭后停止从飞书群会话与云文档生成 AI 草稿",
                updated_by=user.id,
            )
        )
        return
    row.value = value
    row.updated_by = user.id


def _valid_http_url(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if not text.startswith("http"):
        raise HTTPException(status_code=400, detail="飞书文档链接请粘贴完整 URL")
    return text[:300]


MAX_ATTACHMENTS = 5
_HTML_CHUNK_RE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>|<[^>]+>")


def _plain_text(text: str) -> str:
    raw = _HTML_CHUNK_RE.sub(" ", text or "")
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def _auto_summary(content: str, explicit: str | None = None) -> str | None:
    """列表摘要：人手写的纯文本优先；否则从正文抽纯文本，避免富文本表格变成标签。"""
    text = (explicit or "").strip()
    if text and "<" not in text:
        return text[:500]
    return _plain_text(content)[:180] or None



def _normalize_attachments(items: list | None, *, strict: bool = True) -> list[dict]:
    if not items:
        return []
    if strict and len(items) > MAX_ATTACHMENTS:
        raise HTTPException(status_code=400, detail="附件最多 5 个")
    out: list[dict] = []
    for item in items[:MAX_ATTACHMENTS]:
        if isinstance(item, str):
            path, filename = item.strip(), ""
        else:
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            path = str((item or {}).get("path") or (item or {}).get("url") or "").strip()
            filename = str((item or {}).get("filename") or "").strip()
        if not path:
            continue
        if not filename:
            filename = path.rsplit("/", 1)[-1]
        rel = path[len("/uploads/") :] if path.startswith("/uploads/") else path
        out.append(
            {
                "filename": filename[:255],
                "path": rel[:500],
                "url": path if path.startswith("http") else f"/uploads/{rel}",
            }
        )
    return out


def _with_download_urls(article_id: int, items: list[dict]) -> list[dict]:
    for i, item in enumerate(items):
        item["download_url"] = f"/api/v1/knowledge/entries/{article_id}/attachments/{i}/download"
    return items


def _dump_attachments(items: list[dict]) -> str | None:
    if not items:
        return None
    return json.dumps(
        [{"filename": x["filename"], "path": x["path"]} for x in items],
        ensure_ascii=False,
    )


def _load_attachments(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return _normalize_attachments(data, strict=False)


def _payload_attachments(attachments=None, attachment: str | None = None) -> list | None:
    items = list(attachments or [])
    extra = (attachment or "").strip()
    if extra:
        items.append(extra)
    return items or None


def _refresh_attachment_text(article: KnowledgeArticle) -> None:
    """从附件抽文本写入 attachment_text，供检索/问答（不改用户正文）。"""
    from app.services.attachment_extract import extract_attachment_text
    from app.services import uploads as upload_service

    parts: list[str] = []
    for item in _load_attachments(getattr(article, "attachments_json", None)):
        rel = (item.get("path") or "").strip()
        if not rel:
            continue
        try:
            path = upload_service.resolve_stored_file(rel)
        except HTTPException:
            continue
        text = extract_attachment_text(path)
        if text:
            name = item.get("filename") or path.name
            parts.append(f"[{name}]\n{text}")
    article.attachment_text = "\n\n".join(parts) or None


_DEMO_ORPHAN_SUMMARIES = frozenset({"发布前三道审核。", "排期冲突协调规则。"})


def _purge_demo_content(db: Session) -> None:
    """清掉原型演示源/条目，避免被当成正式制度。"""
    demo_sources = (
        db.query(KnowledgeSource)
        .filter(
            (KnowledgeSource.external_ref.in_(_DEMO_SOURCE_REFS))
            | (KnowledgeSource.name.in_(_DEMO_SOURCE_NAMES))
        )
        .all()
    )
    demo_sources = [
        s
        for s in demo_sources
        if (s.external_ref in _DEMO_SOURCE_REFS)
        or not (s.external_ref or "").startswith("http")
    ]
    source_ids = [s.id for s in demo_sources]
    removed = False
    # 用 id 批量删除，避免 ORM 整行加载受未迁移列影响
    if source_ids:
        n = (
            db.query(KnowledgeArticle)
            .filter(KnowledgeArticle.source_id.in_(source_ids))
            .delete(synchronize_session=False)
        )
        removed = removed or bool(n)
    n = (
        db.query(KnowledgeArticle)
        .filter(
            KnowledgeArticle.source_id.is_(None),
            KnowledgeArticle.title.in_(_DEMO_ARTICLE_TITLES),
            KnowledgeArticle.summary.in_(_DEMO_ORPHAN_SUMMARIES),
        )
        .delete(synchronize_session=False)
    )
    removed = removed or bool(n)
    for src in demo_sources:
        db.delete(src)
        removed = True
    if removed:
        db.commit()


def _rich_text(blocks: list | None) -> str:
    parts: list[str] = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        text = block.get("text") or {}
        content = text.get("content") if isinstance(text, dict) else None
        if content:
            parts.append(str(content))
    return "".join(parts).strip()


def _cell_text(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "name", "link"):
            if value.get(key):
                return str(value[key]).strip()
        return ""
    if isinstance(value, list):
        return "、".join(part for part in (_cell_text(item) for item in value) if part)
    return str(value).strip()


def _col_letter(index: int) -> str:
    name = ""
    while index > 0:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def sheet_plain_text(sheets: list[dict]) -> str:
    blocks: list[str] = []
    for sheet in sheets:
        rows: list[str] = []
        for row in sheet.get("values") or []:
            cells = [_cell_text(cell) for cell in row]
            if any(cells):
                rows.append(" | ".join(cells).strip())
        if not rows:
            continue
        if sheet.get("truncated"):
            rows.append("（仅同步前 200 行、20 列）")
        blocks.append(f"{sheet.get('title') or '工作表'}\n" + "\n".join(rows))
    return "\n\n".join(blocks).strip()


def bitable_plain_text(tables: list[dict]) -> str:
    blocks: list[str] = []
    for table in tables:
        records = table.get("records") or []
        names: list[str] = []
        for record in records:
            for key in record.get("fields") or {}:
                if key not in names:
                    names.append(key)
        if not names:
            continue
        lines = [" | ".join(names)]
        for record in records:
            fields = record.get("fields") or {}
            lines.append(" | ".join(_cell_text(fields.get(name)) for name in names))
        if table.get("truncated"):
            lines.append("（仅同步前 200 条）")
        blocks.append(f"{table.get('name') or '数据表'}\n" + "\n".join(lines))
    return "\n\n".join(blocks).strip()


def mindnote_plain_text(nodes: list[dict]) -> str:
    """把思维笔记节点压成缩进大纲。根节点没有 parent_id。"""
    by_parent: dict[str, list[dict]] = {}
    for node in nodes:
        by_parent.setdefault(str(node.get("parent_id") or ""), []).append(node)
    lines: list[str] = []

    def walk(parent: str, depth: int) -> None:
        for node in by_parent.get(parent, []):
            title = _rich_text(node.get("texts"))
            note = _rich_text(node.get("notes"))
            if title:
                lines.append(f"{'  ' * depth}{title}")
            if note:
                lines.append(f"{'  ' * depth}{note}")
            walk(str(node.get("node_id") or ""), depth + (1 if title or note else 0))

    walk("", 0)
    return "\n".join(lines).strip()


def parse_feishu_doc_ref(raw: str) -> tuple[str, str, str | None]:
    """解析飞书文档 URL 或 token → (kind, token, url)。"""
    text = (raw or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请填写飞书云文档链接")
    match = _FEISHU_DOC_RE.search(text)
    if match:
        url = text if text.startswith("http") else None
        return _FEISHU_KIND.get(match.group(1).lower(), match.group(1).lower()), match.group(2), url
    if re.fullmatch(r"[A-Za-z0-9_-]{10,80}", text):
        return "unknown", text, None
    raise HTTPException(status_code=400, detail="无法识别飞书文档链接，请粘贴浏览器地址栏中的文档 URL")


def _http_source_url(source: KnowledgeSource | None) -> str | None:
    ref = (source.external_ref or "").strip() if source else ""
    return ref if ref.startswith("http") else None


async def _pull_feishu_doc(kind: str, token: str) -> dict[str, str]:
    async with get_feishu_client() as client:
        obj_token = token
        title = ""
        if kind in ("wiki", "unknown"):
            try:
                node = await client.get_wiki_node(token)
            except FeishuAuthError:
                if kind == "wiki":
                    raise
                node = {}
            if node:
                obj_type = str(node.get("obj_type") or "").lower()
                if obj_type and obj_type not in _READABLE_KINDS:
                    raise HTTPException(
                        status_code=400,
                        detail=f"该节点类型为 {obj_type}，目前只支持云文档、旧版文档、表格、多维表格和思维笔记",
                    )
                obj_token = str(node.get("obj_token") or token)
                title = str(node.get("title") or "")
                kind = obj_type or "docx"
        if kind == "mindnote":
            nodes = await client.get_mindnote_nodes(obj_token)
            content = mindnote_plain_text(nodes)
            if not content:
                raise HTTPException(status_code=400, detail="思维笔记没有可读取的文字")
            return {"title": title or "未命名思维笔记", "content": content, "version": "1"}
        if kind == "doc":
            content = (await client.get_doc_raw_content(obj_token)).strip()
            if not content:
                raise HTTPException(status_code=400, detail="旧版文档正文为空，或应用没有旧版文档阅读权限")
            return {"title": title or "未命名文档", "content": content, "version": "1"}
        if kind == "sheet":
            meta = await client.get_sheet_meta(obj_token)
            title = title or str((meta.get("properties") or {}).get("title") or "未命名表格")
            blocks = []
            for sheet in meta.get("sheets") or []:
                sheet_id = str(sheet.get("sheetId") or sheet.get("sheet_id") or "")
                if not sheet_id:
                    continue
                row_count = int(sheet.get("rowCount") or 0)
                col_count = int(sheet.get("columnCount") or 0)
                rows = min(row_count or _SHEET_MAX_ROWS, _SHEET_MAX_ROWS)
                cols = min(col_count or _SHEET_MAX_COLS, _SHEET_MAX_COLS)
                if rows < 1 or cols < 1:
                    continue
                values = await client.get_sheet_values(obj_token, f"{sheet_id}!A1:{_col_letter(cols)}{rows}")
                blocks.append({
                    "title": sheet.get("title") or "工作表",
                    "values": values,
                    "truncated": row_count > _SHEET_MAX_ROWS or col_count > _SHEET_MAX_COLS,
                })
            content = sheet_plain_text(blocks)
            if not content:
                raise HTTPException(status_code=400, detail="表格没有可读取的内容，或应用没有电子表格权限")
            return {"title": title, "content": content, "version": "1"}
        if kind == "bitable":
            tables = await client.list_bitable_tables(obj_token)
            blocks = []
            for table in tables:
                table_id = str(table.get("table_id") or "")
                if not table_id:
                    continue
                records, truncated = await client.list_bitable_records(
                    obj_token, table_id, limit=_BITABLE_MAX_RECORDS
                )
                blocks.append({
                    "name": table.get("name") or "数据表",
                    "records": records,
                    "truncated": truncated,
                })
            content = bitable_plain_text(blocks)
            if not content:
                raise HTTPException(status_code=400, detail="多维表格没有可读取的记录，或应用没有多维表格权限")
            return {"title": title or "未命名多维表格", "content": content, "version": "1"}
        if kind not in _READABLE_KINDS:
            raise HTTPException(status_code=400, detail="无法识别该飞书文档类型")
        meta = await client.get_docx_meta(obj_token)
        title = title or str(meta.get("title") or "未命名文档")
        content = (await client.get_docx_raw_content(obj_token)).strip()
        if not content:
            raise HTTPException(status_code=400, detail="文档正文为空，或应用没有云文档阅读权限")
        version = str(meta.get("revision_id") or "1")
        return {"title": title, "content": content, "version": version}


async def sync_feishu_source(db: Session, user: User, source_id: int) -> KnowledgeSource:
    if not can_manage_knowledge(user):
        raise HTTPException(status_code=403, detail="无权同步知识源")
    source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="知识源不存在")
    if source.source_type != SOURCE_TYPE_FEISHU_DOC:
        raise HTTPException(status_code=400, detail="只有飞书云文档可以同步")
    if not source.space_id:
        raise HTTPException(status_code=400, detail="请先为该知识源选择空间")
    kind, token, url = parse_feishu_doc_ref(source.external_ref or "")
    try:
        payload = await _pull_feishu_doc(kind, token)
    except FeishuAuthError as exc:
        source.status = SOURCE_STATUS_FAILED
        source.sync_error = str(exc)[:300]
        db.commit()
        raise HTTPException(status_code=502, detail=f"飞书文档同步失败：{exc}") from exc
    except HTTPException as exc:
        source.status = SOURCE_STATUS_FAILED
        source.sync_error = str(exc.detail)[:300]
        db.commit()
        raise

    if url:
        source.external_ref = url
    article = (
        db.query(KnowledgeArticle).filter(KnowledgeArticle.source_id == source.id).first()
    )
    summary = _auto_summary(payload["content"])
    if article is None:
        article = KnowledgeArticle(
            title=payload["title"][:200],
            space_id=source.space_id,
            source_id=source.id,
            content=payload["content"],
            summary=summary,
            version=payload["version"][:20],
            status=ARTICLE_STATUS_PENDING_REVIEW,
            origin=ARTICLE_ORIGIN_FEISHU_DOC,
            source_label="飞书文档同步",
            source_url=_http_source_url(source),
            creator_id=user.id,
        )
        db.add(article)
    else:
        if article.status == ARTICLE_STATUS_PUBLISHED and article.content != payload["content"]:
            db.add(
                KnowledgeArticleVersion(
                    article_id=article.id,
                    version=article.version,
                    title=article.title,
                    content=article.content,
                    summary=article.summary,
                    change_reason="飞书同步出新草稿",
                    created_by=user.id,
                )
            )
            article.version = _bump_version(article.version)
        article.title = payload["title"][:200]
        article.space_id = source.space_id
        article.content = payload["content"]
        article.summary = summary
        article.origin = ARTICLE_ORIGIN_FEISHU_DOC
        article.status = ARTICLE_STATUS_PENDING_REVIEW
        article.source_label = "飞书文档同步"
        article.source_url = _http_source_url(source)
        article.published_at = None
    source.authorized = True
    source.status = SOURCE_STATUS_ACTIVE
    source.sync_error = None
    source.last_sync_at = _now()
    db.commit()
    db.refresh(source)
    return enrich_source(db, source)


def _article_count_query(db: Session, user: User | None = None):
    """与 list_entries 可见范围一致：管理员计全部状态，普通用户仅已发布。"""
    q = db.query(func.count(KnowledgeArticle.id))
    if user is None or not can_manage_knowledge(user):
        q = q.filter(KnowledgeArticle.status == ARTICLE_STATUS_PUBLISHED)
    return q


def _space_article_counts(db: Session, user: User | None = None) -> dict[int, int]:
    q = db.query(KnowledgeArticle.space_id, func.count(KnowledgeArticle.id))
    if user is None or not can_manage_knowledge(user):
        q = q.filter(KnowledgeArticle.status == ARTICLE_STATUS_PUBLISHED)
    return {int(sid): int(n) for sid, n in q.group_by(KnowledgeArticle.space_id).all() if sid is not None}


def enrich_space(
    db: Session,
    space: KnowledgeSpace,
    user: User | None = None,
    *,
    counts: dict[int, int] | None = None,
) -> KnowledgeSpace:
    if counts is not None:
        if space.code == "all":
            space.article_count = sum(counts.values())  # type: ignore[attr-defined]
        else:
            space.article_count = int(counts.get(space.id, 0))  # type: ignore[attr-defined]
        return space
    if space.code == "all":
        cnt = _article_count_query(db, user).scalar()
    else:
        cnt = (
            _article_count_query(db, user)
            .filter(KnowledgeArticle.space_id == space.id)
            .scalar()
        )
    space.article_count = int(cnt or 0)  # type: ignore[attr-defined]
    return space


_SPACE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def create_space(db: Session, user: User, payload: KnowledgeSpaceCreate) -> KnowledgeSpace:
    _require_manage(user)
    _ensure_spaces(db)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="请填写知识库名称")
    code = (payload.code or "").strip().lower()
    if code:
        if code == "all" or not _SPACE_CODE_RE.match(code):
            raise HTTPException(status_code=400, detail="知识库编码无效")
        if db.query(KnowledgeSpace).filter(KnowledgeSpace.code == code).first():
            raise HTTPException(status_code=400, detail="知识库编码已存在")
    else:
        code = f"c_{uuid.uuid4().hex[:10]}"
    icon = (payload.icon or "").strip() or name[0]
    description = (payload.description or "").strip() or None
    max_order = db.query(func.max(KnowledgeSpace.sort_order)).scalar()
    space = KnowledgeSpace(
        code=code,
        name=name,
        icon=icon[:8],
        description=description,
        sort_order=int(max_order or 0) + 1,
    )
    db.add(space)
    db.commit()
    db.refresh(space)
    return enrich_space(db, space, user)


def enrich_source(db: Session, source: KnowledgeSource) -> KnowledgeSource:
    sp = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == source.space_id).first() if source.space_id else None
    source.space_name = sp.name if sp else None  # type: ignore[attr-defined]
    source.article_count = int(  # type: ignore[attr-defined]
        db.query(func.count(KnowledgeArticle.id))
        .filter(KnowledgeArticle.source_id == source.id)
        .scalar()
        or 0
    )
    return source


def enrich_article(
    db: Session,
    article: KnowledgeArticle,
    *,
    sources_by_id: dict[int, KnowledgeSource] | None = None,
) -> KnowledgeArticle:
    sp = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == article.space_id).first()
    article.space_name = sp.name if sp else None  # type: ignore[attr-defined]
    source = None
    if article.source_id:
        if sources_by_id is not None:
            source = sources_by_id.get(article.source_id)
        else:
            source = db.query(KnowledgeSource).filter(KnowledgeSource.id == article.source_id).first()
    article.source_url = (article.source_url or "").strip() or _http_source_url(source)  # type: ignore[attr-defined]
    article.attachments = _with_download_urls(  # type: ignore[attr-defined]
        article.id, _load_attachments(getattr(article, "attachments_json", None))
    )
    if article.summary and "<" in article.summary:
        article.summary = _auto_summary(article.content)
    return article


def get_workbench(db: Session, user: User) -> dict:
    _ensure_spaces(db)
    _purge_demo_content(db)
    spaces = db.query(KnowledgeSpace).order_by(KnowledgeSpace.sort_order.asc(), KnowledgeSpace.id.asc()).all()
    sources = db.query(KnowledgeSource).order_by(KnowledgeSource.id.desc()).all()
    sources_by_id = {s.id: s for s in sources}
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

    counts = _space_article_counts(db, user)
    return {
        "spaces": [enrich_space(db, s, user, counts=counts) for s in spaces],
        "sources": [enrich_source(db, s) for s in sources],
        "articles": [enrich_article(db, a, sources_by_id=sources_by_id) for a in articles],
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


def _validate_space(db: Session, space_id: int | None, *, required: bool) -> None:
    if not space_id:
        if required:
            raise HTTPException(status_code=400, detail="请选择知识空间")
        return
    sp = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == space_id).first()
    if not sp or sp.code == "all":
        raise HTTPException(status_code=400, detail="请选择有效知识空间")


async def create_source(db: Session, user: User, payload: KnowledgeSourceCreate) -> KnowledgeSource:
    if not can_manage_knowledge(user):
        raise HTTPException(status_code=403, detail="无权添加知识源")
    if payload.source_type not in {SOURCE_TYPE_FEISHU_DOC, SOURCE_TYPE_FEISHU_CHAT, SOURCE_TYPE_MANUAL}:
        raise HTTPException(status_code=400, detail="无效的知识源类型")
    auto_sync = bool(payload.auto_sync)
    _validate_space(
        db,
        payload.space_id,
        required=payload.source_type == SOURCE_TYPE_FEISHU_DOC and auto_sync,
    )
    external_ref = (payload.external_ref or "").strip() or None
    if payload.source_type == SOURCE_TYPE_FEISHU_CHAT and not external_ref:
        raise HTTPException(status_code=400, detail="请填写飞书群 ID")
    if payload.source_type == SOURCE_TYPE_FEISHU_DOC and auto_sync:
        kind, token, url = parse_feishu_doc_ref(external_ref or "")
        _ = (kind, token)
        external_ref = url or external_ref
    elif payload.source_type == SOURCE_TYPE_FEISHU_DOC and not external_ref:
        raise HTTPException(status_code=400, detail="请填写飞书文档或文件夹 ID")

    source = KnowledgeSource(
        name=payload.name.strip(),
        source_type=payload.source_type,
        space_id=payload.space_id,
        external_ref=external_ref,
        status=SOURCE_STATUS_PENDING,
        authorized=False,
        creator_id=user.id,
        remark=(payload.remark or "").strip() or None,
    )
    if payload.source_type in {SOURCE_TYPE_MANUAL, SOURCE_TYPE_FEISHU_CHAT} or not auto_sync:
        source.status = SOURCE_STATUS_ACTIVE
        source.authorized = True
        if payload.source_type == SOURCE_TYPE_MANUAL:
            source.last_sync_at = _now()
    db.add(source)
    db.commit()
    db.refresh(source)
    if payload.source_type == SOURCE_TYPE_FEISHU_DOC and auto_sync and _crawl_enabled(db):
        return await sync_feishu_source(db, user, source.id)
    if source.status == SOURCE_STATUS_PENDING:
        source.status = SOURCE_STATUS_ACTIVE
        source.authorized = True
        db.commit()
        db.refresh(source)
    return enrich_source(db, source)


def _normalize_doc_type(raw: str | None) -> str:
    doc_type = (raw or DOC_TYPE_QA).strip()
    if doc_type not in DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail="文档类型仅支持 qa / doc / note / guide / policy / case / faq",
        )
    return doc_type


def _normalize_visibility(
    visibility: str | None, department: str | None
) -> tuple[str, str | None]:
    value = (visibility or VISIBILITY_INHERIT).strip() or VISIBILITY_INHERIT
    if value not in VISIBILITIES:
        raise HTTPException(status_code=400, detail="可见范围仅支持 inherit / department / all")
    dept = (department or "").strip() or None
    if value == VISIBILITY_DEPARTMENT and not dept:
        raise HTTPException(status_code=400, detail="部门可见时请填写可见部门")
    if value != VISIBILITY_DEPARTMENT:
        dept = None
    return value, dept


def _ensure_not_expired(expires_at: date | None) -> None:
    if expires_at and expires_at < date.today():
        raise HTTPException(status_code=400, detail="有效期已过，请调整后再提交")


def create_article(db: Session, user: User, payload: KnowledgeArticleCreate) -> KnowledgeArticle:
    if not can_manage_knowledge(user):
        raise HTTPException(status_code=403, detail="无权录入知识")
    _validate_space(db, payload.space_id, required=True)
    action = (payload.action or ARTICLE_ACTION_SUBMIT).strip()
    if action not in ARTICLE_ACTIONS:
        raise HTTPException(status_code=400, detail="action 仅支持 draft / submit / publish")
    doc_type = _normalize_doc_type(payload.doc_type)
    visibility, visibility_department = _normalize_visibility(
        payload.visibility, payload.visibility_department
    )
    expires_at = payload.expires_at
    if action != ARTICLE_ACTION_DRAFT:
        _ensure_not_expired(expires_at)
    status = {
        ARTICLE_ACTION_DRAFT: ARTICLE_STATUS_DRAFT,
        ARTICLE_ACTION_SUBMIT: ARTICLE_STATUS_PENDING_REVIEW,
        ARTICLE_ACTION_PUBLISH: ARTICLE_STATUS_PUBLISHED,
    }[action]
    content = payload.content.strip()
    article = KnowledgeArticle(
        title=payload.title.strip(),
        space_id=payload.space_id,
        content=content,
        summary=_auto_summary(content, payload.summary),
        keywords=(payload.keywords or "").strip() or None,
        doc_type=doc_type,
        origin=ARTICLE_ORIGIN_MANUAL,
        source_url=_valid_http_url(payload.source_url),
        source_note=(payload.source_note or "").strip() or None,
        visibility=visibility,
        visibility_department=visibility_department,
        expires_at=expires_at,
        version="1",
        status=status,
        source_label="人工录入",
        published_at=date.today() if status == ARTICLE_STATUS_PUBLISHED else None,
        creator_id=user.id,
        attachments_json=_dump_attachments(
            _normalize_attachments(_payload_attachments(payload.attachments, payload.attachment))
        ),
    )
    _refresh_attachment_text(article)
    db.add(article)
    db.commit()
    db.refresh(article)
    return enrich_article(db, article)


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


CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


def _chunk_text(text: str) -> list[str]:
    """按字符窗口切；中文按字符长度足够。检索时用，不入库。"""
    text = (text or "").strip()
    if len(text) <= CHUNK_SIZE:
        return [text] if text else []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    return [
        text[i : i + CHUNK_SIZE]
        for i in range(0, len(text), step)
        if text[i : i + CHUNK_SIZE].strip()
    ]


def _score_article(article: KnowledgeArticle, tokens: list[str]) -> tuple[int, str]:
    title = (article.title or "").lower()
    keywords = (article.keywords or "").lower()
    body = (article.content or "") + "\n" + (getattr(article, "attachment_text", None) or "")
    chunks = _chunk_text(body)
    if not chunks:
        chunks = [article.summary or ""]
    best_score, best_chunk = 0, chunks[0]
    for chunk in chunks:
        blob = f"{title} {keywords} {chunk.lower()}"
        score = 0
        for t in tokens:
            if t and t in blob:
                score += 2 if t in title else 1
                if t in keywords:
                    score += 2
        if score > best_score:
            best_score, best_chunk = score, chunk
    return best_score, best_chunk


def _build_citations(db: Session, hits: list[tuple[str, KnowledgeArticle]]) -> list[dict]:
    citations = []
    source_ids = [a.source_id for _, a in hits if a.source_id]
    sources_by_id: dict[int, KnowledgeSource] = {}
    if source_ids:
        rows = db.query(KnowledgeSource).filter(KnowledgeSource.id.in_(source_ids)).all()
        sources_by_id = {s.id: s for s in rows}
    for chunk, art in hits:
        updated = art.published_at.isoformat() if art.published_at else (
            art.updated_at.strftime("%Y-%m-%d") if art.updated_at else None
        )
        source = sources_by_id.get(art.source_id) if art.source_id else None
        snippet = (chunk or art.summary or art.content or "")[:120]
        citations.append(
            {
                "article_id": art.id,
                "title": art.title,
                "source_label": art.source_label or "知识条目",
                "version": art.version,
                "updated_at": updated,
                "snippet": snippet,
                "source_url": _http_source_url(source),
            }
        )
    return citations


def _stitch_answer_html(hits: list[tuple[str, KnowledgeArticle]]) -> str:
    lead_chunk, lead_art = hits[0]
    lead = lead_art.summary or lead_chunk[:80]
    paragraphs = [f"<p><strong>{html.escape(lead)}</strong></p>"]
    for i, (chunk, _art) in enumerate(hits):
        text = chunk.replace("。", "。\n").split("\n")
        if i == 0:
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


def _generate_llm_answer(question: str, hits: list[tuple[str, KnowledgeArticle]]) -> str:
    docs = []
    for i, (chunk, art) in enumerate(hits, start=1):
        docs.append(
            f"[{i}] 标题：{art.title}\n"
            f"来源：{art.source_label or '知识条目'} · 版本：{art.version}\n"
            f"摘要：{art.summary or ''}\n"
            f"相关片段：{chunk}"
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


def _record_gap(db: Session, question: str) -> None:
    keyword = question.strip()[:200]
    if not keyword:
        return
    gap = db.query(KnowledgeGap).filter(KnowledgeGap.keyword == keyword).first()
    if gap:
        gap.hit_count = int(gap.hit_count or 0) + 1
        gap.last_asked_at = _now()
    else:
        db.add(KnowledgeGap(keyword=keyword, hit_count=1, last_asked_at=_now()))


def _save_ask(db: Session, user: User, question: str, matched_count: int) -> KnowledgeAsk:
    row = KnowledgeAsk(user_id=user.id, question=question, matched_count=matched_count)
    db.add(row)
    db.flush()
    return row


def ask(db: Session, user: User, payload: KnowledgeAskRequest) -> dict:
    from app.services.ai_admin import scene_enabled

    q = payload.question.strip()
    if not scene_enabled(db, "knowledge_ask"):
        return {
            "question": q,
            "answer_html": "<p>知识问答已停用，请联系管理员或改走人工查询。</p>",
            "citations": [],
            "retrieved_at": _now().strftime("%H:%M"),
            "matched_count": 0,
            "answer_mode": ANSWER_MODE_RETRIEVE,
            "ask_id": None,
        }
    _ensure_spaces(db)
    tokens = _tokenize(q)

    query = (
        db.query(KnowledgeArticle)
        .outerjoin(KnowledgeSource, KnowledgeArticle.source_id == KnowledgeSource.id)
        .filter(KnowledgeArticle.status == ARTICLE_STATUS_PUBLISHED)
        .filter(
            or_(
                KnowledgeArticle.source_id.is_(None),
                (KnowledgeSource.status != SOURCE_STATUS_REVOKED) & (KnowledgeSource.authorized.is_(True)),
            )
        )
    )
    if payload.space_id:
        sp = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == payload.space_id).first()
        if sp and sp.code != "all":
            query = query.filter(KnowledgeArticle.space_id == payload.space_id)

    candidates: list[tuple[int, str, KnowledgeArticle]] = []
    dirty = False
    for art in query.all():
        if art.attachments_json and not (art.attachment_text or "").strip():
            _refresh_attachment_text(art)
            dirty = True
        s, chunk = _score_article(art, tokens)
        if s > 0:
            candidates.append((s, chunk, art))
    if dirty:
        db.commit()
    candidates.sort(key=lambda x: -x[0])
    top_hits = [(chunk, art) for _, chunk, art in candidates[:3]]

    if not top_hits:
        _record_gap(db, q)
        ask_row = _save_ask(db, user, q, 0)
        db.commit()
        return {
            "question": q,
            "answer_html": (
                "<p><strong>未在已发布知识中找到足够依据。</strong></p>"
                "<p>请更换关键词，或由管理员接入飞书云文档、录入制度条目。已登记知识缺失。</p>"
            ),
            "citations": [],
            "retrieved_at": _now().strftime("%H:%M"),
            "matched_count": 0,
            "answer_mode": ANSWER_MODE_RETRIEVE,
            "ask_id": ask_row.id,
        }

    citations = _build_citations(db, top_hits)
    answer_mode = ANSWER_MODE_RETRIEVE
    answer_html = _stitch_answer_html(top_hits)

    if llm_service.is_llm_configured():
        try:
            answer_html = _generate_llm_answer(q, top_hits)
            answer_mode = ANSWER_MODE_LLM
        except llm_service.LlmError as exc:
            logger.warning("knowledge RAG LLM fallback: %s", exc)

    ask_row = _save_ask(db, user, q, len(citations))
    db.commit()
    return {
        "question": q,
        "answer_html": answer_html,
        "citations": citations,
        "retrieved_at": _now().strftime("%H:%M"),
        "matched_count": len(citations),
        "answer_mode": answer_mode,
        "ask_id": ask_row.id,
    }


def _require_manage(user: User) -> None:
    if not can_manage_knowledge(user):
        raise HTTPException(status_code=403, detail="无权管理知识库")


def _get_source(db: Session, source_id: int) -> KnowledgeSource:
    source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="知识源不存在")
    return source


def _get_article(db: Session, article_id: int) -> KnowledgeArticle:
    article = db.query(KnowledgeArticle).filter(KnowledgeArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    return article


def _bump_version(current: str | None) -> str:
    raw = (current or "1").lstrip("Vv")
    try:
        return str(int(raw.split(".")[0]) + 1)
    except ValueError:
        return "2"


def _chunks(text: str, size: int = 500) -> list[str]:
    body = text or ""
    return [body[i : i + size] for i in range(0, len(body), size)] or [""]


def list_sources(
    db: Session,
    *,
    status: str | None = None,
    source_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    q = db.query(KnowledgeSource)
    if status:
        q = q.filter(KnowledgeSource.status == status)
    if source_type:
        q = q.filter(KnowledgeSource.source_type == source_type)
    total = q.count()
    rows = (
        q.order_by(KnowledgeSource.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": [enrich_source(db, s) for s in rows]}


def get_source(db: Session, source_id: int) -> KnowledgeSource:
    return enrich_source(db, _get_source(db, source_id))


def source_sync_status(db: Session, source_id: int) -> dict:
    source = enrich_source(db, _get_source(db, source_id))
    return {
        "source_id": source.id,
        "status": source.status,
        "last_sync_at": source.last_sync_at,
        "article_count": getattr(source, "article_count", 0),
        "sync_error": source.sync_error,
    }


async def resync_source(db: Session, user: User, source_id: int) -> KnowledgeSource:
    _require_manage(user)
    source = _get_source(db, source_id)
    if source.status == SOURCE_STATUS_REVOKED:
        raise HTTPException(status_code=400, detail="来源已失效，无法同步")
    job = KnowledgeJob(source_id=source.id, job_type="resync", status=JOB_STATUS_RUNNING)
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        result = await sync_feishu_source(db, user, source.id)
        job.status = JOB_STATUS_DONE
        job.finished_at = _now()
        db.commit()
        return result
    except HTTPException as exc:
        job.status = JOB_STATUS_FAILED
        job.error = str(exc.detail)[:300]
        job.finished_at = _now()
        db.commit()
        raise


def revoke_source(db: Session, user: User, source_id: int) -> KnowledgeSource:
    _require_manage(user)
    source = _get_source(db, source_id)
    source.status = SOURCE_STATUS_REVOKED
    source.authorized = False
    for art in db.query(KnowledgeArticle).filter(KnowledgeArticle.source_id == source.id).all():
        if art.status == ARTICLE_STATUS_PUBLISHED:
            art.status = ARTICLE_STATUS_DISABLED
    db.commit()
    db.refresh(source)
    return enrich_source(db, source)


def list_entries(
    db: Session,
    user: User,
    *,
    source_id: int | None = None,
    status: str | None = None,
    space_id: int | None = None,
    keyword: str | None = None,
    origin: str | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    q = db.query(KnowledgeArticle)
    if not can_manage_knowledge(user):
        status = ARTICLE_STATUS_PUBLISHED
    if source_id:
        q = q.filter(KnowledgeArticle.source_id == source_id)
    if status:
        q = q.filter(KnowledgeArticle.status == status)
    if space_id:
        sp = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == space_id).first()
        if sp and sp.code != "all":
            q = q.filter(KnowledgeArticle.space_id == space_id)
    if origin == ARTICLE_ORIGIN_AI:
        q = q.filter(
            KnowledgeArticle.origin.in_([ARTICLE_ORIGIN_FEISHU_DOC, ARTICLE_ORIGIN_FEISHU_CHAT])
        )
    elif origin:
        q = q.filter(KnowledgeArticle.origin == origin)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(
            or_(
                KnowledgeArticle.title.ilike(like),
                KnowledgeArticle.summary.ilike(like),
                KnowledgeArticle.content.ilike(like),
                KnowledgeArticle.attachment_text.ilike(like),
                KnowledgeArticle.keywords.ilike(like),
            )
        )
    sort_key = (sort or SORT_RECENT).strip() or SORT_RECENT
    if sort_key not in ENTRY_SORTS:
        raise HTTPException(status_code=400, detail="sort 仅支持 recent / title")
    order = (
        KnowledgeArticle.title.asc()
        if sort_key == SORT_TITLE
        else KnowledgeArticle.updated_at.desc()
    )
    total = q.count()
    rows = q.order_by(order).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [enrich_article(db, a) for a in rows]}


def get_entry(db: Session, article_id: int, user: User | None = None) -> KnowledgeArticle:
    article = enrich_article(db, _get_article(db, article_id))
    if user and not can_manage_knowledge(user) and article.status != ARTICLE_STATUS_PUBLISHED:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    article.chunks = _chunks(article.content)  # type: ignore[attr-defined]
    return article


def download_attachment(db: Session, user: User, article_id: int, index: int) -> tuple[Path, str]:
    from app.services import uploads as upload_service

    article = get_entry(db, article_id, user)
    atts = getattr(article, "attachments", None) or []
    if index < 0 or index >= len(atts):
        raise HTTPException(status_code=404, detail="附件不存在")
    att = atts[index]
    return upload_service.resolve_stored_file(att["path"]), att["filename"]


def review_entry(db: Session, user: User, article_id: int) -> KnowledgeArticle:
    _require_manage(user)
    article = _get_article(db, article_id)
    if article.status not in {ARTICLE_STATUS_PENDING_REVIEW, ARTICLE_STATUS_REVIEWED}:
        raise HTTPException(status_code=400, detail="仅待审核条目可以审核")
    article.status = ARTICLE_STATUS_REVIEWED
    db.commit()
    db.refresh(article)
    return enrich_article(db, article)


def publish_entry(db: Session, user: User, article_id: int) -> KnowledgeArticle:
    _require_manage(user)
    article = _get_article(db, article_id)
    if article.status not in {
        ARTICLE_STATUS_PENDING_REVIEW,
        ARTICLE_STATUS_REVIEWED,
        ARTICLE_STATUS_DISABLED,
        ARTICLE_STATUS_DRAFT,
    }:
        raise HTTPException(status_code=400, detail="当前状态不可发布")
    if article.attachments_json and not (article.attachment_text or "").strip():
        _refresh_attachment_text(article)
    article.status = ARTICLE_STATUS_PUBLISHED
    article.published_at = date.today()
    db.commit()
    db.refresh(article)
    return enrich_article(db, article)


def disable_entry(db: Session, user: User, article_id: int) -> KnowledgeArticle:
    _require_manage(user)
    article = _get_article(db, article_id)
    if article.status != ARTICLE_STATUS_PUBLISHED:
        raise HTTPException(status_code=400, detail="仅已发布条目可以停用")
    article.status = ARTICLE_STATUS_DISABLED
    db.commit()
    db.refresh(article)
    return enrich_article(db, article)


def archive_entry(db: Session, user: User, article_id: int) -> KnowledgeArticle:
    _require_manage(user)
    article = _get_article(db, article_id)
    if article.status == ARTICLE_STATUS_ARCHIVED:
        raise HTTPException(status_code=400, detail="条目已归档")
    article.status = ARTICLE_STATUS_ARCHIVED
    db.commit()
    db.refresh(article)
    return enrich_article(db, article)


def delete_entry(db: Session, user: User, article_id: int) -> None:
    _require_manage(user)
    article = _get_article(db, article_id)
    db.query(KnowledgeArticleVersion).filter(KnowledgeArticleVersion.article_id == article.id).delete()
    db.delete(article)
    db.commit()


def patch_entry(
    db: Session, user: User, article_id: int, payload: KnowledgeArticlePatch
) -> KnowledgeArticle:
    _require_manage(user)
    article = _get_article(db, article_id)
    if article.status not in {ARTICLE_STATUS_DRAFT, ARTICLE_STATUS_REJECTED}:
        raise HTTPException(status_code=400, detail="仅草稿或已退回条目可以保存")
    data = payload.model_dump(exclude_unset=True)
    if "space_id" in data:
        _validate_space(db, data["space_id"], required=True)
        article.space_id = data["space_id"]
    if "title" in data and data["title"]:
        article.title = data["title"].strip()
    if "content" in data and data["content"]:
        article.content = data["content"].strip()
    if "summary" in data:
        article.summary = _auto_summary(article.content, data["summary"])
    elif "content" in data:
        article.summary = _auto_summary(article.content, article.summary)
    if "keywords" in data:
        article.keywords = (data["keywords"] or "").strip() or None
    if "doc_type" in data and data["doc_type"]:
        article.doc_type = _normalize_doc_type(data["doc_type"])
    if "source_url" in data:
        article.source_url = _valid_http_url(data["source_url"])
    if "source_note" in data:
        article.source_note = (data["source_note"] or "").strip() or None
    if "visibility" in data or "visibility_department" in data:
        visibility, department = _normalize_visibility(
            data["visibility"] if "visibility" in data else article.visibility,
            data["visibility_department"]
            if "visibility_department" in data
            else article.visibility_department,
        )
        article.visibility = visibility
        article.visibility_department = department
    if "expires_at" in data:
        article.expires_at = data["expires_at"]
    if "attachments" in data or "attachment" in data:
        article.attachments_json = _dump_attachments(
            _normalize_attachments(_payload_attachments(data.get("attachments"), data.get("attachment")))
        )
        _refresh_attachment_text(article)
    if article.status == ARTICLE_STATUS_REJECTED:
        article.status = ARTICLE_STATUS_DRAFT
    db.commit()
    db.refresh(article)
    return enrich_article(db, article)


def submit_entry(db: Session, user: User, article_id: int) -> KnowledgeArticle:
    _require_manage(user)
    article = _get_article(db, article_id)
    if article.status not in {ARTICLE_STATUS_DRAFT, ARTICLE_STATUS_REJECTED}:
        raise HTTPException(status_code=400, detail="仅草稿或已退回条目可以提交审核")
    _ensure_not_expired(article.expires_at)
    article.status = ARTICLE_STATUS_PENDING_REVIEW
    article.reject_reason = None
    db.commit()
    db.refresh(article)
    return enrich_article(db, article)


def approve_entry(
    db: Session, user: User, article_id: int, payload: KnowledgeApproveIn | None = None
) -> KnowledgeArticle:
    _require_manage(user)
    article = _get_article(db, article_id)
    if article.status not in {
        ARTICLE_STATUS_PENDING_REVIEW,
        ARTICLE_STATUS_REVIEWED,
    }:
        raise HTTPException(status_code=400, detail="仅待审核条目可通过入库")
    payload = payload or KnowledgeApproveIn()
    new_title = (payload.title or article.title).strip()
    new_content = (payload.content or article.content).strip()
    edited = bool(payload.title or payload.content or payload.summary is not None)
    if edited and (new_title != article.title or new_content != article.content):
        db.add(
            KnowledgeArticleVersion(
                article_id=article.id,
                version=article.version,
                title=article.title,
                content=article.content,
                summary=article.summary,
                change_reason="审核修订后通过",
                created_by=user.id,
            )
        )
        article.version = _bump_version(article.version)
    article.title = new_title
    article.content = new_content
    if payload.summary is not None:
        article.summary = _auto_summary(new_content, payload.summary)
    elif payload.content:
        article.summary = _auto_summary(new_content)
    if article.attachments_json and not (article.attachment_text or "").strip():
        _refresh_attachment_text(article)
    article.status = ARTICLE_STATUS_PUBLISHED
    article.published_at = date.today()
    article.reject_reason = None
    db.commit()
    db.refresh(article)
    return enrich_article(db, article)


def reject_entry(
    db: Session, user: User, article_id: int, reason: str
) -> KnowledgeArticle:
    _require_manage(user)
    article = _get_article(db, article_id)
    if article.status not in {
        ARTICLE_STATUS_PENDING_REVIEW,
        ARTICLE_STATUS_REVIEWED,
    }:
        raise HTTPException(status_code=400, detail="仅待审核条目可退回修改")
    text = (reason or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请填写修改意见")
    article.reject_reason = text[:500]
    article.status = ARTICLE_STATUS_DRAFT
    db.commit()
    db.refresh(article)
    return enrich_article(db, article)


def get_sync_config(db: Session, user: User) -> dict:
    _require_manage(user)
    _ensure_spaces(db)
    sources = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.status != SOURCE_STATUS_REVOKED)
        .order_by(KnowledgeSource.id.desc())
        .all()
    )
    return {
        "crawl_enabled": _crawl_enabled(db),
        "chats": [enrich_source(db, s) for s in sources if s.source_type == SOURCE_TYPE_FEISHU_CHAT],
        "folders": [enrich_source(db, s) for s in sources if s.source_type == SOURCE_TYPE_FEISHU_DOC],
    }


def patch_sync_config(db: Session, user: User, crawl_enabled: bool) -> dict:
    _require_manage(user)
    _set_crawl_enabled(db, user, crawl_enabled)
    db.commit()
    return get_sync_config(db, user)


async def add_whitelist(
    db: Session, user: User, source_type: str, payload: KnowledgeWhitelistCreate
) -> KnowledgeSource:
    _require_manage(user)
    return await create_source(
        db,
        user,
        KnowledgeSourceCreate(
            name=payload.name,
            source_type=source_type,
            space_id=payload.space_id,
            external_ref=payload.external_ref,
            auto_sync=False,
        ),
    )


def list_versions(db: Session, article_id: int) -> list[KnowledgeArticleVersion]:
    _get_article(db, article_id)
    return (
        db.query(KnowledgeArticleVersion)
        .filter(KnowledgeArticleVersion.article_id == article_id)
        .order_by(KnowledgeArticleVersion.id.desc())
        .all()
    )


def correct_entry(
    db: Session, user: User, article_id: int, payload: KnowledgeCorrectionIn
) -> KnowledgeArticle:
    _require_manage(user)
    article = _get_article(db, article_id)
    db.add(
        KnowledgeArticleVersion(
            article_id=article.id,
            version=article.version,
            title=article.title,
            content=article.content,
            summary=article.summary,
            change_reason=(payload.reason or "").strip() or "纠错",
            created_by=user.id,
        )
    )
    article.title = (payload.title or article.title).strip()
    article.content = payload.content.strip()
    article.summary = _auto_summary(article.content, payload.summary)
    article.version = _bump_version(article.version)
    article.status = ARTICLE_STATUS_PENDING_REVIEW
    db.commit()
    db.refresh(article)
    return enrich_article(db, article)


def list_jobs(db: Session, *, page: int = 1, page_size: int = 20) -> dict:
    q = db.query(KnowledgeJob)
    total = q.count()
    rows = (
        q.order_by(KnowledgeJob.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": rows}


async def retry_job(db: Session, user: User, job_id: int) -> KnowledgeJob:
    _require_manage(user)
    job = db.query(KnowledgeJob).filter(KnowledgeJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not job.source_id:
        raise HTTPException(status_code=400, detail="任务没有关联来源")
    await resync_source(db, user, job.source_id)
    db.refresh(job)
    latest = (
        db.query(KnowledgeJob)
        .filter(KnowledgeJob.source_id == job.source_id)
        .order_by(KnowledgeJob.id.desc())
        .first()
    )
    return latest or job


def create_feedback(
    db: Session, user: User, ask_id: int, payload: KnowledgeFeedbackIn
) -> KnowledgeFeedback:
    kind = (payload.kind or "").strip()
    if kind not in {FEEDBACK_USEFUL, FEEDBACK_USELESS, FEEDBACK_CORRECTION}:
        raise HTTPException(status_code=400, detail="反馈类型无效")
    ask_row = db.query(KnowledgeAsk).filter(KnowledgeAsk.id == ask_id).first()
    if not ask_row:
        raise HTTPException(status_code=404, detail="问答记录不存在")
    row = KnowledgeFeedback(
        ask_id=ask_id,
        user_id=user.id,
        kind=kind,
        content=(payload.content or "").strip() or None,
        status=FEEDBACK_PENDING,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    row.question = ask_row.question  # type: ignore[attr-defined]
    return row


def list_feedback(db: Session, *, status: str | None = None) -> list[KnowledgeFeedback]:
    q = db.query(KnowledgeFeedback)
    if status:
        q = q.filter(KnowledgeFeedback.status == status)
    rows = q.order_by(KnowledgeFeedback.id.desc()).limit(200).all()
    ask_ids = [r.ask_id for r in rows]
    asks = {
        a.id: a.question
        for a in db.query(KnowledgeAsk).filter(KnowledgeAsk.id.in_(ask_ids)).all()
    } if ask_ids else {}
    for r in rows:
        r.question = asks.get(r.ask_id)  # type: ignore[attr-defined]
    return rows


def patch_feedback(
    db: Session, user: User, feedback_id: int, payload: KnowledgeFeedbackPatch
) -> KnowledgeFeedback:
    _require_manage(user)
    row = db.query(KnowledgeFeedback).filter(KnowledgeFeedback.id == feedback_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="反馈不存在")
    if payload.status not in {FEEDBACK_ACCEPTED, FEEDBACK_REJECTED}:
        raise HTTPException(status_code=400, detail="处理状态无效")
    row.status = payload.status
    row.resolution = (payload.resolution or "").strip() or None
    db.commit()
    db.refresh(row)
    ask_row = db.query(KnowledgeAsk).filter(KnowledgeAsk.id == row.ask_id).first()
    row.question = ask_row.question if ask_row else None  # type: ignore[attr-defined]
    return row


def list_gaps(db: Session) -> list[KnowledgeGap]:
    return db.query(KnowledgeGap).order_by(KnowledgeGap.hit_count.desc(), KnowledgeGap.id.desc()).limit(200).all()


def knowledge_stats(db: Session) -> dict:
    def _cnt(model, **filters):
        q = db.query(func.count(model.id))
        for k, v in filters.items():
            q = q.filter(getattr(model, k) == v)
        return int(q.scalar() or 0)

    ask_count = _cnt(KnowledgeAsk)
    no_result = int(
        db.query(func.count(KnowledgeAsk.id)).filter(KnowledgeAsk.matched_count == 0).scalar() or 0
    )
    hit_rate = round((ask_count - no_result) / ask_count, 4) if ask_count else 0.0
    return {
        "total_articles": _cnt(KnowledgeArticle),
        "published": _cnt(KnowledgeArticle, status=ARTICLE_STATUS_PUBLISHED),
        "pending_review": _cnt(KnowledgeArticle, status=ARTICLE_STATUS_PENDING_REVIEW)
        + _cnt(KnowledgeArticle, status=ARTICLE_STATUS_REVIEWED),
        "disabled": _cnt(KnowledgeArticle, status=ARTICLE_STATUS_DISABLED),
        "archived": _cnt(KnowledgeArticle, status=ARTICLE_STATUS_ARCHIVED),
        "sources_active": _cnt(KnowledgeSource, status=SOURCE_STATUS_ACTIVE),
        "sources_failed": _cnt(KnowledgeSource, status=SOURCE_STATUS_FAILED),
        "ask_count": ask_count,
        "ask_hit_rate": hit_rate,
        "no_result_count": no_result,
        "feedback_pending": _cnt(KnowledgeFeedback, status=FEEDBACK_PENDING),
    }
