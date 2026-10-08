# AI 改造方案（交给 Cursor 执行）

> 目标：把现有智能体和知识库 RAG 从"能跑"提升到"能用"。
> 原则：懒 = 最少代码、最少依赖、复用已有能力。不上向量库、不换模型、不加新进程。

---

## 现状快照

- 智能体：`backend/app/agent/`，LangGraph（agent → confirm → tools），13 个工具，DeepSeek。P0-1 已完成（checkpoint 已切 `SqliteSaver`）。
- 知识库 RAG：`backend/app/services/knowledge.py`，中文 2/3-gram 关键词 LIKE 打分，top-3 整篇塞 prompt。
- 权限：`backend/app/core/rbac.py:122` 的 `user_can(user, permission_code)` 是唯一入口。

---

## 执行清单（按顺序）

### ✅ P0-1 · LangGraph checkpoint 落库（已完成，无需再做）

已修改：`backend/app/agent/graph.py`、`backend/app/config.py`、`backend/requirements.txt`。

---

### ▶ P0-2 · 知识库长文分块检索

**痛点**：`knowledge.py:345 _score_article` 在整篇 content 上打分，命中的整篇塞进 LLM prompt。文章长时噪声大、命中不精、context 撑爆。

**做法**：**检索时切块**，不改表结构、不入库、不加字段。

**改文件**：`backend/app/services/knowledge.py`

**新增函数**（放在 `_score_article` 之前）：

```python
CHUNK_SIZE = 500      # 字符
CHUNK_OVERLAP = 80

def _chunk_text(text: str) -> list[str]:
    """按字符窗口切；中文按字符长度足够。"""
    text = (text or "").strip()
    if len(text) <= CHUNK_SIZE:
        return [text] if text else []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    return [text[i : i + CHUNK_SIZE] for i in range(0, len(text), step) if text[i : i + CHUNK_SIZE].strip()]
```

**改 `_score_article`（约 knowledge.py:345）**：改为返回 `(best_score, best_chunk)`：

```python
def _score_article(article: KnowledgeArticle, tokens: list[str]) -> tuple[int, str]:
    title = (article.title or "").lower()
    keywords = (article.keywords or "").lower()
    chunks = _chunk_text(article.content or "")
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
```

**改 `ask`（约 knowledge.py:430）**：把 `(score, chunk, article)` 一起存下，向 LLM 只传 chunk：

```python
candidates: list[tuple[int, str, KnowledgeArticle]] = []
for art in query.all():
    s, chunk = _score_article(art, tokens)
    if s > 0:
        candidates.append((s, chunk, art))
candidates.sort(key=lambda x: -x[0])
top = candidates[:3]  # 注意后续代码要跟着改：`_, _, art` 解包
```

**改 `_generate_llm_answer`**：签名从 `(question, articles)` 改为 `(question, hits)`，`hits` 是 `list[tuple[chunk, article]]`。docs 拼接时用 `chunk` 而非 `art.content`。

**验证**：
```bash
cd backend && python -m pytest tests/ -k knowledge -x
```
再手工在前端知识库页问一个长篇文章里靠尾部的关键词，看引用条 snippet 是否变成了尾部片段。

---

### ▶ P0-3 · 工具级 RBAC 兜底

**痛点**：`base.py:9 write_operation` 只标记"要确认"，不查权限。当前 service 层大多数会拦（如 `project.update_project` 内部有 rbac 校验），但工具直接调 service 时若某个 service 遗漏，LLM 可能越权。**加一层兜底守卫，一次到位。**

**改文件**：`backend/app/agent/tools/base.py`

**改为**：

