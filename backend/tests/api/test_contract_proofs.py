"""合同证明支持多文件。"""
import json

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.customer import Customer
from app.models.role import Role
from app.models.user import User
from app.services.contract import CONTRACT_PROOF_MAX, _normalize_proof_items


def _headers(client: TestClient, db: Session) -> dict[str, str]:
    role = Role(name="证明测试管理员", code="admin", data_scope="company")
    user = User(
        username="proof_admin",
        password_hash=hash_password("secret123"),
        real_name="证明管理员",
        is_active=True,
    )
    user.roles.append(role)
    db.add_all([role, user])
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "proof_admin", "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_normalize_proof_items_caps_and_dedupes() -> None:
    items = [{"filename": f"a{i}.jpg", "path": f"p/{i}.jpg"} for i in range(12)]
    items.append({"filename": "dup.jpg", "path": "p/0.jpg"})
    out = _normalize_proof_items(items)
    assert len(out) == CONTRACT_PROOF_MAX
    assert out[0]["path"] == "p/0.jpg"


def test_create_and_update_contract_with_multi_proofs(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = _headers(client, db_session)
    owner = db_session.query(User).filter(User.username == "proof_admin").one()
    customer = Customer(name="多证明客户", owner_id=owner.id, creator_id=owner.id)
    db_session.add(customer)
    db_session.commit()

    create = client.post(
        "/api/v1/contracts",
        headers=headers,
        json={
            "title": "多图合同",
            "customer_id": customer.id,
            "contract_type": "other",
            "amount": 100,
            "proofs": [
                {"filename": "a.jpg", "path": "contract_proof/a.jpg"},
                {"filename": "b.jpg", "path": "contract_proof/b.jpg"},
            ],
        },
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert len(body["proofs"]) == 2
    assert body["proof_filename"] == "a.jpg"
    assert body["proof_path"] == "contract_proof/a.jpg"
    assert body["proof_url"] == "/uploads/contract_proof/a.jpg"
    cid = body["id"]

    patch = client.patch(
        f"/api/v1/contracts/{cid}",
        headers=headers,
        json={
            "proofs": [
                {"filename": "a.jpg", "path": "contract_proof/a.jpg"},
                {"filename": "b.jpg", "path": "contract_proof/b.jpg"},
                {"filename": "c.pdf", "path": "contract_proof/c.pdf"},
            ]
        },
    )
    assert patch.status_code == 200, patch.text
    patched = patch.json()
    assert len(patched["proofs"]) == 3
    assert patched["proofs"][2]["filename"] == "c.pdf"

    detail = client.get(f"/api/v1/contracts/{cid}", headers=headers)
    assert detail.status_code == 200
    raw = db_session.execute(
        text("SELECT proof_files_json FROM contracts WHERE id = :id"),
        {"id": cid},
    ).scalar_one()
    stored = json.loads(raw)
    assert len(stored) == 3
