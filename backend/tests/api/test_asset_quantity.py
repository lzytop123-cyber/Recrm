"""同型号多件入库：每件独立编号，便于台账按型号合并。"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.asset import FixedAsset
from app.models.role import Role
from app.models.user import User


def _admin_headers(client: TestClient, db: Session) -> dict[str, str]:
    role = Role(name="测试管理员", code="admin", data_scope="company")
    user = User(
        username="asset_qty_admin",
        password_hash=hash_password("secret123"),
        real_name="资产管理员",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "asset_qty_admin", "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_create_asset_quantity_creates_distinct_units(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    resp = client.post(
        "/api/v1/assets",
        headers=headers,
        json={
            "name": "RØDE Wireless PRO",
            "category": "收音",
            "model": "Wireless PRO",
            "location": "器材柜 C1",
            "original_value": 3195,
            "quantity": 3,
        },
    )
    assert resp.status_code == 200, resp.text
    rows = (
        db_session.query(FixedAsset)
        .filter(FixedAsset.name == "RØDE Wireless PRO")
        .order_by(FixedAsset.id.asc())
        .all()
    )
    assert len(rows) == 3
    nos = {r.asset_no for r in rows}
    qrs = {r.qr_code for r in rows}
    assert len(nos) == 3
    assert len(qrs) == 3
    assert all(r.category == "收音" for r in rows)
    assert all(r.model == "Wireless PRO" for r in rows)
    assert all(r.status == "available" for r in rows)


def test_create_asset_default_quantity_is_one(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    resp = client.post(
        "/api/v1/assets",
        headers=headers,
        json={"name": "DJI RS 4 Pro", "category": "稳定器", "model": "RS 4 Pro"},
    )
    assert resp.status_code == 200, resp.text
    assert db_session.query(FixedAsset).filter(FixedAsset.name == "DJI RS 4 Pro").count() == 1


def test_create_asset_rejects_invalid_quantity(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    too_many = client.post(
        "/api/v1/assets",
        headers=headers,
        json={"name": "备用电池", "category": "其他", "quantity": 100},
    )
    assert too_many.status_code == 422
    zero = client.post(
        "/api/v1/assets",
        headers=headers,
        json={"name": "备用电池", "category": "其他", "quantity": 0},
    )
    assert zero.status_code == 422


def test_update_one_unit_does_not_touch_siblings(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    created = client.post(
        "/api/v1/assets",
        headers=headers,
        json={"name": "索尼 A7M4", "category": "相机", "model": "A7M4", "quantity": 2},
    )
    assert created.status_code == 200, created.text
    rows = (
        db_session.query(FixedAsset)
        .filter(FixedAsset.name == "索尼 A7M4")
        .order_by(FixedAsset.id.asc())
        .all()
    )
    assert len(rows) == 2
    first, second = rows
    resp = client.patch(
        f"/api/v1/assets/{first.id}",
        headers=headers,
        json={"name": "索尼 A7M4 主机", "location": "A柜", "apply_to_same_model": False},
    )
    assert resp.status_code == 200, resp.text
    db_session.expire_all()
    first = db_session.get(FixedAsset, first.id)
    second = db_session.get(FixedAsset, second.id)
    assert first is not None and second is not None
    assert first.name == "索尼 A7M4 主机"
    assert first.location == "A柜"
    assert second.name == "索尼 A7M4"
    assert second.location is None


def test_update_same_model_syncs_siblings(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    created = client.post(
        "/api/v1/assets",
        headers=headers,
        json={
            "name": "南光 Forza",
            "category": "灯具",
            "model": "300B",
            "location": "灯光区",
            "original_value": 6290,
            "quantity": 3,
        },
    )
    assert created.status_code == 200, created.text
    rows = db_session.query(FixedAsset).filter(FixedAsset.model == "300B").all()
    assert len(rows) == 3
    target_id = rows[0].id
    resp = client.patch(
        f"/api/v1/assets/{target_id}",
        headers=headers,
        json={
            "name": "南光 Forza 300B II",
            "location": "B1",
            "original_value": 6500,
            "apply_to_same_model": True,
        },
    )
    assert resp.status_code == 200, resp.text
    db_session.expire_all()
    updated = db_session.query(FixedAsset).filter(FixedAsset.id.in_([r.id for r in rows])).all()
    assert len(updated) == 3
    assert all(x.name == "南光 Forza 300B II" for x in updated)
    assert all(x.location == "B1" for x in updated)
    assert all(float(x.original_value) == 6500 for x in updated)


def test_update_quantity_increases_and_decreases_units(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    created = client.post(
        "/api/v1/assets",
        headers=headers,
        json={"name": "索尼 A7M4", "category": "相机", "model": "A7M4", "quantity": 1},
    )
    assert created.status_code == 200, created.text
    asset_id = created.json()["id"]

    up = client.patch(
        f"/api/v1/assets/{asset_id}",
        headers=headers,
        json={"quantity": 3},
    )
    assert up.status_code == 200, up.text
    db_session.expire_all()
    assert db_session.query(FixedAsset).filter(FixedAsset.model == "A7M4").count() == 3

    down = client.patch(
        f"/api/v1/assets/{asset_id}",
        headers=headers,
        json={"quantity": 1},
    )
    assert down.status_code == 200, down.text
    db_session.expire_all()
    assert db_session.query(FixedAsset).filter(FixedAsset.model == "A7M4").count() == 1
