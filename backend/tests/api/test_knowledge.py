"""知识库：侧栏、去演示数据、关键词检索、飞书文档同步。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.knowledge import KnowledgeArticle, KnowledgeSource, KnowledgeSpace
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services.knowledge import parse_feishu_doc_ref
from app.services.menu import build_menus_for_user, flatten_menu_paths


def _user(db: Session, username: str, *codes: str) -> User:
    role = Role(name=f"{username}-role", code=f"{username}_role", data_scope="company")
    db.add(role)
    db.flush()
    for code in codes:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if perm is None:
            perm = Permission(name=code, code=code, module="knowledge")
            db.add(perm)
            db.flush()
        role.permissions.append(perm)
    user = User(
        username=username,
        password_hash=hash_password("secret123"),
        real_name=username,
        is_active=True,
    )
    user.roles.append(role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_parse_feishu_doc_ref() -> None:
    kind, token, url = parse_feishu_doc_ref("https://ztxd.feishu.cn/docx/AbCdEfGh123")
    assert kind == "docx"
    assert token == "AbCdEfGh123"
    assert url.startswith("https://")
    kind, token, url = parse_feishu_doc_ref("https://ztxd.feishu.cn/wiki/WkToken99")
    assert kind == "wiki"
    assert token == "WkToken99"
    assert parse_feishu_doc_ref("https://ztxd.feishu.cn/docs/doccnABC")[0] == "doc"
    assert parse_feishu_doc_ref("https://ztxd.feishu.cn/sheets/shtcnABC")[0] == "sheet"
    assert parse_feishu_doc_ref("https://ztxd.feishu.cn/base/bascnABC")[0] == "bitable"


def test_mindnote_plain_text_keeps_outline() -> None:
    from app.services.knowledge import mindnote_plain_text

    text = mindnote_plain_text([
        {"node_id": "root", "texts": [{"text": {"content": "店铺管理"}}]},
        {"node_id": "child", "parent_id": "root", "texts": [{"text": {"content": "商品"}}], "notes": [{"text": {"content": "需上架"}}]},
    ])
    assert text == "店铺管理\n  商品\n  需上架"


def test_sheet_and_bitable_plain_text() -> None:
    from app.services.knowledge import bitable_plain_text, sheet_plain_text

    sheet = sheet_plain_text([{
        "title": "客户",
        "values": [["名称", "金额"], ["甲", 12], [None, None]],
        "truncated": True,
    }])
    assert sheet.startswith("客户\n名称 | 金额\n甲 | 12")
    assert "仅同步前 200 行" in sheet
    table = bitable_plain_text([{
        "name": "线索",
        "records": [{"fields": {"名称": "乙", "负责人": [{"name": "合成丙"}]}}],
    }])
    assert table == "线索\n名称 | 负责人\n乙 | 合成丙"


def test_auto_summary_strips_rich_text_table() -> None:
    from app.services.knowledge import _auto_summary

    html_doc = (
        '<table style="min-width: 75px;"><tr><th>场景</th>'
        "<td>项目验收</td></tr></table><p>注意核对清单。</p>"
    )
    summary = _auto_summary(html_doc)
    assert summary
    assert "<" not in summary
    assert "项目验收" in summary
    assert _auto_summary(html_doc, "延期必须走变更") == "延期必须走变更"


def test_knowledge_menu_visible(db_session: Session) -> None:
    user = _user(db_session, "kb_viewer", "knowledge:view")
    paths = flatten_menu_paths(build_menus_for_user(user))
    assert "/knowledge" in paths


def test_workbench_has_spaces_without_demo_articles(
    client: TestClient, db_session: Session
) -> None:
    _user(db_session, "kb_viewer", "knowledge:view")
    headers = _headers(client, "kb_viewer")
    resp = client.get("/api/v1/knowledge/workbench", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert {s["code"] for s in data["spaces"]} >= {"all", "policy", "delivery", "compliance"}
    assert data["articles"] == []
    assert data["total_published"] == 0


def test_create_knowledge_space(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    headers = _headers(client, "kb_mgr")
    resp = client.post(
        "/api/v1/knowledge/spaces",
        headers=headers,
        json={"name": "研发规范", "code": "rd_spec", "icon": "研"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "研发规范"
    assert data["code"] == "rd_spec"
    assert data["icon"] == "研"
    assert data["article_count"] == 0

    wb = client.get("/api/v1/knowledge/workbench", headers=headers)
    assert any(s["code"] == "rd_spec" for s in wb.json()["spaces"])

    dup = client.post(
        "/api/v1/knowledge/spaces",
        headers=headers,
        json={"name": "重复", "code": "rd_spec"},
    )
    assert dup.status_code == 400


def test_workbench_space_article_count_matches_entries(
    client: TestClient, db_session: Session
) -> None:
    """目录数量由 workbench 返回，与 entries total 一致（管理员含非已发布）。"""
    _user(db_session, "kb_cnt_mgr", "knowledge:view", "knowledge:manage")
    _user(db_session, "kb_cnt_viewer", "knowledge:view")
    mgr = _headers(client, "kb_cnt_mgr")
    viewer = _headers(client, "kb_cnt_viewer")

    wb0 = client.get("/api/v1/knowledge/workbench", headers=mgr).json()
    policy_id = next(s["id"] for s in wb0["spaces"] if s["code"] == "policy")
    delivery_id = next(s["id"] for s in wb0["spaces"] if s["code"] == "delivery")

    pub = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "已发布制度A",
            "space_id": policy_id,
            "content": "已发布正文",
            "action": "publish",
        },
    )
    assert pub.status_code == 200
    draft = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "草稿制度B",
            "space_id": policy_id,
            "content": "草稿正文",
            "action": "draft",
        },
    )
    assert draft.status_code == 200
    other = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "交付规范C",
            "space_id": delivery_id,
            "content": "交付正文",
            "action": "publish",
        },
    )
    assert other.status_code == 200

    wb = client.get("/api/v1/knowledge/workbench", headers=mgr).json()
    by_code = {s["code"]: s["article_count"] for s in wb["spaces"]}
    assert by_code["policy"] == 2
    assert by_code["delivery"] == 1
    assert by_code["all"] == 3

    entries_policy = client.get(
        "/api/v1/knowledge/entries",
        headers=mgr,
        params={"space_id": policy_id, "page": 1, "page_size": 1},
    ).json()
    assert entries_policy["total"] == by_code["policy"]

    wb_viewer = client.get("/api/v1/knowledge/workbench", headers=viewer).json()
    viewer_counts = {s["code"]: s["article_count"] for s in wb_viewer["spaces"]}
    assert viewer_counts["policy"] == 1
    assert viewer_counts["delivery"] == 1
    assert viewer_counts["all"] == 2


def test_purge_demo_seed_on_workbench(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_viewer", "knowledge:view")
    space = KnowledgeSpace(code="delivery", name="项目交付规范", icon="项", sort_order=2)
    db_session.add(space)
    db_session.flush()
    src = KnowledgeSource(
        name="项目交付规范云文档目录",
        source_type="feishu_doc",
        space_id=space.id,
        external_ref="wiki/delivery",
        status="active",
        authorized=True,
    )
    db_session.add(src)
    db_session.flush()
    db_session.add(
        KnowledgeArticle(
            title="项目变更与基线管理规范",
            space_id=space.id,
            source_id=src.id,
            content="演示正文",
            summary="延期必须走变更申请并保留原基线与新版本。",
            status="published",
        )
    )
    db_session.add(
        KnowledgeArticle(
            title="员工请假与排期冲突处理制度",
            space_id=space.id,
            content="演示正文",
            summary="排期冲突协调规则。",
            status="published",
        )
    )
    db_session.commit()

    headers = _headers(client, "kb_viewer")
    data = client.get("/api/v1/knowledge/workbench", headers=headers).json()
    titles = {a["title"] for a in data["articles"]}
    assert "项目变更与基线管理规范" not in titles
    assert "员工请假与排期冲突处理制度" not in titles


def test_manual_article_ask(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    headers = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=headers).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")

    created = client.post(
        "/api/v1/knowledge/articles",
        headers=headers,
        json={
            "title": "请假与排期冲突处理",
            "space_id": policy_id,
            "content": "排期冲突应先请求协调，由组织者调整时间或替换人员。",
            "keywords": "请假,排期,冲突",
        },
    )
    assert created.status_code == 200
    assert created.json()["status"] == "pending_review"

    missed = client.post(
        "/api/v1/knowledge/ask",
        headers=headers,
        json={"question": "请假和排期冲突怎么处理"},
    )
    assert missed.status_code == 200
    assert missed.json()["matched_count"] == 0

    published = client.post(
        "/api/v1/knowledge/articles",
        headers=headers,
        json={
            "title": "请假与排期冲突处理",
            "space_id": policy_id,
            "content": "排期冲突应先请求协调，由组织者调整时间或替换人员。",
            "keywords": "请假,排期,冲突",
            "action": "publish",
        },
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    asked = client.post(
        "/api/v1/knowledge/ask",
        headers=headers,
        json={"question": "请假和排期冲突怎么处理"},
    )
    assert asked.status_code == 200
    body = asked.json()
    assert body["matched_count"] >= 1
    assert body["citations"][0]["title"] == "请假与排期冲突处理"
    assert body["citations"][0]["source_url"] is None


def test_view_cannot_create_article(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_viewer", "knowledge:view")
    headers = _headers(client, "kb_viewer")
    wb = client.get("/api/v1/knowledge/workbench", headers=headers).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")
    resp = client.post(
        "/api/v1/knowledge/articles",
        headers=headers,
        json={"title": "x", "space_id": policy_id, "content": "y" * 8},
    )
    assert resp.status_code == 403


class _FakeDocClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get_wiki_node(self, token: str):
        return {}

    async def get_docx_meta(self, document_id: str):
        return {"title": "项目变更管理办法", "revision_id": 7}

    async def get_docx_raw_content(self, document_id: str):
        return "项目延期必须提交变更申请，审批完成前不得修改原基线。"


def test_feishu_doc_sync_creates_article(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    from app.services import knowledge as knowledge_service

    monkeypatch.setattr(knowledge_service, "get_feishu_client", lambda: _FakeDocClient())
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    headers = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=headers).json()
    delivery_id = next(s["id"] for s in wb["spaces"] if s["code"] == "delivery")

    resp = client.post(
        "/api/v1/knowledge/sources",
        headers=headers,
        json={
            "name": "变更管理办法",
            "source_type": "feishu_doc",
            "space_id": delivery_id,
            "external_ref": "https://ztxd.feishu.cn/docx/DocTokenAAA",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["authorized"] is True

    drafts = client.get(
        "/api/v1/knowledge/entries",
        headers=headers,
        params={"status": "pending_review", "origin": "ai"},
    )
    assert drafts.status_code == 200
    assert drafts.json()["total"] >= 1
    entry_id = drafts.json()["items"][0]["id"]
    assert drafts.json()["items"][0]["origin"] == "feishu_doc"
    assert drafts.json()["items"][0]["status"] == "pending_review"

    asked_before = client.post(
        "/api/v1/knowledge/ask",
        headers=headers,
        json={"question": "延期要不要走变更", "space_id": delivery_id},
    )
    assert asked_before.status_code == 200
    assert asked_before.json()["matched_count"] == 0

    approved = client.post(
        f"/api/v1/knowledge/entries/{entry_id}/approve",
        headers=headers,
        json={},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "published"

    asked = client.post(
        "/api/v1/knowledge/ask",
        headers=headers,
        json={"question": "延期要不要走变更", "space_id": delivery_id},
    )
    assert asked.status_code == 200
    body = asked.json()
    assert body["matched_count"] >= 1
    assert body["citations"][0]["source_url"] == "https://ztxd.feishu.cn/docx/DocTokenAAA"


def test_knowledge_governance_loop(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    headers = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=headers).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")

    created = client.post(
        "/api/v1/knowledge/articles",
        headers=headers,
        json={"title": "报销制度", "space_id": policy_id, "content": "报销需先提交申请单。", "action": "publish"},
    )
    assert created.status_code == 200
    entry_id = created.json()["id"]

    listed = client.get("/api/v1/knowledge/entries", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    detail = client.get(f"/api/v1/knowledge/entries/{entry_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["chunks"]

    disable = client.post(f"/api/v1/knowledge/entries/{entry_id}/disable", headers=headers)
    assert disable.status_code == 200
    assert disable.json()["status"] == "disabled"

    missed = client.post(
        "/api/v1/knowledge/ask",
        headers=headers,
        json={"question": "报销需先提交申请单怎么走"},
    )
    assert missed.status_code == 200
    assert missed.json()["matched_count"] == 0
    assert missed.json()["ask_id"]

    published = client.post(f"/api/v1/knowledge/entries/{entry_id}/publish", headers=headers)
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    asked = client.post(
        "/api/v1/knowledge/ask",
        headers=headers,
        json={"question": "报销需先提交申请单怎么走"},
    )
    assert asked.status_code == 200
    ask_id = asked.json()["ask_id"]
    assert asked.json()["matched_count"] >= 1

    fb = client.post(
        f"/api/v1/knowledge/ask/{ask_id}/feedback",
        headers=headers,
        json={"kind": "useful"},
    )
    assert fb.status_code == 200

    corr = client.post(
        f"/api/v1/knowledge/entries/{entry_id}/corrections",
        headers=headers,
        json={"content": "报销需先提交申请单，并附发票。", "reason": "补充发票"},
    )
    assert corr.status_code == 200
    assert corr.json()["status"] == "pending_review"

    versions = client.get(f"/api/v1/knowledge/entries/{entry_id}/versions", headers=headers)
    assert versions.status_code == 200
    assert len(versions.json()) == 1

    review = client.post(f"/api/v1/knowledge/entries/{entry_id}/review", headers=headers)
    assert review.status_code == 200
    assert review.json()["status"] == "reviewed"

    client.post(f"/api/v1/knowledge/entries/{entry_id}/publish", headers=headers)

    gaps = client.get("/api/v1/knowledge/gaps", headers=headers)
    assert gaps.status_code == 200
    assert len(gaps.json()) >= 1

    stats = client.get("/api/v1/knowledge/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["ask_count"] >= 1

    sources = client.get("/api/v1/knowledge/sources", headers=headers)
    assert sources.status_code == 200


def test_revoke_source_hides_from_ask(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    from app.services import knowledge as knowledge_service

    monkeypatch.setattr(knowledge_service, "get_feishu_client", lambda: _FakeDocClient())
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    headers = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=headers).json()
    delivery_id = next(s["id"] for s in wb["spaces"] if s["code"] == "delivery")

    created = client.post(
        "/api/v1/knowledge/sources",
        headers=headers,
        json={
            "name": "变更管理办法",
            "source_type": "feishu_doc",
            "space_id": delivery_id,
            "external_ref": "https://ztxd.feishu.cn/docx/DocTokenBBB",
        },
    )
    assert created.status_code == 200
    source_id = created.json()["id"]

    revoked = client.post(f"/api/v1/knowledge/sources/{source_id}/revoke", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    asked = client.post(
        "/api/v1/knowledge/ask",
        headers=headers,
        json={"question": "延期要不要走变更", "space_id": delivery_id},
    )
    assert asked.status_code == 200
    assert asked.json()["matched_count"] == 0


def test_agent_search_knowledge_tool(db_session: Session) -> None:
    from app.agent.runtime import agent_runtime
    from app.agent.tools.knowledge import search_knowledge
    from app.models.knowledge import KnowledgeArticle, KnowledgeSpace

    user = _user(db_session, "kb_agent", "knowledge:view")
    space = KnowledgeSpace(code="policy", name="制度", icon="制", sort_order=1)
    db_session.add(space)
    db_session.flush()
    db_session.add(
        KnowledgeArticle(
            title="报销制度",
            space_id=space.id,
            content="报销需先提交申请单。",
            status="published",
        )
    )
    db_session.commit()
    with agent_runtime(db_session, user):
        hit = search_knowledge.invoke({"question": "报销怎么走"})
        miss = search_knowledge.invoke({"question": "火星移民审批流程"})
    assert hit["found"] is True
    assert hit["citations"][0]["title"] == "报销制度"
    assert miss["found"] is False


def test_article_draft_submit_and_reject(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    mgr = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=mgr).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")

    created = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "Q&A 草稿",
            "space_id": policy_id,
            "content": "客户问交付周期时按合同约定答复。",
            "doc_type": "qa",
            "keywords": "交付,周期",
            "source_url": "https://ztxd.feishu.cn/docx/QaDraft001",
            "action": "draft",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "draft"
    assert body["origin"] == "manual"
    assert body["doc_type"] == "qa"
    assert body["attachments"] == []
    entry_id = body["id"]

    too_early = client.post(f"/api/v1/knowledge/entries/{entry_id}/approve", headers=mgr)
    assert too_early.status_code == 400
    too_early_rej = client.post(
        f"/api/v1/knowledge/entries/{entry_id}/reject",
        headers=mgr,
        json={"reason": "还没提交"},
    )
    assert too_early_rej.status_code == 400

    submitted = client.post(f"/api/v1/knowledge/entries/{entry_id}/submit", headers=mgr)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_review"

    missing_reason = client.post(f"/api/v1/knowledge/entries/{entry_id}/reject", headers=mgr, json={})
    assert missing_reason.status_code == 422

    rejected = client.post(
        f"/api/v1/knowledge/entries/{entry_id}/reject",
        headers=mgr,
        json={"reason": "请补充交付周期口径"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "draft"
    assert rejected.json()["reject_reason"] == "请补充交付周期口径"


def test_article_attachments_max_five(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    mgr = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=mgr).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")
    files = [{"filename": "cover.png", "path": "knowledge/cover.png"}] + [
        {"filename": f"a{i}.pdf", "path": f"knowledge/a{i}.pdf"} for i in range(4)
    ]
    created = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "带附件",
            "space_id": policy_id,
            "content": "正文",
            "action": "draft",
            "attachments": files,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    atts = body["attachments"]
    assert len(atts) == 5
    assert atts[0]["url"] == "/uploads/knowledge/cover.png"
    assert atts[0]["download_url"] == (
        f"/api/v1/knowledge/entries/{body['id']}/attachments/0/download"
    )
    assert body["attachment_name"] == "cover.png、a0.pdf、a1.pdf、a2.pdf、a3.pdf"
    assert body["images"] == ["/uploads/knowledge/cover.png"]
    assert body["source"] == "人工录入"
    assert body["origin"] == "manual"

    listed = client.get("/api/v1/knowledge/entries", headers=mgr)
    assert listed.status_code == 200
    hit = next(x for x in listed.json()["items"] if x["id"] == body["id"])
    assert hit["attachment_name"] == body["attachment_name"]
    assert hit["images"] == body["images"]

    too_many = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "超限",
            "space_id": policy_id,
            "content": "正文",
            "action": "draft",
            "attachments": files + [{"filename": "x.pdf", "path": "knowledge/x.pdf"}],
        },
    )
    assert too_many.status_code == 400

    single = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "单附件",
            "space_id": policy_id,
            "content": "正文",
            "action": "draft",
            "attachment": "/uploads/knowledge/e3e775237b616cc3f530289e1ef1bb_说明.pdf",
        },
    )
    assert single.status_code == 200, single.text
    one = single.json()["attachments"]
    assert len(one) == 1
    assert one[0]["path"] == "knowledge/e3e775237b616cc3f530289e1ef1bb_说明.pdf"
    assert one[0]["url"] == "/uploads/knowledge/e3e775237b616cc3f530289e1ef1bb_说明.pdf"
    assert single.json()["attachment_name"] == "e3e775237b616cc3f530289e1ef1bb_说明.pdf"


def test_download_attachment(client: TestClient, db_session: Session, tmp_path, monkeypatch) -> None:
    from app.services import uploads as upload_service

    monkeypatch.setattr(upload_service, "UPLOAD_ROOT", tmp_path)
    dest = tmp_path / "knowledge"
    dest.mkdir()
    payload = b"%PDF-1.4 talk"
    (dest / "talk.pdf").write_bytes(payload)

    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    mgr = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=mgr).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")

    draft = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "草稿附件",
            "space_id": policy_id,
            "content": "正文",
            "action": "draft",
            "attachments": [{"filename": "话术.pdf", "path": "knowledge/talk.pdf"}],
        },
    )
    assert draft.status_code == 200, draft.text
    draft_id = draft.json()["id"]
    got = client.get(
        f"/api/v1/knowledge/entries/{draft_id}/attachments/0/download",
        headers=mgr,
    )
    assert got.status_code == 200
    assert got.content == payload
    assert "attachment" in got.headers["content-disposition"].lower()

    missing = client.get(
        f"/api/v1/knowledge/entries/{draft_id}/attachments/3/download",
        headers=mgr,
    )
    assert missing.status_code == 404

    (dest / "talk.pdf").unlink()
    gone = client.get(
        f"/api/v1/knowledge/entries/{draft_id}/attachments/0/download",
        headers=mgr,
    )
    assert gone.status_code == 404


def test_viewer_lists_only_published(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_viewer", "knowledge:view")
    headers = _headers(client, "kb_viewer")
    wb = client.get("/api/v1/knowledge/workbench", headers=headers).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")
    db_session.add(
        KnowledgeArticle(
            title="未发布草稿",
            space_id=policy_id,
            content="不应被普通员工看到。",
            status="draft",
            origin="manual",
        )
    )
    db_session.commit()

    listed = client.get("/api/v1/knowledge/entries", headers=headers)
    assert listed.status_code == 200
    assert all(x["status"] == "published" for x in listed.json()["items"])
    assert all(x["title"] != "未发布草稿" for x in listed.json()["items"])


def test_approve_with_edit_and_direct_publish(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    headers = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=headers).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")

    created = client.post(
        "/api/v1/knowledge/articles",
        headers=headers,
        json={
            "title": "差旅报销口述",
            "space_id": policy_id,
            "content": "住宿上限待确认。",
            "action": "submit",
        },
    )
    assert created.status_code == 200
    entry_id = created.json()["id"]

    approved = client.post(
        f"/api/v1/knowledge/entries/{entry_id}/approve",
        headers=headers,
        json={"title": "差旅报销标准", "content": "住宿上限 500 元/晚。"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "published"
    assert approved.json()["title"] == "差旅报销标准"

    asked = client.post(
        "/api/v1/knowledge/ask",
        headers=headers,
        json={"question": "住宿上限多少"},
    )
    assert asked.status_code == 200
    assert asked.json()["matched_count"] >= 1


def test_feishu_sync_config_whitelist(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    headers = _headers(client, "kb_mgr")

    cfg = client.get("/api/v1/knowledge/sync-config", headers=headers)
    assert cfg.status_code == 200
    assert cfg.json()["crawl_enabled"] is True
    assert cfg.json()["chats"] == []
    assert cfg.json()["folders"] == []

    chat = client.post(
        "/api/v1/knowledge/sync-config/chats",
        headers=headers,
        json={"name": "销售-客户对接群", "external_ref": "oc-xxxx1"},
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["source_type"] == "feishu_chat"
    assert chat.json()["authorized"] is True
    chat_id = chat.json()["id"]

    folder = client.post(
        "/api/v1/knowledge/sync-config/folders",
        headers=headers,
        json={"name": "产品方案库", "external_ref": "fold-xxx2"},
    )
    assert folder.status_code == 200, folder.text
    assert folder.json()["source_type"] == "feishu_doc"
    folder_id = folder.json()["id"]

    listed = client.get("/api/v1/knowledge/sync-config", headers=headers).json()
    assert len(listed["chats"]) == 1
    assert len(listed["folders"]) == 1

    off = client.patch(
        "/api/v1/knowledge/sync-config",
        headers=headers,
        json={"crawl_enabled": False},
    )
    assert off.status_code == 200
    assert off.json()["crawl_enabled"] is False

    removed = client.delete(f"/api/v1/knowledge/sync-config/{chat_id}", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["status"] == "revoked"
    _ = folder_id


def test_create_article_summary_from_html_table(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    mgr = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=mgr).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")
    html_doc = (
        '<table style="min-width: 75px;"><colgroup><col style="min-width: 25px;"></colgroup>'
        "<tbody><tr><th>检查项</th><td>验收资料是否齐全</td></tr></tbody></table>"
    )
    created = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={"title": "验收检查", "space_id": policy_id, "content": html_doc, "action": "publish"},
    )
    assert created.status_code == 200, created.text
    summary = created.json()["summary"]
    assert summary
    assert "<table" not in summary
    assert "验收资料是否齐全" in summary

    listed = client.get("/api/v1/knowledge/entries", headers=mgr).json()
    row = next(x for x in listed["items"] if x["id"] == created.json()["id"])
    assert "<table" not in (row["summary"] or "")


def test_list_keyword_and_delete_entry(client: TestClient, db_session: Session) -> None:
    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    mgr = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=mgr).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")
    compliance_id = next(s["id"] for s in wb["spaces"] if s["code"] == "compliance")

    hit = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "请假与排期冲突处理",
            "space_id": policy_id,
            "content": "排期冲突应先请求协调。",
            "action": "publish",
        },
    )
    other = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "合规红线清单",
            "space_id": compliance_id,
            "content": "不得向客户承诺未审批折扣。",
            "action": "publish",
        },
    )
    assert hit.status_code == 200
    assert other.status_code == 200
    hit_id = hit.json()["id"]
    other_id = other.json()["id"]

    found = client.get(
        "/api/v1/knowledge/entries",
        headers=mgr,
        params={"keyword": "排期冲突", "status": "published"},
    )
    assert found.status_code == 200
    titles = {row["title"] for row in found.json()["items"]}
    assert "请假与排期冲突处理" in titles
    assert "合规红线清单" not in titles

    scoped = client.get(
        "/api/v1/knowledge/entries",
        headers=mgr,
        params={"space_id": compliance_id, "status": "published"},
    )
    assert scoped.status_code == 200
    assert {row["title"] for row in scoped.json()["items"]} == {"合规红线清单"}

    deleted = client.delete(f"/api/v1/knowledge/entries/{hit_id}", headers=mgr)
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/knowledge/entries/{hit_id}", headers=mgr).status_code == 404
    leftover = client.get(
        "/api/v1/knowledge/entries",
        headers=mgr,
        params={"keyword": "排期冲突", "status": "published"},
    )
    assert leftover.json()["total"] == 0
    assert client.get(f"/api/v1/knowledge/entries/{other_id}", headers=mgr).status_code == 200


def test_attachment_text_is_searchable(
    client: TestClient, db_session: Session, tmp_path, monkeypatch
) -> None:
    from app.services import attachment_extract, uploads as upload_service

    monkeypatch.setattr(upload_service, "UPLOAD_ROOT", tmp_path)
    dest = tmp_path / "knowledge"
    dest.mkdir()
    (dest / "lodging.pdf").write_bytes(b"%PDF-1.4 extract-me")
    monkeypatch.setattr(
        attachment_extract,
        "extract_attachment_text",
        lambda path: "独角兽差旅住宿上限八百元每晚" if path.name.endswith(".pdf") else "",
    )

    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    mgr = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=mgr).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")

    created = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "附件制度",
            "space_id": policy_id,
            "content": "见附件。",
            "action": "publish",
            "attachments": [{"filename": "lodging.pdf", "path": "knowledge/lodging.pdf"}],
        },
    )
    assert created.status_code == 200, created.text
    art = db_session.get(KnowledgeArticle, created.json()["id"])
    assert art is not None
    assert "八百元" in (art.attachment_text or "")

    asked = client.post(
        "/api/v1/knowledge/ask",
        headers=mgr,
        json={"question": "独角兽差旅住宿上限八百元吗"},
    )
    assert asked.status_code == 200
    assert asked.json()["matched_count"] >= 1


def test_article_editor_fields_and_sort(client: TestClient, db_session: Session) -> None:
    from datetime import date, timedelta

    _user(db_session, "kb_mgr", "knowledge:view", "knowledge:manage")
    mgr = _headers(client, "kb_mgr")
    wb = client.get("/api/v1/knowledge/workbench", headers=mgr).json()
    policy_id = next(s["id"] for s in wb["spaces"] if s["code"] == "policy")

    bad_vis = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "部门可见缺部门",
            "space_id": policy_id,
            "content": "正文",
            "action": "draft",
            "visibility": "department",
        },
    )
    assert bad_vis.status_code == 400

    expired = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "过期文档",
            "space_id": policy_id,
            "content": "正文",
            "action": "submit",
            "expires_at": (date.today() - timedelta(days=1)).isoformat(),
        },
    )
    assert expired.status_code == 400

    created = client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "验收检查清单",
            "space_id": policy_id,
            "content": "按清单核对交付物。",
            "action": "draft",
            "doc_type": "guide",
            "source_note": "基于交付组经验整理",
            "visibility": "department",
            "visibility_department": "项目交付部",
            "expires_at": (date.today() + timedelta(days=30)).isoformat(),
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["doc_type"] == "guide"
    assert body["source_note"] == "基于交付组经验整理"
    assert body["visibility"] == "department"
    assert body["visibility_department"] == "项目交付部"
    assert body["expires_at"] == (date.today() + timedelta(days=30)).isoformat()

    client.post(
        "/api/v1/knowledge/articles",
        headers=mgr,
        json={
            "title": "A 案例",
            "space_id": policy_id,
            "content": "案例正文",
            "action": "draft",
            "doc_type": "case",
        },
    )
    by_title = client.get("/api/v1/knowledge/entries", headers=mgr, params={"sort": "title"})
    assert by_title.status_code == 200
    titles = [x["title"] for x in by_title.json()["items"]]
    assert titles == sorted(titles)

