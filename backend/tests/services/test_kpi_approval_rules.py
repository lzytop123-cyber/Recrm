"""AP-KPI-01/02/03 规则 seed 后能被审批引擎拆成正确节点。"""
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.seed import seed_approval_rules
from app.services.approval_flow import start_instance


def test_kpi_review_instance_has_four_seq_tasks(db_session: Session) -> None:
    seed_approval_rules(db_session)
    db_session.commit()

    staff = User(username="kpi_staff", password_hash=hash_password("x"), real_name="员工", is_active=True)
    manager = User(username="kpi_mgr", password_hash=hash_password("x"), real_name="上级", is_active=True)
    skip_mgr = User(username="kpi_skip", password_hash=hash_password("x"), real_name="隔级", is_active=True)
    db_session.add_all([staff, manager, skip_mgr])
    db_session.flush()

    inst = start_instance(
        db_session,
        biz_type="kpi_review",
        biz_id=1,
        initiator=staff,
        title="KPI 考核",
        assignees={
            "user_id": staff.id,
            "manager_id": manager.id,
            "skip_manager_id": skip_mgr.id,
        },
        commit=True,
    )

    assert inst.rule_code == "AP-KPI-01"
    seqs = sorted({t.seq for t in inst.tasks})
    assert seqs == [1, 2, 3, 4]
    by_seq = {t.seq: t for t in inst.tasks}
    assert by_seq[1].name == "员工自评" and by_seq[1].assignee_id == staff.id
    assert by_seq[2].name == "上级评分" and by_seq[2].assignee_id == manager.id
    assert by_seq[3].name == "隔级复核" and by_seq[3].assignee_id == skip_mgr.id
    assert by_seq[4].name == "HR 归档"
    assert by_seq[4].node_type == "approve"


def test_kpi_appeal_instance_has_two_seq_tasks(db_session: Session) -> None:
    seed_approval_rules(db_session)
    db_session.commit()

    staff = User(username="kpi_staff2", password_hash=hash_password("x"), real_name="员工", is_active=True)
    skip_mgr = User(username="kpi_skip2", password_hash=hash_password("x"), real_name="隔级", is_active=True)
    db_session.add_all([staff, skip_mgr])
    db_session.flush()

    inst = start_instance(
        db_session,
        biz_type="kpi_appeal",
        biz_id=1,
        initiator=staff,
        title="KPI 申诉",
        assignees={"skip_manager_id": skip_mgr.id},
        commit=True,
    )
    assert inst.rule_code == "AP-KPI-03"
    assert sorted({t.seq for t in inst.tasks}) == [1, 2]


def test_seed_publishes_three_kpi_rules(db_session: Session) -> None:
    seed_approval_rules(db_session)
    db_session.commit()
    from app.models.approval_rule import ApprovalRule, RULE_STATUS_PUBLISHED

    codes = {
        r.code
        for r in db_session.query(ApprovalRule)
        .filter(ApprovalRule.status == RULE_STATUS_PUBLISHED)
        .all()
    }
    assert {"AP-KPI-01", "AP-KPI-02", "AP-KPI-03"} <= codes
