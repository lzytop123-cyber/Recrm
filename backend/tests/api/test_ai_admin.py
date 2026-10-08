"""Prompt、场景开关、token 限额、L1 自动通过。"""
from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.agent import AiSceneRun
from app.models.approval_flow import INSTANCE_APPROVED, INSTANCE_PENDING, TASK_ACTIVE, ApprovalInstance, ApprovalTask
from app.models.audit_log import AuditLog
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def _user(db: Session, username: str, *codes: str) -> User:
    role = Role(name=f"{username}-role", code=f"{username}_role", data_scope="company")
    for code in codes:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if perm is None:
            perm = Permission(name=code, code=code, module=code.split(":")[0])
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


def test_prompt_versions_and_publish(client: TestClient, db_session: Session) -> None:
    admin = _user(db_session, "ai_admin_prompt", "system:view", "system:manage")
    headers = _headers(client, admin.username)
    first = client.post(
        "/api/v1/ai/prompts",
        json={"code": "daily_report", "name": "日报", "content": "只用事实"},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    published = client.post(f"/api/v1/ai/prompts/{first.json()['id']}/publish", headers=headers)
    assert published.json()["status"] == "published"
    second = client.post(
        "/api/v1/ai/prompts",
        json={"code": "daily_report", "name": "日报", "content": "仍然只用事实"},
        headers=headers,
    )
    assert second.json()["version"] == 2
    client.post(f"/api/v1/ai/prompts/{second.json()['id']}/publish", headers=headers)
    detail = client.get(f"/api/v1/ai/prompts/{second.json()['id']}", headers=headers)
    versions = {item["version"]: item["status"] for item in detail.json()["versions"]}
    assert versions[1] == "archived"
    assert versions[2] == "published"


def test_scene_off_falls_back(client: TestClient, db_session: Session) -> None:
    admin = _user(db_session, "ai_admin_scene", "system:view", "system:manage", "approval:center")
    headers = _headers(client, admin.username)
    off = client.patch("/api/v1/ai/scenes/daily_report", json={"enabled": False}, headers=headers)
    assert off.status_code == 200
    blocked = client.post("/api/v1/agent/scenes/daily-report", json={}, headers=headers)
    assert blocked.status_code == 409
    inst = ApprovalInstance(
        code="AF-SCENE-OFF",
        biz_type="timesheet",
        biz_id=1,
        title="停用预审",
        summary="仍可人工审",
        status=INSTANCE_PENDING,
        current_seq=1,
        initiator_id=admin.id,
        initiator_name=admin.real_name,
        version=1,
    )
    db_session.add(inst)
    db_session.commit()
    client.patch("/api/v1/ai/scenes/approval_precheck", json={"enabled": False}, headers=headers)
    report = client.get(f"/api/v1/approvals/approval_instance:{inst.id}/precheck", headers=headers)
    assert report.status_code == 200, report.text
    assert report.json()["fallback"] == "manual"
    skipped = client.post(f"/api/v1/approvals/approval_instance:{inst.id}/auto-pass", headers=headers)
    assert skipped.json()["passed"] is False
    assert skipped.json()["level"] == "L3"
    db_session.refresh(inst)
    assert inst.status == INSTANCE_PENDING


def test_budget_blocks_and_is_audited(client: TestClient, db_session: Session) -> None:
    admin = _user(db_session, "ai_admin_budget", "system:view", "system:manage")
    headers = _headers(client, admin.username)
    saved = client.put(
        "/api/v1/ai/budgets",
        json={"items": [{"scope": "user", "scope_id": admin.id, "monthly_tokens": 0}], "auto_pass_max_amount": "1000"},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["auto_pass_max_amount"] == "1000"
    blocked = client.post("/api/v1/agent/scenes/daily-report", json={}, headers=headers)
    assert blocked.status_code == 429
    assert db_session.query(AuditLog).filter(AuditLog.target_id == "ai.budgets").count() == 1


def test_auto_pass_l1_and_spot_check(client: TestClient, db_session: Session) -> None:
    initiator = _user(db_session, "ai_initiator", "approval:center")
    approver = _user(
        db_session, "ai_approver", "approval:center", "system:view", "system:manage"
    )
    inst = ApprovalInstance(
        code="AF-L1",
        biz_type="timesheet",
        biz_id=2,
        title="低风险",
        summary="金额以内",
        amount=Decimal("100"),
        status=INSTANCE_PENDING,
        current_seq=1,
        initiator_id=initiator.id,
        initiator_name=initiator.real_name,
        version=1,
    )
    db_session.add(inst)
    db_session.flush()
    db_session.add(
        ApprovalTask(
            instance_id=inst.id,
            seq=1,
            name="确认",
            node_type="assignee",
            roles_json="[]",
            assignee_id=approver.id,
            status=TASK_ACTIVE,
        )
    )
    for _ in range(9):
        db_session.add(
            AiSceneRun(
                user_id=approver.id,
                scene="auto_pass",
                status="done",
                model_version="facts-v1",
                result={},
            )
        )
    db_session.commit()
    headers = _headers(client, approver.username)
    client.put(
        "/api/v1/ai/budgets",
        json={"items": [], "auto_pass_max_amount": "1000"},
        headers=headers,
    )
    resp = client.post(f"/api/v1/approvals/approval_instance:{inst.id}/auto-pass", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["passed"] is True
    assert body["level"] == "L1"
    assert body["spot_check_id"]
    db_session.refresh(inst)
    assert inst.status == INSTANCE_APPROVED
    calls = client.get("/api/v1/ai/calls", headers=headers)
    precheck = next(item for item in calls.json()["items"] if item["scene"] == "approval_precheck")
    detail = client.get(f"/api/v1/ai/calls/{precheck['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["tokens"] == 0
    assert "elapsed_ms" in detail.json()
    review = client.post(
        f"/api/v1/approvals/spot-checks/{body['spot_check_id']}/review",
        json={"conclusion": "pass", "comment": "抽查无误"},
        headers=headers,
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "reviewed"
