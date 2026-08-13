"""线索批量导入：模板 / 预览 / 确认。"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.schemas.lead import LeadCreate
from app.services import lead as lead_service
from app.services.lead import (
    build_import_template_csv,
    build_import_template_xlsx,
    preview_lead_import,
)


def _user(db: Session, username: str = "lead_importer") -> User:
    role = Role(name=f"{username}-role", code=f"{username}_role", data_scope="personal")
    perm = db.query(Permission).filter(Permission.code == "lead:view").first()
    if not perm:
        perm = Permission(name="线索查看", code="lead:view", module="lead")
        db.add(perm)
        db.flush()
    role.permissions.append(perm)
    user = User(
        username=username,
        password_hash=hash_password("secret123"),
        real_name=username,
        is_active=True,
    )
    user.roles.append(role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth(client: TestClient, username: str = "lead_importer") -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_template_and_preview_ok(client: TestClient, db_session: Session) -> None:
    _user(db_session)
    headers = _auth(client)
    tpl = client.get("/api/v1/leads/import/template", headers=headers)
    assert tpl.status_code == 200
    ctype = tpl.headers.get("content-type") or ""
    assert "spreadsheetml" in ctype or ctype.startswith(
        "application/vnd.openxmlformats"
    )

    csv_body = (
        "客户主体,联系电话,联系人,统一社会信用代码,企业域名,需求方向,需求说明,备注\n"
        "批量导入甲公司,13900000001,甲,,,AI产品销售,需要方案,\n"
        "批量导入乙公司,13900000002,乙,,,ai_product,,\n"
    ).encode("utf-8-sig")
    preview = client.post(
        "/api/v1/leads/import/preview",
        headers=headers,
        files={"file": ("leads.csv", csv_body, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["total"] == 2
    assert body["ok_count"] == 2
    assert body["error_count"] == 0

    confirm = client.post(
        "/api/v1/leads/import/confirm",
        headers=headers,
        json={
            "rows": [
                {
                    "row_no": r["row_no"],
                    "company_name": r["company_name"],
                    "phone": r["phone"],
                    "name": r["name"],
                    "business_type": r["business_type"],
                    "force": False,
                }
                for r in body["rows"]
            ]
        },
    )
    assert confirm.status_code == 200, confirm.text
    result = confirm.json()
    assert result["success_count"] == 2
    assert result["failed_count"] == 0


def test_preview_xlsx_ok(db_session: Session) -> None:
    content = build_import_template_xlsx()
    out = preview_lead_import(db_session, content, filename="t.xlsx")
    assert out.total >= 1
    assert out.error_count == 0


def test_template_xlsx_has_business_type_dropdown() -> None:
    import io

    from openpyxl import load_workbook

    content = build_import_template_xlsx(["AI产品销售", "AI定制开发"])
    wb = load_workbook(io.BytesIO(content))
    ws = wb["线索导入"]
    dvs = list(ws.data_validations.dataValidation)
    assert dvs
    assert dvs[0].type == "list"
    assert "_选项" in (dvs[0].formula1 or "")
    assert wb["_选项"]["A1"].value == "AI产品销售"
    assert wb["_选项"].sheet_state == "hidden"


def test_preview_rejects_invalid_business_type(db_session: Session) -> None:
    csv_body = (
        "客户主体,联系电话,联系人,统一社会信用代码,企业域名,需求方向,需求说明,备注\n"
        "某公司,13900000003,王,,,随便写的方向,,\n"
    ).encode("utf-8-sig")
    out = preview_lead_import(db_session, csv_body, filename="bad.csv")
    assert out.total == 1
    assert out.error_count == 1
    assert out.rows[0].can_import is False
    assert "需求方向无效" in out.rows[0].message


def test_preview_flags_hard_duplicate(db_session: Session) -> None:
    user = _user(db_session, username="lead_importer_dup")
    lead_service.create_lead(
        db_session,
        user,
        LeadCreate(
            company_name="已存在公司",
            phone="13900000999",
            business_type="ai_product",
        ),
    )
    csv_body = (
        "客户主体,联系电话,联系人,统一社会信用代码,企业域名,需求方向,需求说明,备注\n"
        "新公司,13900000999,张三,,,AI产品销售,,\n"
    ).encode("utf-8-sig")
    out = preview_lead_import(db_session, csv_body, filename="dup.csv")
    assert out.total == 1
    assert out.hard_count == 1
    assert out.rows[0].force_required is True
