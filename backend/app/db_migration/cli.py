"""Operator CLI for SQLite-to-PostgreSQL data migration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url

import app.models  # noqa: F401 - register every ORM table
from app.database import Base
from app.db_migration.copy import copy_all, reset_postgres_sequences
from app.db_migration.schema import (
    deferred_foreign_key_columns,
    ordered_tables,
    require_empty_target,
    target_row_counts,
)
from app.db_migration.urls import safe_url, validate_endpoints
from app.db_migration.validation import ValidationReport, run_all_validations


class MigrationValidationError(RuntimeError):
    def __init__(self, report: ValidationReport):
        super().__init__("Migration validation failed")
        self.report = report


def _source_engine(source_url: str) -> Engine:
    engine = create_engine(source_url)

    @event.listens_for(engine, "connect")
    def enable_read_only(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA query_only=ON")
        finally:
            cursor.close()

    return engine


def _write_report(path: str, report: ValidationReport) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _add_endpoint_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--target-url", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate CRM data from SQLite to PostgreSQL")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect the SQLite source")
    inspect_parser.add_argument("--source-url", required=True)

    migrate_parser = subparsers.add_parser("migrate", help="Copy and validate all data")
    _add_endpoint_arguments(migrate_parser)
    migrate_parser.add_argument("--report", required=True)
    migrate_parser.add_argument("--batch-size", type=int, default=500)

    validate_parser = subparsers.add_parser("validate", help="Validate an existing copy")
    _add_endpoint_arguments(validate_parser)
    validate_parser.add_argument("--report", required=True)
    return parser


def _inspect(source_url: str) -> int:
    parsed = make_url(source_url)
    if not parsed.drivername.startswith("sqlite"):
        raise ValueError("Source database must be SQLite")
    tables = ordered_tables(Base.metadata)
    engine = _source_engine(source_url)
    try:
        with engine.connect() as source:
            counts = target_row_counts(source, tables)
    finally:
        engine.dispose()
    print(json.dumps({"source": safe_url(source_url), "counts": counts}, indent=2))
    return 0


def _run_migration(
    source_url: str,
    target_url: str,
    report_path: str,
    batch_size: int,
) -> int:
    validate_endpoints(source_url, target_url)
    tables = ordered_tables(Base.metadata)
    source_engine = _source_engine(source_url)
    target_engine = create_engine(target_url)
    report: ValidationReport | None = None
    try:
        with source_engine.connect() as source:
            with target_engine.begin() as target:
                require_empty_target(target_row_counts(target, tables))
                copy_all(
                    source,
                    target,
                    tables,
                    batch_size=batch_size,
                    deferred_columns=deferred_foreign_key_columns(Base.metadata),
                )
                reset_postgres_sequences(target, tables)
                report = run_all_validations(source, target, tables, Base.metadata)
                if not report.passed:
                    raise MigrationValidationError(report)
    except MigrationValidationError as exc:
        _write_report(report_path, exc.report)
        raise
    finally:
        source_engine.dispose()
        target_engine.dispose()

    assert report is not None
    _write_report(report_path, report)
    print(f"Migration passed; report written to {report_path}")
    return 0


def _run_validation(source_url: str, target_url: str, report_path: str) -> int:
    validate_endpoints(source_url, target_url)
    tables = ordered_tables(Base.metadata)
    source_engine = _source_engine(source_url)
    target_engine = create_engine(target_url)
    try:
        with source_engine.connect() as source, target_engine.connect() as target:
            report = run_all_validations(source, target, tables, Base.metadata)
    finally:
        source_engine.dispose()
        target_engine.dispose()
    _write_report(report_path, report)
    if not report.passed:
        raise MigrationValidationError(report)
    print(f"Validation passed; report written to {report_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            return _inspect(args.source_url)
        if args.command == "migrate":
            return _run_migration(
                args.source_url,
                args.target_url,
                args.report,
                args.batch_size,
            )
        return _run_validation(args.source_url, args.target_url, args.report)
    except Exception as exc:
        print(f"Migration error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
