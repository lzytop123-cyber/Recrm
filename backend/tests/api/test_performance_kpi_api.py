"""绩效 API：模板 → 周期 → 生成 → 自评 → 明细时间线。"""
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.seed import seed_approval_rules


ITEMS = [
    {
        "order_no": 1,
        "name": "销售额",
        "weight": 50,
        "data_source": "system",
        "source_ref": "customer.deals",
        "target_value": "100000",
    },
    {"order_no": 2, "name": "协作", "weight": 50, "data_source": "manual"},
]


def _user(db: Session, username: str, *codes: str, manager_id: int | None = None) -> User:
    role = Role(name=f"{username}-role", code=f"{username}_role", data_scope="company")
    for code in codes:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if not perm:
            perm = Permission(name=code, code=code, module="okr")
            db.add(perm)
            db.flush()
        role.permissions.append(perm)
    user = User(
        username=username,
        password_hash=hash_password("secret123"),
        real_name=username,
        is_active=True,
        manager_id=manager_id,
    )
    user.roles.append(role)
    db.add(user)
    db.flush()
    return user


def _headers(client: TestClient, username: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "secret123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_performance_api_template_cycle_detail_flow(client: TestClient, db_session: Session) -> None:
    seed_approval_rules(db_session)
    skip = _user(db_session, "skip_api", "okr:view")
    mgr = _user(db_session, "mgr_api", "okr:view", manager_id=skip.id)
    staff = _user(db_session, "staff_api", "okr:view", manager_id=mgr.id)
    hr = _user(
        db_session,
        "hr_api",
        "okr:view",
        "kpi:template:manage",
        "kpi:cycle:manage",
    )
    # HR 节点需要 hr 角色码
    hr_role = Role(name="人力资源", code="hr", data_scope="company")
    hr.roles.append(hr_role)
    db_session.add(hr_role)
    db_session.commit()

    hr_h = _headers(client, "hr_api")
    staff_h = _headers(client, "staff_api")

    create = client.post(
        "/api/v1/performance/templates",
        headers=hr_h,
        json={
            "name": "销售模板",
            "code": "TPL-API-1",
            "cycle_type": "monthly",
            "items": ITEMS,
        },
    )
    assert create.status_code == 200, create.text
    tpl_id = create.json()["id"]

    tpl_get = client.get(f"/api/v1/performance/templates/{tpl_id}", headers=hr_h)
    assert tpl_get.status_code == 200
    assert tpl_get.json()["code"] == "TPL-API-1"
    assert len(tpl_get.json()["items"]) == 2

    cycle = client.post(
        "/api/v1/performance/cycles",
        headers=hr_h,
        json={"name": "2026-Q3-API", "template_id": tpl_id, "cycle_type": "monthly"},
    )
    assert cycle.status_code == 200, cycle.text
    cycle_id = cycle.json()["id"]

    cycles = client.get("/api/v1/performance/cycles", headers=hr_h)
    assert cycles.status_code == 200
    assert any(c["id"] == cycle_id for c in cycles.json())

    gen = client.post(
        f"/api/v1/performance/cycles/{cycle_id}/generate",
        headers=hr_h,
        json={"scope": {"user_ids": [staff.id]}},
    )
    assert gen.status_code == 200, gen.text
    assert len(gen.json()) == 1
    assessment_id = gen.json()[0]["id"]
    items = gen.json()[0]["items"]
    assert len(items) == 2

    detail = client.get(
        f"/api/v1/performance/assessments/{assessment_id}/detail",
        headers=staff_h,
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["template_id"] == tpl_id
    assert len(body["items"]) == 2
    assert len(body["timeline"]) >= 1

    self_rate = client.post(
        f"/api/v1/performance/assessments/{assessment_id}/self-rate",
        headers=staff_h,
        json={
            "self_score": 80,
            "items": [
                {
                    "item_id": items[1]["id"],
                    "self_score": str(Decimal("80")),
                    "self_comment": "自评",
                }
            ],
        },
    )
    assert self_rate.status_code == 200, self_rate.text
    assert self_rate.json()["status"] == "pending_manager"

    mine = client.get("/api/v1/performance/assessments/mine", headers=staff_h)
    assert mine.status_code == 200
    assert any(a["id"] == assessment_id for a in mine.json()["assessments"])

    team = client.get("/api/v1/performance/assessments/team?scope=direct", headers=_headers(client, "mgr_api"))
    assert team.status_code == 200
    assert any(a["id"] == assessment_id for a in team.json())

    cdetail = client.get(f"/api/v1/performance/cycles/{cycle_id}/detail", headers=hr_h)
    assert cdetail.status_code == 200
    assert cdetail.json()["cycle"]["id"] == cycle_id
    assert len(cdetail.json()["assessments"]) == 1
