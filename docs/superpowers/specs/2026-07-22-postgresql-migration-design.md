# PostgreSQL Migration Design

## Objective

Move the CRM + OKR system's complete existing SQLite dataset from
`backend/app.db` to PostgreSQL during a planned maintenance window. Preserve
all primary keys, relationships, business identifiers, timestamps, amounts,
users, roles, permissions, and audit data. Keep the original SQLite database
as a read-only rollback source until PostgreSQL has passed verification.

## Scope

This migration phase includes:

- PostgreSQL runtime configuration and driver support.
- An Alembic-created PostgreSQL schema.
- A repeatable SQLite-to-PostgreSQL migration command.
- Row-count, foreign-key, sequence, aggregate, and sample-record validation.
- Application smoke tests against PostgreSQL.
- Backup, cutover, rollback, and operator documentation.

It does not include the later permission, authentication, audit, transaction,
query-performance, or frontend refactors. Those remain separate phases so a
database cutover can be verified independently.

## Assumptions

- PostgreSQL is the production database.
- SQLite remains available only for local development and lightweight tests.
- Existing SQLite data must be retained in full.
- A maintenance window is available, so application writes can be stopped.
- The deployed system is accessible only through the company network or VPN.
- The target PostgreSQL database is empty or dedicated to this application.

## Migration Flow

1. Stop backend and frontend processes that can write data.
2. Create a timestamped copy of `backend/app.db` and record its SHA-256 hash.
3. Confirm the SQLite source passes an integrity check.
4. Configure an empty PostgreSQL target database.
5. Run `alembic upgrade head` against PostgreSQL.
6. Copy rows in dependency order while preserving original primary keys.
7. Reset PostgreSQL identity sequences to the maximum imported ID.
8. Validate counts, foreign keys, business-number uniqueness, monetary totals,
   time totals, and representative records.
9. Start the backend with the PostgreSQL connection string.
10. Run health, authentication, and representative business-module smoke tests.
11. Enable normal access only after every required validation passes.

## Table Ordering

The migration command derives the final ordering from SQLAlchemy metadata and
foreign keys. The expected high-level order is:

1. Departments, permissions, roles.
2. Users and role/permission association tables.
3. Leads and customers.
4. Contracts and payments.
5. Projects and milestones.
6. OKRs and key results.
7. Timesheets, tickets, ticket records, and schedules.
8. Follow-up, business-log, and audit-log tables.

The command must fail before cutover if a cycle or an unknown table makes the
order unsafe.

## Migration Command

Provide a backend CLI that accepts explicit source and target URLs. It must:

- Refuse to use the same database as both source and target.
- Refuse a non-SQLite source or non-PostgreSQL target.
- Refuse a non-empty target unless an explicit, separately confirmed override
  is supplied.
- Use parameterized SQLAlchemy operations, not generated SQL strings.
- Copy rows in bounded batches.
- Run inside a PostgreSQL transaction and roll back on any copy or validation
  failure.
- Avoid printing passwords or full connection URLs.
- Produce a machine-readable validation report and a concise operator summary.
- Support a validation-only mode after import.

## Validation

Cutover is blocked unless all required checks pass:

- SQLite integrity check succeeds.
- Every migrated table has the same source and target row count.
- PostgreSQL has no invalid foreign-key relationships.
- Usernames, role codes, permission codes, and business numbers remain unique.
- Contract and payment amount totals match exactly using decimal arithmetic.
- Timesheet hour totals match exactly.
- Maximum primary keys and PostgreSQL sequence values are aligned.
- A deterministic sample of records matches field by field.
- Alembic reports the expected head revision.

Validation reports must redact password hashes and other credentials from
field-level samples.

## Configuration

- Add a PostgreSQL driver to backend dependencies.
- Continue reading `DATABASE_URL` through the existing settings module.
- Update `.env.example` with a percent-encoding-safe PostgreSQL example.
- Do not commit the real production URL or credentials.
- Document separate development, test, and production settings.

## Cutover and Rollback

Cutover changes only the deployed `DATABASE_URL`; the SQLite source remains
untouched. If migration, validation, backend startup, login, or smoke testing
fails, stop the PostgreSQL-backed process, restore the prior configuration,
and restart against the original SQLite database. Do not attempt a reverse
data sync because writes remain disabled until cutover acceptance.

After acceptance, archive the SQLite backup and validation report. Do not
delete the source as part of the migration command.

## Testing

- Unit-test database URL validation, table ordering, redaction, and sequence
  calculations.
- Integration-test migration from a generated SQLite fixture to a temporary
  PostgreSQL database.
- Test rollback by injecting a copy failure.
- Test refusal of a non-empty target.
- Test validation-only mode.
- Run the existing frontend type check and backend import check after config
  changes.

## Acceptance Criteria

- The complete source dataset is present in PostgreSQL.
- All required validations pass with a saved report.
- The backend starts and registers all expected routes against PostgreSQL.
- Admin login and representative read/write flows succeed.
- No real credentials are written to source control or logs.
- The original SQLite database and its timestamped backup remain recoverable.
- A documented rollback procedure has been exercised or dry-run successfully.

