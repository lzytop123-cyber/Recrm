import pytest

from app.db_migration.urls import safe_url, validate_endpoints


def test_accepts_sqlite_source_and_postgresql_target():
    endpoints = validate_endpoints(
        "sqlite:///./app.db",
        "postgresql+psycopg://crm:secret@127.0.0.1/crm_okr",
    )

    assert endpoints.source_url == "sqlite:///./app.db"
    assert endpoints.target_url.endswith("/crm_okr")


@pytest.mark.parametrize("source", ["postgresql://x/y", "mysql://x/y"])
def test_rejects_non_sqlite_source(source):
    with pytest.raises(ValueError, match="SQLite"):
        validate_endpoints(source, "postgresql+psycopg://crm:secret@localhost/crm")


@pytest.mark.parametrize("target", ["sqlite:///./target.db", "mysql://x/y"])
def test_rejects_non_postgresql_target(target):
    with pytest.raises(ValueError, match="PostgreSQL"):
        validate_endpoints("sqlite:///./app.db", target)


def test_rejects_same_source_and_target():
    with pytest.raises(ValueError, match="different"):
        validate_endpoints("sqlite:///./app.db", "sqlite:///./app.db")


def test_redacts_password():
    rendered = safe_url("postgresql+psycopg://crm:secret@localhost/crm")

    assert "secret" not in rendered
    assert "***" in rendered

