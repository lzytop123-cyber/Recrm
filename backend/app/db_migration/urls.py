"""Database endpoint validation for the SQLite-to-PostgreSQL migration."""

from dataclasses import dataclass

from sqlalchemy.engine import URL, make_url


@dataclass(frozen=True)
class DatabaseEndpoints:
    source_url: str
    target_url: str


def _parse(url: str, label: str) -> URL:
    try:
        return make_url(url)
    except Exception as exc:
        raise ValueError(f"{label} database URL is invalid") from exc


def safe_url(url: str) -> str:
    """Render a database URL without exposing its password."""
    return _parse(url, "Database").render_as_string(hide_password=True)


def validate_endpoints(source_url: str, target_url: str) -> DatabaseEndpoints:
    """Validate the supported migration direction and distinct endpoints."""
    source = _parse(source_url, "Source")
    target = _parse(target_url, "Target")

    if source == target:
        raise ValueError("Source and target databases must be different")
    if not source.drivername.startswith("sqlite"):
        raise ValueError("Source database must be SQLite")
    if not target.drivername.startswith("postgresql"):
        raise ValueError("Target database must be PostgreSQL")

    return DatabaseEndpoints(source_url=source_url, target_url=target_url)

