"""Employee drafts persist over HTTP without submitting materials or advancing workflow."""
from decimal import Decimal
import pytest
from app.core.security import hash_password
from app.models.user import User
from app.models.performance import (
    PerformanceAssessment, PerformanceAssessmentItem, PerformanceCycle,
    PerformanceMaterialTask, PerformanceActionLog,
)


def _draft_case(client, db):
    emp = User(username="draft_employee", password_hash=hash_password("secret123"), is_active=True)
    manager = User(username="draft_manager", password_hash=hash_password("secret123"), is_active=True)
    cycle = PerformanceCycle(period_label="2026-10-draft", status="assessing")
    db.add_all([emp, manager, cycle])
    db.flush()
    assessment = PerformanceAssessment(cycle_id=cycle.id, user_id=emp.id, manager_id=manager.id,
        status="employee_pending", revision=1, current_handler_type="employee", current_handler_id=emp.id)
    db.add(assessment)
    db.flush()
    items = [PerformanceAssessmentItem(assessment_id=assessment.id, order_no=i,
        name=f"metric-{i}", weight=Decimal("50"), data_source="manual") for i in (1, 2)]
    db.add_all(items)
    db.flush()
    task = PerformanceMaterialTask(assessment_id=assessment.id, assessment_item_id=items[0].id,
        source_record_type="manual", source_record_id="draft", title="evidence",
        status="draft", employee_content="ready evidence")
    db.add(task)
    db.commit()
    login = client.post("/api/v1/auth/login", json={"username": emp.username, "password": "secret123"})
    assert login.status_code == 200, login.text
    return assessment, items, task, {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.parametrize("filled_count", [1, 2])
def test_employee_draft_persists_without_advancing(client, db_session, filled_count):
    assessment, items, task, headers = _draft_case(client, db_session)
    actuals = [{"item_id": item.id, "actual": str(i + 3)} for i, item in enumerate(items[:filled_count])]
    saved = client.post(f"/api/v1/performance/assessments/{assessment.id}/employee-submit", headers=headers,
        json={"revision": 1, "draft": True, "actuals": actuals, "self_comment": "draft explanation"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "employee_pending"
    assert saved.json()["current_handler_type"] == "employee"
    assert saved.json()["revision"] == 2
    db_session.refresh(task)
    assert task.status == "draft"
    assert task.submitted_at is None
    detail = client.get(f"/api/v1/performance/assessments/{assessment.id}/runtime-detail", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["self_comment"] == "draft explanation"
    assert detail.json()["items"][0]["actual_value"] == "3"
    assert detail.json()["items"][1]["actual_value"] == ("4" if filled_count == 2 else None)
    log = db_session.query(PerformanceActionLog).filter_by(assessment_id=assessment.id).one()
    assert log.action == "employee_draft"
    assert log.from_status == log.to_status == "employee_pending"
    submitted = client.post(f"/api/v1/performance/assessments/{assessment.id}/employee-submit", headers=headers,
        json={"revision": 2, "actuals": [{"item_id": item.id, "actual": "5"} for item in items]})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "manager_pending"


def test_comment_only_draft_and_stale_revision(client, db_session):
    assessment, items, task, headers = _draft_case(client, db_session)
    url = f"/api/v1/performance/assessments/{assessment.id}/employee-submit"
    saved = client.post(url, headers=headers, json={"revision": 1, "draft": True, "self_comment": "note only"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "employee_pending"
    assert saved.json()["self_comment"] == "note only"
    rejected = client.post(url, headers=headers, json={"revision": 1, "draft": True, "self_comment": "stale"})
    assert rejected.status_code == 409, rejected.text
    detail = client.get(f"/api/v1/performance/assessments/{assessment.id}/runtime-detail", headers=headers)
    assert detail.json()["self_comment"] == "note only"
    assert detail.json()["items"][0]["actual_value"] is None


def test_draft_can_clear_actual_without_clearing_omitted_items(client, db_session):
    assessment, items, task, headers = _draft_case(client, db_session)
    items[0].actual_value = "old draft"
    items[1].actual_value = "keep draft"
    db_session.commit()
    url = f"/api/v1/performance/assessments/{assessment.id}/employee-submit"
    cleared = client.post(url, headers=headers, json={"revision": 1, "draft": True,
        "actuals": [{"item_id": items[0].id, "actual": ""}]})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["status"] == "employee_pending"
    detail = client.get(f"/api/v1/performance/assessments/{assessment.id}/runtime-detail", headers=headers).json()
    assert detail["items"][0]["actual_value"] is None
    assert detail["items"][1]["actual_value"] == "keep draft"
    denied = client.post(url, headers=headers, json={"revision": 2, "actuals": [
        {"item_id": items[0].id, "actual": ""}, {"item_id": items[1].id, "actual": "keep draft"}]})
    assert denied.status_code == 422, denied.text
    assert denied.json()["detail"]["code"] == "KPI_ACTUAL_REQUIRED"