```python
"""工具标记：写操作需人工确认 + 权限兜底。"""
from __future__ import annotations

from typing import Any, Callable, TypeVar

from fastapi import HTTPException

from app.agent.runtime import require_user
from app.core.rbac import user_can

F = TypeVar("F", bound=Callable[..., Any])


def write_operation(confirmation_prompt: str, *, permission: str | None = None) -> Callable[[F], F]:
    """标记为写操作；LangGraph 在执行前 interrupt 等待确认。
    permission 非空则在执行前查 RBAC，越权直接返回 error。
    """

    def decorator(func: F) -> F:
        func._requires_confirmation = True  # type: ignore[attr-defined]
        func._confirmation_prompt = confirmation_prompt  # type: ignore[attr-defined]
        func._required_permission = permission  # type: ignore[attr-defined]
        return func

    return decorator


def requires_confirmation(tool: Any) -> bool:
    return bool(getattr(tool, "_requires_confirmation", False))


def confirmation_prompt(tool: Any) -> str:
    return str(getattr(tool, "_confirmation_prompt", "确认执行该写操作？"))


def required_permission(tool: Any) -> str | None:
    return getattr(tool, "_required_permission", None)
```

**改 `backend/app/agent/graph.py` 的 `tool_node`**：在 `fn.invoke(...)` 前加权限检查：

```python
from app.agent.tools.base import required_permission
from app.core.rbac import user_can

# 在 fn.invoke 之前：
perm = required_permission(fn)
if perm and not user_can(user, perm):
    result = {"error": f"当前用户无权限执行 {call['name']}（需要 {perm}）"}
else:
    result = fn.invoke(call.get("args") or {})
```

**改现有工具声明**（补 permission 参数）：

- `backend/app/agent/tools/project.py:102` `update_project_manager` → `@write_operation("修改项目负责人", permission="project:update")`
- `backend/app/agent/tools/approval.py` 里 `act_on_approval` → `@write_operation("...", permission="approval:act")`

具体 permission code 参照 `docs/权限与侧栏可见性-对齐稿.md` 和 `app/core/rbac.py` 已定义的 code；找不到匹配的就先不传（不会退化，保持现状）。

**验证**：写测试或用低权限账号在前端 agent 里让它改一个不属于自己的项目负责人，应看到 `error: 当前用户无权限...` 而非改成功。

---

### ▶ P1-1 · 补写操作工具（3 个）

**痛点**：13 个工具里只 2 个是写操作，用户"少填业务表"的价值没兑现。

**加 3 个高频写工具**，都走 `@write_operation` + `interrupt` 确认：

1. **新建线索** `create_lead`
   - 文件：`backend/app/agent/tools/lead.py`（新建）
   - 参数：`company_name: str, contact_name: Optional[str], phone: Optional[str], source: Optional[str]`
   - 调用：`app.services.lead.create_lead(db, user, LeadCreate(...))`
   - 权限：`lead:create`

2. **新建客户** `create_customer`
   - 文件：`backend/app/agent/tools/customer.py`（现有，追加）
   - 参数：`name: str, industry: Optional[str], contact_phone: Optional[str]`
   - 调用：`app.services.customer.create_customer(db, user, CustomerCreate(...))`
   - 权限：`customer:create`

3. **创建 KR** `create_key_result`
   - 文件：`backend/app/agent/tools/okr.py`（现有，追加）
   - 参数：`okr_id: int, title: str, target_value: float, unit: Optional[str]`
   - 调用现有 okr service 的 KR 创建接口（按代码里实际函数名调整）
   - 权限：`okr:update`（KR 附属 OKR）

**统一模板**（照 `update_project_manager` 抄，注意用 `HTTPException` 捕获 service 抛的错并返回 `{"error": ...}`）：

```python
@write_operation("创建线索：{company_name}", permission="lead:create")
@tool
def create_lead(company_name: str, contact_name: Optional[str] = None,
                phone: Optional[str] = None, source: Optional[str] = None) -> dict:
    """新建销售线索（写操作，需要用户确认）。"""
    db, user = require_db(), require_user()
    try:
        lead = lead_service.create_lead(db, user, LeadCreate(
            company_name=company_name, contact_name=contact_name,
            phone=phone, source=source,
        ))
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}
    return {"status": "ok", "lead_id": lead.id, "company_name": lead.company_name,
            "message": f"已创建线索 {lead.company_name}"}
```

> ⚠️ `confirmation_prompt` 目前是**静态字符串**，`{company_name}` 不会自动填。要动态化需要改 `base.py` 让 prompt 是 callable。**先不改**，静态版够用（"创建线索"这一句已经足够让用户点确认）。改动态版属于 P2。

