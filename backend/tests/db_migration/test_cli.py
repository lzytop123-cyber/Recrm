import subprocess
import sys


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app.db_migration.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_lists_all_commands():
    result = run_cli("--help")

    assert result.returncode == 0
    assert "inspect" in result.stdout
    assert "migrate" in result.stdout
    assert "validate" in result.stdout


def test_migrate_requires_both_urls():
    result = run_cli("migrate")

    assert result.returncode == 2
    assert "--source-url" in result.stderr
    assert "--target-url" in result.stderr


def test_unsafe_url_combination_returns_one_without_printing_password():
    result = run_cli(
        "migrate",
        "--source-url",
        "mysql://user:source-secret@localhost/source",
        "--target-url",
        "postgresql+psycopg://user:target-secret@localhost/target",
        "--report",
        "migration-report.json",
    )

    assert result.returncode == 1
    assert "SQLite" in result.stderr
    assert "source-secret" not in result.stderr
    assert "target-secret" not in result.stderr
