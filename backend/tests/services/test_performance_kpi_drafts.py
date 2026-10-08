"""模板草稿加载与导入去重。"""
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.data.performance_templates import load_drafts
from app.data.performance_templates.catalog import FAMILIES
from app.models.performance import PerformanceMetricFact, PerformanceTemplate
from app.models.user import User
from app.services.performance_kpi import confirm_import, preview_import


def test_thirteen_drafts_reload_does_not_duplicate(db_session: Session) -> None:
    assert len(FAMILIES) == 13
    assert len({item["family_code"] for item in FAMILIES}) == 13
    load_drafts(db_session)
    load_drafts(db_session)
    assert db_session.query(PerformanceTemplate).filter(PerformanceTemplate.engine_version == "kpi-v2").count() == 13
    ops = db_session.query(PerformanceTemplate).filter(PerformanceTemplate.family_code == "AI_OPS_MONTHLY").one()
    assert ops.status == "draft"
    assert str(ops.nominal_total) in {"110", "110.00"}
    for code in (
        "AI_OPS_MONTHLY",
        "CONTENT_MONTHLY",
        "BRAND_MONTHLY",
        "LIVE_HOST_MONTHLY",
        "LIVE_ADS_MONTHLY",
        "LECTURER_MONTHLY",
    ):
        row = db_session.query(PerformanceTemplate).filter(PerformanceTemplate.family_code == code).one()
        assert (row.blocking_issues_json or "[]") == "[]"


def test_draft_items_link_indicator_definition_id(db_session: Session) -> None:
    from app.models.performance import PerformanceIndicatorDefinition, PerformanceTemplateItem

    load_drafts(db_session)
    lec = db_session.query(PerformanceTemplate).filter(PerformanceTemplate.family_code == "LECTURER_MONTHLY").one()
    items = (
        db_session.query(PerformanceTemplateItem)
        .filter(PerformanceTemplateItem.template_id == lec.id)
        .all()
    )
    assert items
    assert all(it.metric_key for it in items)
    assert all(it.indicator_definition_id is not None for it in items)
    for it in items:
        ind = db_session.get(PerformanceIndicatorDefinition, it.indicator_definition_id)
        assert ind is not None
        assert ind.metric_key == it.metric_key
        assert it.source_ref == ind.data_source_code
        if (ind.handling_mode or "").startswith("system"):
            assert it.data_source == "system"


def test_content_items_aligned_with_indicator_source(db_session: Session) -> None:
    from app.models.performance import PerformanceTemplateItem

    load_drafts(db_session)
    content = (
        db_session.query(PerformanceTemplate)
        .filter(PerformanceTemplate.family_code == "CONTENT_MONTHLY")
        .one()
    )
    item = (
        db_session.query(PerformanceTemplateItem)
        .filter(
            PerformanceTemplateItem.template_id == content.id,
            PerformanceTemplateItem.metric_key == "content.output",
        )
        .one()
    )
    assert item.data_source == "system"
    assert item.source_ref == "ledger.manual"


def test_import_duplicate_source_is_not_double_counted(db_session: Session) -> None:
    user = User(username="kpi_imp", password_hash=hash_password("secret123"), real_name="合成甲", is_active=True)
    db_session.add(user)
    db_session.commit()
    csv_text = "employee,metric_key,value,source_record_id,project_ref\n合成甲,market.signed_clients,4,SYN-1,P1\n"
    first = preview_import(db_session, user, csv_text, users_by_name={"合成甲": user.id})
    assert first["can_confirm"] is True
    assert confirm_import(db_session, user, first["id"])["written"] == 1
    assert confirm_import(db_session, user, first["id"])["idempotent"] is True
    second = preview_import(db_session, user, csv_text.replace("SYN-1", "SYN-1"), users_by_name={"合成甲": user.id})
    assert second["rows"][0]["duplicate"] is True
    confirm_import(db_session, user, second["id"])
    assert db_session.query(PerformanceMetricFact).count() == 1
