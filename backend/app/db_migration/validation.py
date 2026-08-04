"""Data-validation primitives for SQLite-to-PostgreSQL migration."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.engine import Connection


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    source: object
    target: object
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "source": _json_value(self.source),
            "target": _json_value(self.target),
            "detail": self.detail,
        }


@dataclass
class ValidationReport:
    started_at: datetime
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "started_at": self.started_at.isoformat(),
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
        }


def _count(connection: Connection, table: Table) -> int:
    return int(connection.execute(select(func.count()).select_from(table)).scalar_one())


def validate_row_counts(
    source: Connection, target: Connection, tables: Sequence[Table]
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for table in tables:
        source_count = _count(source, table)
        target_count = _count(target, table)
        passed = source_count == target_count
        checks.append(
            CheckResult(
                name=f"count:{table.name}",
                passed=passed,
                source=source_count,
                target=target_count,
                detail="matches" if passed else "row count mismatch",
            )
        )
    return checks


def _decimal_sum(connection: Connection, table: Table, column_name: str) -> Decimal:
    value = connection.execute(select(func.sum(table.c[column_name]))).scalar_one()
    return Decimal(str(value)) if value is not None else Decimal("0")


def validate_aggregates(
    source: Connection, target: Connection, metadata: MetaData
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for table_name, column_name in (
        ("contracts", "amount"),
        ("payments", "amount"),
        ("timesheets", "hours"),
    ):
        table = metadata.tables.get(table_name)
        if table is None or column_name not in table.c:
            continue
        source_total = _decimal_sum(source, table, column_name)
        target_total = _decimal_sum(target, table, column_name)
        passed = source_total == target_total
        checks.append(
            CheckResult(
                name=f"sum:{table_name}.{column_name}",
                passed=passed,
                source=source_total,
                target=target_total,
                detail="matches" if passed else "aggregate mismatch",
            )
        )
    return checks


def redact_row(table_name: str, row: Mapping[str, object]) -> dict[str, object]:
    """Remove credential-like values from field-level sample output."""
    _ = table_name
    sensitive_markers = ("password", "token", "secret", "hash")
    return {
        key: "<redacted>"
        if any(marker in key.lower() for marker in sensitive_markers)
        else _json_value(value)
        for key, value in row.items()
    }


def run_all_validations(
    source: Connection,
    target: Connection,
    tables: Sequence[Table],
    metadata: MetaData,
) -> ValidationReport:
    """Run every required validation that is safe inside the copy transaction."""
    report = ValidationReport(started_at=datetime.now().astimezone())
    report.checks.extend(validate_row_counts(source, target, tables))
    report.checks.extend(validate_aggregates(source, target, metadata))
    return report
