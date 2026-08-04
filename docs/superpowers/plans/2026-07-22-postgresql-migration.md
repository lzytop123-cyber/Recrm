# PostgreSQL Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely copy the complete `backend/app.db` SQLite dataset into an empty PostgreSQL database, validate it, switch the backend configuration, and retain a tested rollback path.

**Architecture:** A backend migration package exposes a small CLI interface over four responsibilities: URL safety checks, dependency-ordered row copying, sequence repair, and validation/reporting. Alembic owns target schema creation; the migration transaction owns imported data. The source database is opened read-only and is never modified.

**Tech Stack:** Python 3.12, SQLAlchemy 2, Alembic, psycopg 3, pytest, SQLite, PostgreSQL.

## Global Constraints

- PostgreSQL is the production database; SQLite remains a local/test adapter.
- Preserve every existing row, primary key, relationship, business identifier, timestamp, and decimal value.
- Use a maintenance window and stop all application writes before the final migration.
- Never print or persist a complete PostgreSQL URL containing credentials.
- Never delete or overwrite `backend/app.db`.
- Do not perform Git staging, commits, branch changes, or pushes.
- Do not cut over when any required validation fails.

## File Map

- Create `backend/app/db_migration/__init__.py`: public migration-package exports.
- Create `backend/app/db_migration/urls.py`: URL validation and credential-safe rendering.
- Create `backend/app/db_migration/schema.py`: table ordering and target-state checks.
- Create `backend/app/db_migration/copy.py`: transactional batch copy and PostgreSQL sequence repair.
- Create `backend/app/db_migration/validation.py`: integrity checks and report structures.
- Create `backend/app/db_migration/cli.py`: `migrate`, `validate`, and `inspect` command entry point.
- Create `backend/tests/conftest.py`: isolated database fixtures.
- Create `backend/tests/db_migration/test_urls.py`: URL-safety tests.
- Create `backend/tests/db_migration/test_schema.py`: table-order and empty-target tests.
- Create `backend/tests/db_migration/test_validation.py`: count, aggregate, and redaction tests.
- Create `backend/tests/db_migration/test_sqlite_copy.py`: source-safety and copy-planning tests that run without PostgreSQL.
- Create `backend/tests/db_migration/test_postgres_integration.py`: opt-in real PostgreSQL migration tests.
- Modify `backend/requirements.txt`: add psycopg 3 and pytest.
- Modify `backend/.env.example`: document PostgreSQL URL and runtime mode.
- Modify `README.md`: document preparation, migration, validation, cutover, and rollback commands.

---

### Task 1: Establish Migration Test Harness and URL Safety

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/db_migration/test_urls.py`
- Create: `backend/app/db_migration/__init__.py`
- Create: `backend/app/db_migration/urls.py`

**Interfaces:**
- Produces: `DatabaseEndpoints(source_url: str, target_url: str)`.
- Produces: `validate_endpoints(source_url: str, target_url: str) -> DatabaseEndpoints`.
- Produces: `safe_url(url: str) -> str`.

- [ ] **Step 1: Add test/runtime dependencies**

Add these lines to `backend/requirements.txt`:

```text
psycopg[binary]>=3.2,<4
pytest>=8.3,<9
```

- [ ] **Step 2: Install dependencies**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Expected: command exits `0`; `python -c "import psycopg, pytest"` exits `0`.

- [ ] **Step 3: Write failing URL-safety tests**

Test these exact behaviours in `test_urls.py`:

```python
import pytest

from app.db_migration.urls import safe_url, validate_endpoints


def test_accepts_sqlite_source_and_postgresql_target():
    endpoints = validate_endpoints(
        "sqlite:///./app.db",
        "postgresql+psycopg://crm:secret@127.0.0.1/crm_okr",
    )
    assert endpoints.source_url == "sqlite:///./app.db"


