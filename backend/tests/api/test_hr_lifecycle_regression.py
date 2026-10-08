"""员工交接状态与接收人校验回归。"""
from datetime import date
from app.models.lead import Lead
from app.models.user import User
from app.models.hr import HrHandover, HrHandoverItem, HrResignation
from app.services import hr
from app.schemas.hr import HandoverAssignIn
from fastapi import HTTPException
import pytest


@pytest.mark.parametrize("recipient_kind", ["self", "inactive", "resigned"])
def test_handover_rejects_invalid_recipient(db_session, recipient_kind):
    emp = User(username="departing", password_hash="unused", is_active=True)
    recv = User(username="recipient", password_hash="unused", is_active=recipient_kind != "inactive",
                employment_status="离职" if recipient_kind == "resigned" else "正式")
    db_session.add_all([emp, recv])
    db_session.flush()
    lead = Lead(name="待交接", owner_id=emp.id, status="following")
    resign = HrResignation(employee_id=emp.id, created_by=emp.id, last_working_day=date.today(), reason="离职", status="handing_over")
    db_session.add_all([lead, resign])
    db_session.flush()
    ho = HrHandover(resignation_id=resign.id, employee_id=emp.id, status="open")
    db_session.add(ho)
    db_session.flush()
    item = HrHandoverItem(handover_id=ho.id, kind="lead", ref_id=lead.id, title="待交接", status="pending")
    db_session.add(item)
    db_session.commit()
    with pytest.raises(HTTPException) as error:
        hr.assign_handover_item(db_session, emp, ho.id, item.id,
                               HandoverAssignIn(assignee_id=emp.id if recipient_kind == "self" else recv.id))
    assert error.value.status_code == 400
    assert item.assignee_id is None


def test_completed_handover_cannot_be_reassigned(db_session):
    emp = User(username="departed", password_hash="unused", is_active=True)
    recv = User(username="recipient_done", password_hash="unused", is_active=True)
    db_session.add_all([emp, recv])
    db_session.flush()
    resign = HrResignation(employee_id=emp.id, created_by=emp.id, last_working_day=date.today(), reason="离职", status="completed")
    db_session.add(resign)
    db_session.flush()
    ho = HrHandover(resignation_id=resign.id, employee_id=emp.id, status="completed")
    db_session.add(ho)
    db_session.flush()
    item = HrHandoverItem(handover_id=ho.id, kind="lead", ref_id=1, title="已交接", status="confirmed")
    db_session.add(item)
    db_session.commit()
    with pytest.raises(HTTPException) as error:
        hr.assign_handover_item(db_session, emp, ho.id, item.id, HandoverAssignIn(assignee_id=recv.id))
    assert error.value.status_code == 400
    assert item.status == "confirmed"


def test_returned_assets_do_not_block_handover(db_session):
    emp = User(username="asset_returned", password_hash="unused", is_active=True)
    db_session.add(emp)
    db_session.flush()
    resign = HrResignation(employee_id=emp.id, created_by=emp.id, last_working_day=date.today(), reason="离职", status="handing_over")
    db_session.add(resign)
    db_session.flush()
    ho = HrHandover(resignation_id=resign.id, employee_id=emp.id, status="open")
    db_session.add(ho)
    db_session.flush()
    # 资产已在资产模块真实归还，只有历史快照，不再由该员工持有。
    db_session.add(HrHandoverItem(handover_id=ho.id, kind="asset", ref_id=1, title="已归还资产", status="pending"))
    db_session.commit()
    assert hr.get_handover(db_session, emp, ho.id).can_complete is True
