from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Integer, MetaData, Numeric, String, Table, create_engine

from app.db_migration.validation import (
    CheckResult,
    ValidationReport,
    redact_row,
    validate_aggregates,
    validate_row_counts,
)


def build_financial_metadata() -> MetaData:
    metadata = MetaData()
    Table(
        "contracts",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("amount", Numeric(12, 2), nullable=False),
    )
    Table(
        "payments",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("amount", Numeric(12, 2), nullable=False),
    )
    Table(
        "timesheets",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("hours", Numeric(5, 2), nullable=False),
    )
    return metadata


def test_report_fails_when_any_check_fails():
    report = ValidationReport(
        started_at=datetime.now(timezone.utc),
        checks=[
            CheckResult("one", True, 1, 1, "matches"),
            CheckResult("two", False, 2, 1, "mismatch"),
        ],
    )

    assert report.passed is False
    assert report.to_dict()["passed"] is False


def test_row_count_mismatch_is_reported():
    metadata = build_financial_metadata()
    source_engine = create_engine("sqlite:///:memory:")
    target_engine = create_engine("sqlite:///:memory:")
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)
    with source_engine.begin() as source:
        source.execute(metadata.tables["contracts"].insert(), {"id": 1, "amount": 10})
    with source_engine.connect() as source, target_engine.connect() as target:
        checks = validate_row_counts(source, target, list(metadata.sorted_tables))

    contract_check = next(check for check in checks if check.name == "count:contracts")
    assert contract_check.passed is False
    assert contract_check.source == 1
    assert contract_check.target == 0


def test_decimal_aggregates_compare_exactly():
    metadata = build_financial_metadata()
    source_engine = create_engine("sqlite:///:memory:")
    target_engine = create_engine("sqlite:///:memory:")
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)
    rows = {
        "contracts": {"id": 1, "amount": Decimal("10.10")},
        "payments": {"id": 1, "amount": Decimal("3.30")},
        "timesheets": {"id": 1, "hours": Decimal("7.50")},
    }
    for engine in (source_engine, target_engine):
        with engine.begin() as connection:
            for table_name, row in rows.items():
                connection.execute(metadata.tables[table_name].insert(), row)

    with source_engine.connect() as source, target_engine.connect() as target:
        checks = validate_aggregates(source, target, metadata)

    assert len(checks) == 3
    assert all(check.passed for check in checks)
    assert checks[0].source == checks[0].target


def test_redacts_sensitive_fields():
    redacted = redact_row(
        "users",
        {
            "id": 1,
            "username": "admin",
            "password_hash": "hash-value",
            "refresh_token": "token-value",
            "api_secret": "secret-value",
        },
    )

    assert redacted["username"] == "admin"
    assert redacted["password_hash"] == "<redacted>"
    assert redacted["refresh_token"] == "<redacted>"
    assert redacted["api_secret"] == "<redacted>"