@pytest.mark.parametrize("source", ["postgresql://x/y", "mysql://x/y"])
def test_rejects_non_sqlite_source(source):
    with pytest.raises(ValueError, match="SQLite"):
        validate_endpoints(source, "postgresql+psycopg://crm:secret@localhost/crm")


def test_redacts_password():
    rendered = safe_url("postgresql+psycopg://crm:secret@localhost/crm")
    assert "secret" not in rendered
    assert "***" in rendered
```

- [ ] **Step 4: Verify tests fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db_migration\test_urls.py -v
```

Expected: FAIL because `app.db_migration.urls` does not exist.

- [ ] **Step 5: Implement URL safety**

Implement `urls.py` with SQLAlchemy `make_url`. Accept only source driver names beginning with `sqlite` and target driver names beginning with `postgresql`; reject equal normalized URLs. Return an immutable dataclass. Render URLs with `URL.render_as_string(hide_password=True)`.

- [ ] **Step 6: Verify URL tests pass**

Run the command from Step 4. Expected: all tests PASS.

### Task 2: Derive Safe Table Order and Inspect Target

**Files:**
- Create: `backend/tests/db_migration/test_schema.py`
- Create: `backend/app/db_migration/schema.py`

**Interfaces:**
- Consumes: `app.models` and `app.database.Base.metadata`.
- Produces: `ordered_tables(metadata: MetaData) -> list[Table]`.
- Produces: `target_row_counts(connection: Connection, tables: Sequence[Table]) -> dict[str, int]`.
- Produces: `require_empty_target(counts: Mapping[str, int]) -> None`.

- [ ] **Step 1: Write failing schema tests**

Cover association-table ordering after referenced tables, deterministic output, and refusal when any target table count is nonzero:

```python
def test_require_empty_target_rejects_existing_rows():
    with pytest.raises(ValueError, match="not empty"):
        require_empty_target({"users": 1, "roles": 0})
```

- [ ] **Step 2: Verify schema tests fail**

Run `python -m pytest tests\db_migration\test_schema.py -v`.
Expected: FAIL because `schema.py` does not exist.

- [ ] **Step 3: Implement dependency ordering**

Use `metadata.sorted_tables`; import `app.models` before reading metadata. Raise a descriptive error if SQLAlchemy cannot sort dependencies. Use `select(func.count()).select_from(table)` for target counts.

- [ ] **Step 4: Verify schema tests pass**

Run the command from Step 2. Expected: all tests PASS.

### Task 3: Build Validation Reports

**Files:**
- Create: `backend/tests/db_migration/test_validation.py`
- Create: `backend/app/db_migration/validation.py`

**Interfaces:**
- Produces: `CheckResult(name: str, passed: bool, source: object, target: object, detail: str)`.
- Produces: `ValidationReport(started_at: datetime, checks: list[CheckResult])` with `passed: bool` and `to_dict() -> dict`.
- Produces: `validate_row_counts(source, target, tables) -> list[CheckResult]`.
- Produces: `validate_aggregates(source, target, metadata) -> list[CheckResult]`.
- Produces: `redact_row(table_name: str, row: Mapping[str, object]) -> dict[str, object]`.

- [ ] **Step 1: Write failing validation tests**

Tests must prove that a mismatched count fails the report, Decimal totals compare exactly, and keys containing `password`, `token`, `secret`, or `hash` are replaced by `"<redacted>"`.

- [ ] **Step 2: Verify validation tests fail**

Run `python -m pytest tests\db_migration\test_validation.py -v`.
Expected: FAIL because `validation.py` does not exist.

- [ ] **Step 3: Implement report and checks**

Aggregate exact totals for:

```text
contracts.amount
payments.amount
timesheets.hours
```

Use SQL `SUM` with `Decimal("0")` fallback. The report passes only when every check passes.

- [ ] **Step 4: Verify validation tests pass**

Run the command from Step 2. Expected: all tests PASS.

### Task 4: Implement Transactional Copy and Sequence Repair

**Files:**
- Create: `backend/tests/db_migration/test_sqlite_copy.py`
- Create: `backend/app/db_migration/copy.py`

