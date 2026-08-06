"""P0 资产平台与通知冒烟。"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.platform import Notification
from app.models.role import Role
from app.models.user import User
from app.services import asset as asset_service


def _admin_headers(client: TestClient, db: Session) -> dict[str, str]:
    role = Role(name="测试管理员", code="admin", data_scope="company")
    user = User(
        username="asset_platform_admin",
        password_hash=hash_password("secret123"),
        real_name="资产管理员",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "asset_platform_admin", "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_inventory_create_and_notification_list(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _admin_headers(client, db_session)
    user = db_session.query(User).filter(User.username == "asset_platform_admin").one()

    # seed assets so inventory target_count > 0
    asset_service.ensure_seed_data(db_session)

    inv_resp = client.post(
        "/api/v1/assets/inventories",
        headers=headers,
        json={"period_label": "2099-01", "title": "冒烟盘点"},
    )
    assert inv_resp.status_code == 200, inv_resp.text
    body = inv_resp.json()
    assert body["period_label"] == "2099-01"
    assert body["title"] == "冒烟盘点"
    assert body["status"] == "in_progress"
    inventory_id = body["id"]

    detail = client.get(f"/api/v1/assets/inventories/{inventory_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == inventory_id

    db_session.add(
        Notification(
            user_id=user.id,
            title="盘点已创建",
            body="冒烟通知",
            category="asset",
            is_read=False,
        )
    )
    db_session.commit()

    notes = client.get("/api/v1/notifications", headers=headers)
    assert notes.status_code == 200
    items = notes.json()
    assert isinstance(items, list)
    assert any(x["title"] == "盘点已创建" for x in items)
