"""飞书审批通知：待办推送与催办频控。"""
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import hash_password
from app.models.approval_flow import (
    INSTANCE_PENDING,
    TASK_ACTIVE,
    ApprovalInstance,
    ApprovalTask,
)
from app.models.role import Role
from app.models.user import User
from app.services import approval_flow, feishu_notify


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _user(db: Session, username: str, *, open_id: str | None = None, roles: list[str] | None = None) -> User:
    u = User(
        username=username,
        password_hash=hash_password("secret123"),
        real_name=username,
        is_active=True,
        feishu_open_id=open_id,
    )
    for code in roles or []:
        role = db.query(Role).filter(Role.code == code).first()
        if not role:
            role = Role(name=code, code=code, data_scope="company")
            db.add(role)
            db.flush()
        u.roles.append(role)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _pending_instance(db: Session, initiator: User, assignee: User) -> ApprovalInstance:
    inst = ApprovalInstance(
        code="AF_TEST_001",
        rule_code="AP-TEST",
        biz_type="timesheet",
        biz_id=1,
        title="测试审批待办",
        summary="单元测试",
        status=INSTANCE_PENDING,
        current_seq=1,
        initiator_id=initiator.id,
        initiator_name=initiator.real_name,
        version=1,
    )
    db.add(inst)
    db.flush()
    db.add(
        ApprovalTask(
            instance_id=inst.id,
            seq=1,
            name="执行人确认",
            node_type="assignee",
            roles_json="[]",
            assignee_id=assignee.id,
            status=TASK_ACTIVE,
        )
    )
    db.commit()
    db.refresh(inst)
    return inst


def test_notify_skips_when_disabled(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "")
    monkeypatch.setenv("FEISHU_APP_SECRET", "")
    get_settings.cache_clear()
    initiator = _user(db_session, "n_init")
    assignee = _user(db_session, "n_asg", open_id="ou_assignee")
    inst = _pending_instance(db_session, initiator, assignee)
    assert feishu_notify.notify_active_approvers(db_session, inst) == 0


def test_notify_sends_to_bound_assignee(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec")
    monkeypatch.setenv("FEISHU_REDIRECT_URI", "http://127.0.0.1:5173/login/feishu/callback")
    monkeypatch.setenv("FEISHU_NOTIFY_ENABLED", "true")
    get_settings.cache_clear()

    initiator = _user(db_session, "s_init")
    assignee = _user(db_session, "s_asg", open_id="ou_assignee_1")
    inst = _pending_instance(db_session, initiator, assignee)

    with patch("app.services.feishu_notify.send_text_to_open_id", return_value=True) as send:
        n = feishu_notify.notify_active_approvers(db_session, inst)
    assert n == 1
    assert send.call_count == 1
    assert send.call_args.args[0] == "ou_assignee_1"
    assert "审批待办" in send.call_args.args[1]


def test_remind_rate_limit(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec")
    monkeypatch.setenv("FEISHU_REDIRECT_URI", "http://127.0.0.1:5173/login/feishu/callback")
    get_settings.cache_clear()

    initiator = _user(db_session, "r_init", roles=["admin"])
    assignee = _user(db_session, "r_asg", open_id="ou_r")
    inst = _pending_instance(db_session, initiator, assignee)

    with patch("app.services.feishu_notify.send_text_to_open_id", return_value=True):
        feishu_notify.remind_approvers(db_session, initiator, inst)
        with pytest.raises(HTTPException) as ei:
            feishu_notify.remind_approvers(db_session, initiator, inst)
    assert ei.value.status_code == 429


def test_notify_initiator_on_approve_reject(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec")
    monkeypatch.setenv("FEISHU_REDIRECT_URI", "http://127.0.0.1:5173/login/feishu/callback")
    monkeypatch.setenv("FEISHU_NOTIFY_ENABLED", "true")
    get_settings.cache_clear()

    initiator = _user(db_session, "res_init", open_id="ou_initiator")
    assignee = _user(db_session, "res_asg", open_id="ou_asg")
    inst = _pending_instance(db_session, initiator, assignee)
    inst.reject_reason = "材料不全"

    with patch("app.services.feishu_notify.send_text_to_open_id", return_value=True) as send:
        assert feishu_notify.notify_initiator_result(db_session, inst, approved=True) == 1
        assert feishu_notify.notify_initiator_result(db_session, inst, approved=False) == 1
    assert send.call_count == 2
    assert send.call_args_list[0].args[0] == "ou_initiator"
    assert "审批已通过" in send.call_args_list[0].args[1]
    assert "审批已驳回" in send.call_args_list[1].args[1]
    assert "材料不全" in send.call_args_list[1].args[1]


def test_advance_triggers_notify(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """_advance 激活节点后会尝试通知（mock 发送）。"""
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec")
    monkeypatch.setenv("FEISHU_REDIRECT_URI", "http://127.0.0.1:5173/cb")
    get_settings.cache_clear()

    initiator = _user(db_session, "a_init")
    assignee = _user(db_session, "a_asg", open_id="ou_a")
    from app.models.approval_rule import RULE_STATUS_PUBLISHED, ApprovalRule
    import json

    rule = ApprovalRule(
        code="AP-NOTIFY",
        name="通知测试",
        biz_type="schedule",
        nodes_json=json.dumps(
            {"nodes": [{"name": "确认", "type": "assignee", "assignee_key": "owner_id"}], "cc": []},
            ensure_ascii=False,
        ),
        timeout_hours=48,
        status=RULE_STATUS_PUBLISHED,
        version=1,
    )
    db_session.add(rule)
    db_session.commit()

    with patch("app.services.feishu_notify.send_text_to_open_id", return_value=True) as send:
        approval_flow.start_instance(
            db_session,
            biz_type="schedule",
            biz_id=99,
            initiator=initiator,
            title="排期确认通知测试",
            assignees={"owner_id": assignee.id},
        )
    assert send.call_count >= 1