**Interfaces:**
- Consumes: ordered SQLAlchemy `Table` objects and open source/target connections.
- Produces: `copy_table(source: Connection, target: Connection, table: Table, batch_size: int = 500) -> int`.
- Produces: `copy_all(source: Connection, target: Connection, tables: Sequence[Table], batch_size: int = 500) -> dict[str, int]`.
- Produces: `reset_postgres_sequences(target: Connection, tables: Sequence[Table]) -> dict[str, int]`.

- [ ] **Step 1: Write failing copy tests**

Create a temporary SQLite source and target using SQLAlchemy metadata. Verify row values and primary keys are preserved, rows copy in dependency order, and a forced target error rolls back all target inserts.

- [ ] **Step 2: Verify copy tests fail**

Run `python -m pytest tests\db_migration\test_sqlite_copy.py -v`.
Expected: FAIL because `copy.py` does not exist.

- [ ] **Step 3: Implement bounded copy**

Read rows using `select(table).order_by(*table.primary_key.columns)` with `fetchmany(batch_size)`. Convert each row using `dict(row._mapping)` and insert batches with `target.execute(table.insert(), rows)`. Do not open or commit a transaction inside `copy_all`; the CLI owns the single target transaction.

- [ ] **Step 4: Implement PostgreSQL sequence repair**

For each single integer primary key with a PostgreSQL-owned sequence, execute `setval(pg_get_serial_sequence(...), max_id, max_id > 0)` using bound parameters for values and validated SQLAlchemy identifiers for table/column names. Skip association tables without sequences.

- [ ] **Step 5: Verify copy tests pass**

Run the command from Step 2. Expected: all tests PASS.

### Task 5: Implement Operator CLI

**Files:**
- Create: `backend/app/db_migration/cli.py`
- Modify: `backend/app/db_migration/__init__.py`

**Interfaces:**
- Consumes: `validate_endpoints`, `ordered_tables`, `copy_all`, `reset_postgres_sequences`, and validation functions.
- Produces commands:
  - `python -m app.db_migration.cli inspect --source-url <url>`
  - `python -m app.db_migration.cli migrate --source-url <url> --target-url <url> --report <path>`
  - `python -m app.db_migration.cli validate --source-url <url> --target-url <url> --report <path>`

- [ ] **Step 1: Write CLI argument tests**

Add tests proving missing URLs return exit code `2`, unsafe URL combinations return `1`, and help output lists all three commands.

- [ ] **Step 2: Verify CLI tests fail**

Run `python -m pytest tests\db_migration -v`.
Expected: CLI tests FAIL while earlier tests PASS.

- [ ] **Step 3: Implement CLI orchestration**

The `migrate` flow must:

```python
with target_engine.begin() as target:
    require_empty_target(target_row_counts(target, tables))
    copied = copy_all(source, target, tables)
    reset_postgres_sequences(target, tables)
    report = run_all_validations(source, target, tables)
    if not report.passed:
        raise MigrationValidationError(report)
```

Write the JSON report after rollback/commit using a sanitized report object. Never include raw URLs.

- [ ] **Step 4: Verify all migration unit tests pass**

Run `python -m pytest tests\db_migration -v`.
Expected: all non-integration tests PASS.

### Task 6: Verify Alembic Against PostgreSQL

**Files:**
- Create: `backend/tests/db_migration/test_postgres_integration.py`
- Modify only if required: `backend/alembic/env.py`
- Modify only if required: migration files under `backend/alembic/versions/`

**Interfaces:**
- Consumes environment variable `TEST_POSTGRES_URL`.
- Produces an opt-in test marked `postgres`.

- [ ] **Step 1: Write opt-in PostgreSQL integration test**

Skip unless `TEST_POSTGRES_URL` is set. The test must create a temporary schema name, run Alembic to head in that schema, import a generated SQLite fixture, validate it, and drop only that exact temporary schema in `finally`.

