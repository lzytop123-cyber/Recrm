"""运行期完整流程 API：发布→匹配→批次→材料→评分→确认。"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.permission import Permission
from app.models.performance import (
    PerformanceTemplate,
    PerformanceTemplateItem,
    PerformanceTemplateScope,
    PerformanceCycle,
)
from app.models.role import Role
from app.models.user import User
from app.services import performance_personnel_matcher as matcher
from app.services.performance_template import publish_template


def _perm_user(db: Session, username: str, *codes: str, dept_id=None, manager_id=None, job_title=None) -> User:
    role = Role(name=f"{username}-role", code=f"{username}_role", data_scope="company")
    for code in codes:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if not perm:
            perm = Permission(name=code, code=code, module="kpi")
            db.add(perm)
            db.flush()
        role.permissions.append(perm)
    user = User(
        username=username,
        password_hash=hash_password("secret123"),
        real_name=username,
        is_active=True,
        department_id=dept_id,
        manager_id=manager_id,
        job_title=job_title,
        employment_status="正式",
        hire_date=date(2025, 1, 1),
    )
    user.roles.append(role)
    db.add(user)
    db.flush()
    return user


def _headers(client: TestClient, username: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "secret123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}



def _employee_fill_and_submit(client, headers, assessment_id, actual="3家"):
    tasks = client.get(f"/api/v1/performance/assessments/{assessment_id}/material-tasks", headers=headers)
    assert tasks.status_code == 200, tasks.text
    for task in tasks.json():
        if task["status"] in ("pending", "draft", "returned"):
            saved = client.patch(
                f"/api/v1/performance/material-tasks/{task['id']}/draft",
                headers=headers,
                json={"content": "演示补充"},
            )
            assert saved.status_code == 200, saved.text
    detail = client.get(f"/api/v1/performance/assessments/{assessment_id}/runtime-detail", headers=headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    submitted = client.post(
        f"/api/v1/performance/assessments/{assessment_id}/employee-submit",
        headers=headers,
        json={
            "revision": body["revision"],
            "actuals": [{"item_id": row["id"], "actual": actual} for row in body["items"]],
        },
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "manager_pending"
    assert submitted.json()["items"][0]["actual_value"] == actual
    return submitted.json()


def test_runtime_happy_path(client: TestClient, db_session: Session) -> None:
    dept = Department(name="市场部", code="RT_MKT")
    db_session.add(dept)
    db_session.flush()
    hr = _perm_user(db_session, "rt_hr", "kpi:template:manage", "kpi:assessment:manage", dept_id=dept.id)
    mgr = _perm_user(db_session, "rt_mgr", "okr:view", dept_id=dept.id, job_title="市场主管")
    emp = _perm_user(
        db_session,
        "rt_emp",
        "okr:view",
        "kpi:view",
        dept_id=dept.id,
        manager_id=mgr.id,
        job_title="市场业务",
    )
    matcher.seed_attendance_days(db_session, emp.id, date(2026, 10, 1), 30)
    tpl = PerformanceTemplate(
        name="市场合成月度",
        code="RT-MARKET-1",
        status="approved",
        family_code="MARKET_MONTHLY",
        version=1,
        engine_version="kpi-v2",
        scoring_mode="points_sum",
        assessment_kind="monthly",
        definition_json='{"items":[{"metric_key":"market.signed_clients","max_points":"100"}],"open_issues":[]}',
        blocking_issues_json="[]",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        created_by=hr.id,
    )
    cycle = PerformanceCycle(period_label="2026-10", status="assessing", cycle_type="monthly")
    db_session.add_all([tpl, cycle])
    db_session.flush()
    db_session.add(
        PerformanceTemplateItem(
            template_id=tpl.id,
            order_no=1,
            name="签约数",
            weight=Decimal("100"),
            data_source="system",
            metric_key="market.signed_clients",
            scoring_type="quantity",
            handling_mode="employee_submit",
            evidence_policy_json='{"required_fields":["content"]}',
        )
    )
    db_session.add(PerformanceTemplateScope(template_id=tpl.id, department_id=dept.id, job_title="市场业务"))
    db_session.commit()

    publish_template(db_session, tpl.id, hr)

    hr_h = _headers(client, "rt_hr")
    emp_h = _headers(client, "rt_emp")
    mgr_h = _headers(client, "rt_mgr")

    match = client.post(
        "/api/v1/performance/assessments/match-personnel",
        headers=hr_h,
        json={"cycle_id": cycle.id, "template_id": tpl.id},
    )
    assert match.status_code == 200, match.text
    assert match.json()["summary"]["matched"] >= 1

    base = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)
    batch = client.post(
        "/api/v1/performance/assessment-batches",
        headers={**hr_h, "Idempotency-Key": "rt-batch-1"},
        json={
            "cycle_id": cycle.id,
            "template_id": tpl.id,
            "people": [{"user_id": emp.id, "selected": True, "adjustment_reason": None}],
            "employee_due_at": base.isoformat(),
            "manager_due_at": (base + timedelta(days=3)).isoformat(),
            "hr_review_required": False,
            "hr_review_due_at": None,
            "confirm_due_at": (base + timedelta(days=8)).isoformat(),
        },
    )
    assert batch.status_code == 200, batch.text
    assessment_id = batch.json()["assessment_ids"][0]
    batch_id = batch.json()["id"]

    emp_board = client.get(
        f"/api/v1/performance/assessment-batches?cycle_id={cycle.id}",
        headers=emp_h,
    )
    assert emp_board.status_code == 200, emp_board.text
    assert emp_board.json()["totals"]["batch_count"] == 1
    emp_detail = client.get(f"/api/v1/performance/assessment-batches/{batch_id}", headers=emp_h)
    assert emp_detail.status_code == 200, emp_detail.text

    tasks = client.get(f"/api/v1/performance/assessments/{assessment_id}/material-tasks", headers=emp_h)
    assert tasks.status_code == 200, tasks.text
    assert len(tasks.json()) >= 1

    detail = client.get(f"/api/v1/performance/assessments/{assessment_id}/runtime-detail", headers=emp_h)
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "employee_pending"
    assert "employee_submit" in body["allowed_actions"]
    assert body["manager_name"] == "rt_mgr"
    assert body["full_points"] == "100.00"
    mgr_detail = client.get(f"/api/v1/performance/assessments/{assessment_id}/runtime-detail", headers=mgr_h)
    assert mgr_detail.status_code == 200
    assert "manager_submit" not in body["allowed_actions"]
    submitted = _employee_fill_and_submit(client, emp_h, assessment_id)
    mgr_detail = client.get(f"/api/v1/performance/assessments/{assessment_id}/runtime-detail", headers=mgr_h)
    assert mgr_detail.status_code == 200
    rev = submitted["revision"]
    assert "manager_submit" in mgr_detail.json()["allowed_actions"]
    arrangement = body["arrangement"]
    assert isinstance(arrangement, list) and len(arrangement) >= 6
    labels = [row["label"] for row in arrangement]
    assert labels == ["周期", "考核人员", "匹配方式", "考核模板", "评分人 / 复核", "截止日期"]
    assert any(row["label"] == "周期" and row["value"] for row in arrangement)
    assert any("市场业务" in row["value"] for row in arrangement if row["label"] == "考核人员")
    assert any("→" in row["value"] for row in arrangement if row["label"] == "截止日期")
    items = body.get("items") or []
    assert len(items) >= 1
    assert "display_actual" in items[0]
    assert "score_label" in items[0]
    due = next(row["value"] for row in arrangement if row["label"] == "截止日期")
    assert "各部门主管评分" in due
    assert "员工结果确认" in due

    # 取考核项 id
    from app.models.performance import PerformanceAssessmentItem

    item = (
        db_session.query(PerformanceAssessmentItem)
        .filter(PerformanceAssessmentItem.assessment_id == assessment_id)
        .first()
    )
    mgr_submit = client.post(
        f"/api/v1/performance/assessments/{assessment_id}/manager-submit",
        headers=mgr_h,
        json={"revision": rev, "scores": [{"item_id": item.id, "score": "85"}], "comment": "达标"},
    )
    assert mgr_submit.status_code == 200, mgr_submit.text
    assert mgr_submit.json()["status"] == "employee_confirm_pending"
    rev = mgr_submit.json()["revision"]
    after_score = client.get(
        f"/api/v1/performance/assessments/{assessment_id}/runtime-detail", headers=emp_h
    )
    assert after_score.status_code == 200
    assert after_score.json()["manager_comment"] == "达标"

    confirm = client.post(
        f"/api/v1/performance/assessments/{assessment_id}/result-confirm",
        headers=emp_h,
        json={"revision": rev},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "completed"


def test_runtime_hr_review_and_material_return(client: TestClient, db_session: Session) -> None:
    dept = Department(name="市场部", code="RT2_MKT")
    db_session.add(dept)
    db_session.flush()
    hr = _perm_user(db_session, "rt2_hr", "kpi:template:manage", "kpi:assessment:manage", dept_id=dept.id)
    mgr = _perm_user(db_session, "rt2_mgr", "okr:view", dept_id=dept.id, job_title="市场主管")
    emp = _perm_user(
        db_session, "rt2_emp", "okr:view", "kpi:view", dept_id=dept.id, manager_id=mgr.id, job_title="市场业务"
    )
    matcher.seed_attendance_days(db_session, emp.id, date(2026, 10, 1), 30)
    tpl = PerformanceTemplate(
        name="市场HR复核",
        code="RT-MARKET-HR",
        status="approved",
        family_code="MARKET_MONTHLY_HR",
        version=1,
        engine_version="kpi-v2",
        scoring_mode="points_sum",
        definition_json='{"items":[{"metric_key":"market.signed_clients","max_points":"100"}],"open_issues":[]}',
        blocking_issues_json="[]",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        created_by=hr.id,
    )
    cycle = PerformanceCycle(period_label="2026-10", status="assessing", cycle_type="monthly")
    db_session.add_all([tpl, cycle])
    db_session.flush()
    db_session.add(
        PerformanceTemplateItem(
            template_id=tpl.id,
            order_no=1,
            name="签约数",
            weight=Decimal("100"),
            data_source="manual",
            metric_key="market.signed_clients",
            scoring_type="quantity",
            handling_mode="employee_submit",
            evidence_policy_json='{"required_fields":["content"]}',
        )
    )
    db_session.add(PerformanceTemplateScope(template_id=tpl.id, department_id=dept.id, job_title="市场业务"))
    db_session.commit()
    publish_template(db_session, tpl.id, hr)

    hr_h = _headers(client, "rt2_hr")
    mgr_h = _headers(client, "rt2_mgr")
    base = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)
    batch = client.post(
        "/api/v1/performance/assessment-batches",
        headers={**hr_h, "Idempotency-Key": "rt-batch-hr"},
        json={
            "cycle_id": cycle.id,
            "template_id": tpl.id,
            "people": [{"user_id": emp.id, "selected": True}],
            "employee_due_at": base.isoformat(),
            "manager_due_at": (base + timedelta(days=2)).isoformat(),
            "hr_review_required": True,
            "hr_review_due_at": (base + timedelta(days=4)).isoformat(),
            "confirm_due_at": (base + timedelta(days=6)).isoformat(),
        },
    )
    assert batch.status_code == 200, batch.text
    aid = batch.json()["assessment_ids"][0]
    detail = client.get(f"/api/v1/performance/assessments/{aid}/runtime-detail", headers=mgr_h)
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "employee_pending"
    assert detail.json()["hr_review_required"] is True
    review_row = next(r for r in detail.json()["arrangement"] if r["label"] == "评分人 / 复核")
    assert "HR复核" in review_row["value"]
    submitted = _employee_fill_and_submit(client, _headers(client, "rt2_emp"), aid)
    rev = submitted["revision"]
    from app.models.performance import PerformanceAssessmentItem

    item = db_session.query(PerformanceAssessmentItem).filter_by(assessment_id=aid).one()
    ms = client.post(
        f"/api/v1/performance/assessments/{aid}/manager-submit",
        headers=mgr_h,
        json={"revision": rev, "scores": [{"item_id": item.id, "score": "80"}]},
    )
    assert ms.status_code == 200, ms.text
    assert ms.json()["status"] == "hr_review"
    assert ms.json()["hr_review_required"] is True
    rev = ms.json()["revision"]
    hr_ok = client.post(
        f"/api/v1/performance/assessments/{aid}/hr-review",
        headers=hr_h,
        json={"revision": rev, "approve": True, "note": "复核通过"},
    )
    assert hr_ok.status_code == 200, hr_ok.text
    assert hr_ok.json()["status"] == "employee_confirm_pending"