**注册工具**：在 `backend/app/agent/tools/__init__.py` 的 `ALL_TOOLS` 追加。

**改 prompts**：`backend/app/agent/prompts.py:22-34` 的"工具选择"表补三行：
```
- "新建/录入线索" → create_lead（写操作）
- "新建客户" → create_customer（写操作）
- "给某 OKR 加 KR" → create_key_result（写操作）
```

**验证**：前端 agent 里说"帮我新建一条 A 公司的线索"，走完确认流程后去线索页看是否真新建。

---

### ▶ P1-2 · page_context 增强：选中行 & 最近操作

**痛点**：`prompts.py:44` 现在只塞了 `page` 和 `project_id`。用户"把这几个改负责人"、"刚才那个项目"没上下文。

**改文件**：`backend/app/agent/prompts.py` + 前端 `frontend/src/api/agent.ts` 与 `frontend/src/components/agent/AgentDrawer.vue`（或 InputBox.vue，取实际发起 SSE 请求的地方）

**后端**（`prompts.py`）：

```python
SYSTEM_PROMPT += """
# 页面上下文
- 当前所在页面：{current_page}
- 当前项目 ID：{current_project_id}
- 选中的记录 ID 列表：{selected_ids}
- 用户最近一次成功操作：{last_action}
"""

# build_system_prompt 里补：
selected_ids=ctx.get("selected_ids") or [],
last_action=ctx.get("last_action") or "无",
```

**前端**：在触发 agent 请求前，把当前页的选中行 ID（大多数列表用了 ElTable 的 `@selection-change`，把 selectedRows.map(r=>r.id) 塞进 payload.page_context.selected_ids）。`last_action` 从 pinia store 里读（如果没有 store 记录最近操作，就先跳过这一项，只加 `selected_ids`）。

**验证**：项目列表页勾三个项目，问 agent "这几个项目现在都是谁负责的？"，看它调 `get_project_detail` 的 project_id 是否命中勾选的三个。

---

### ⏸ P2 · 需要触发条件才做

只在下述条件命中后再启动，别提前上：

- **向量检索**：文章过 500 篇 / 单篇过 10KB / 用户开始问"这个流程有没有例外""为什么这么规定"这种语义查询 / 有 eval 显示答对率系统性下降。
  - 到时的最懒路径：Postgres + pgvector（新表 `article_chunks(article_id, content, embedding vector(1024))` + HNSW），embedding 用 BGE-M3 或阿里百炼 text-embedding-v3。**不要**引入 Chroma/Qdrant/Milvus 独立进程。

- **飞书文档真同步**：当前 `authorize_source` 只翻 flag。真接入需飞书 wiki/doc 拉全文接口 + 定时任务 + 增量差分。工作量大，价值取决于团队真在飞书上写多少制度文档。**先不做**，等业务催了再做。

- **动态 confirmation prompt**：让 `_confirmation_prompt` 支持 callable，参数从工具调用 args 填模板。

---

## 落地顺序建议

1. P0-2（分块）· 1-2 小时 · **命中率立刻可测**
2. P0-3（工具 RBAC）· 30 分钟 · **安全兜底**
3. P1-1（3 个写工具）· 2-3 小时 · **用户价值最大**
4. P1-2（page_context）· 1 小时 · **交互体验**

全部做完约半天到一天。

---

## 通用注意事项（交给 Cursor 前必读）

- 源码常带只读属性（`-r--r--r--`），Cursor 改文件前若报权限拒绝，用 `chmod u+w <file>` 或在 Windows 上取消只读。
- **不要**改 Alembic 迁移；本项目 alembic-sqlite 有坑（见 `memory/alembic-sqlite-broken.md`），激活功能靠 `create_all` + seed。P0-2/P0-3/P1 全部不涉及表结构变更。
- 工具函数签名（`@tool` 装饰）里的类型注解和 docstring 会作为 LLM 的工具 schema，**docstring 必须写清楚"什么时候用"**，别只写"做什么"。
- 每加一个写工具，跟着改 `prompts.py` 的"工具选择"表，否则模型不知道什么时候调。
- 冒烟测试统一走：设置好 `LLM_API_KEY`，前端登录后打开 agent 抽屉，直接问。别只跑单测。