- [ ] **Step 2: Run against the supplied PostgreSQL server**

Run:

```powershell
$env:TEST_POSTGRES_URL='<credential supplied outside source control>'
.\.venv\Scripts\python.exe -m pytest tests\db_migration\test_postgres_integration.py -v
```

Expected: PASS. If Alembic fails, patch only dialect-incompatible migration operations and rerun until PASS.

### Task 7: Document Configuration and Operating Procedure

**Files:**
- Modify: `backend/.env.example`
- Modify: `README.md`

- [ ] **Step 1: Update example configuration**

Document:

```env
DATABASE_URL=postgresql+psycopg://crm_user:percent_encoded_password@127.0.0.1:5432/crm_okr
```

Explain that reserved password characters must be percent-encoded and that real credentials must remain only in `backend/.env` or the deployment secret store.

- [ ] **Step 2: Add exact migration runbook**

Document stop, backup, hash, SQLite integrity, Alembic, migration, report inspection, configuration cutover, smoke test, and rollback commands. Commands must use explicit paths and must never delete the source database.

- [ ] **Step 3: Verify docs match CLI help**

Run `python -m app.db_migration.cli --help` and each subcommand's `--help`. Expected: documented flags match output exactly.

### Task 8: Perform Production Migration and Cutover

**Files:**
- Create at runtime: `backend/backups/app-<timestamp>.db`.
- Create at runtime: `backend/backups/app-<timestamp>.sha256`.
- Create at runtime: `backend/migration-reports/postgresql-<timestamp>.json`.
- Modify locally, never commit: `backend/.env`.

- [ ] **Step 1: Discover and verify PostgreSQL connectivity**

Use the user-supplied target URL through an environment variable. Run `SELECT current_database(), current_user, version()` and confirm the intended empty database.

- [ ] **Step 2: Stop application writers**

Confirm no `uvicorn`, frontend development server, or other process can write to `backend/app.db`.

- [ ] **Step 3: Back up SQLite without deleting or moving the source**

Use SQLite's online backup command or a filesystem copy after writers are stopped. Compute SHA-256 for source and backup and verify hashes match.

- [ ] **Step 4: Validate SQLite integrity**

Run `PRAGMA integrity_check`; expected result is exactly `ok`.

- [ ] **Step 5: Create PostgreSQL schema with Alembic**

Set `DATABASE_URL` only for the command process and run `alembic upgrade head`. Expected: exit `0` and `alembic current` reports the repository head.

- [ ] **Step 6: Execute migration**

Run `python -m app.db_migration.cli migrate` using environment-provided source and target URLs and a timestamped report path. Expected: exit `0`, report `passed: true`.

- [ ] **Step 7: Independently re-run validation**

Run the `validate` command in a new process. Expected: exit `0`, all checks pass.

- [ ] **Step 8: Switch backend configuration**

Update only `backend/.env` with the tested PostgreSQL URL. Keep the prior file as a timestamped backup containing the SQLite URL.

- [ ] **Step 9: Run application smoke tests**

Start the backend and verify `/health`, admin login, `/api/v1/auth/me`, dashboard, one list endpoint per module, and a reversible test record flow. Expected: no HTTP 500 responses and the migrated record counts remain unchanged except for explicitly created smoke-test data.

- [ ] **Step 10: Record cutover result and rollback readiness**

Save the validation report, backup paths, Alembic revision, target database name, and smoke-test result. If any check fails, restore the prior `.env` and restart against the untouched SQLite source.

## Plan Self-Review

- Spec coverage: schema creation, complete copy, sequence repair, validation, backup, cutover, rollback, testing, and documentation are each mapped to a task.
- Placeholder scan: no TBD, TODO, or unspecified implementation step remains.
- Type consistency: all CLI tasks consume the interfaces defined in Tasks 1–4; the production task uses the exact commands defined in Task 5.
- Scope: this plan migrates the database only; subsequent security, transaction, performance, and frontend work remains independently testable future work.

