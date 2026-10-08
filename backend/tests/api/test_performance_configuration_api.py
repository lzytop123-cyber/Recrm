"""配置元数据接口：计分类型 schema、数据源、部门范围。"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.department import Department
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def _user(db: Session, username: str, *codes: str, data_scope: str = "company", dept_id=None) -> User:
    role = Role(name=f"{username}-role", code=f"{username}_role", data_scope=data_scope)
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
        job_title="市场业务" if dept_id else None,
    )
    user.roles.append(role)
    db.add(user)
    db.flush()
    return user


def _headers(client: TestClient, username: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "secret123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_configuration_scoring_types_complete(client: TestClient, db_session: Session) -> None:
    hr = _user(db_session, "cfg_hr", "kpi:template:manage")
    db_session.commit()
    h = _headers(client, "cfg_hr")
    resp = client.get("/api/v1/performance/configuration", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"]
    codes = [x["code"] for x in body["scoring_types"]]
    assert codes == ["quantity", "ratio", "tier", "subjective", "bonus", "veto"]
    ratio = next(x for x in body["scoring_types"] if x["code"] == "ratio")
    keys = {f["key"] for f in ratio["field_schema"]}
    assert "zero_denominator_policy" in keys
    for st in body["scoring_types"]:
        for field in st["field_schema"]:
            if field.get("input_type") == "select":
                assert field.get("options"), f"{st['code']}.{field['key']} missing options"
    assert {m["code"] for m in body["handling_modes"]} == {
        "system_auto",
        "system_supplement",
        "employee_submit",
        "manager_score",
    }
    assert isinstance(body["data_sources"], list)
    assert all("code" in d and "available_fields" in d for d in body["data_sources"])


def test_configuration_dept_scope_for_department_manager(
    client: TestClient, db_session: Session
) -> None:
    market = Department(name="市场部", code="CFG_MKT")
    other = Department(name="讲师部", code="CFG_LEC")
    db_session.add_all([market, other])
    db_session.flush()
    staff = User(
        username="cfg_staff",
        password_hash=hash_password("x"),
        real_name="员工",
        is_active=True,
        department_id=market.id,
        job_title="市场业务",
    )
    db_session.add(staff)
    mgr = _user(
        db_session,
        "cfg_mgr",
        "kpi:template:manage",
        data_scope="department",
        dept_id=market.id,
    )
    db_session.commit()
    h = _headers(client, "cfg_mgr")
    resp = client.get("/api/v1/performance/configuration", headers=h)
    assert resp.status_code == 200, resp.text
    names = {d["name"] for d in resp.json()["departments"]}
    assert "市场部" in names
    assert "讲师部" not in names
    market_out = next(d for d in resp.json()["departments"] if d["name"] == "市场部")
    assert any(j["name"] == "市场业务" for j in market_out["job_titles"])


def test_indicator_definitions_api_crud(client: TestClient, db_session: Session) -> None:
    hr = _user(db_session, "ind_hr", "kpi:template:manage")
    db_session.commit()
    h = _headers(client, "ind_hr")
    created = client.post(
        "/api/v1/performance/indicator-definitions",
        headers=h,
        json={
            "metric_key": "market.new_customers",
            "name": "客户拓展",
            "scoring_type": "quantity",
            "unit": "个",
            "data_source_code": "crm_lead",
            "handling_mode": "system_supplement",
            "status": "active",
            "rule_config": {
                "target_value": "10",
                "unit": "个",
                "calculation": "proportional",
                "floor_points": "0",
                "cap_at_max": True,
            },
        },
    )
    assert created.status_code == 200, created.text
    ind_id = created.json()["id"]
    subjective = client.post(
        "/api/v1/performance/indicator-definitions",
        headers=h,
        json={
            "metric_key": "market.subjective_demo",
            "name": "主观演示",
            "scoring_type": "subjective",
            "unit": "分",
            "data_source_code": "manager_review",
            "handling_mode": "system_auto",
            "rule_config": {"reviewer_type": "manager", "dimensions": "准确性", "hint": "说明"},
        },
    )
    assert subjective.status_code == 200, subjective.text
    listed = client.get(
        "/api/v1/performance/indicator-definitions?status=active",
        headers=h,
    )
    assert listed.status_code == 200
    assert any(x["id"] == ind_id for x in listed.json())
    disabled = client.post(
        f"/api/v1/performance/indicator-definitions/{ind_id}/disable",
        headers=h,
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    sub_id = subjective.json()["id"]
    deleted = client.delete(f"/api/v1/performance/indicator-definitions/{sub_id}", headers=h)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"ok": True}
    gone = client.delete(f"/api/v1/performance/indicator-definitions/{sub_id}", headers=h)
    assert gone.status_code == 404
