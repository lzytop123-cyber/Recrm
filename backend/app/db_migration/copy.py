"""Transactional row copying and PostgreSQL sequence repair."""

from collections.abc import Mapping, Sequence

from sqlalchemy import Integer, Table, and_, func, select, text
from sqlalchemy.engine import Connection


def copy_table(
    source: Connection,
    target: Connection,
    table: Table,
    batch_size: int = 500,
    deferred_columns: frozenset[str] = frozenset(),
    deferred_updates: list[dict[str, object]] | None = None,
) -> int:
    """Copy one table without committing the caller-owned transaction."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    primary_key = list(table.primary_key.columns)
    statement = select(table)
    if primary_key:
        statement = statement.order_by(*primary_key)

    copied = 0
    result = source.execute(statement)
    while True:
        batch = result.fetchmany(batch_size)
        if not batch:
            break
        rows = [dict(row._mapping) for row in batch]
        if deferred_columns:
            if deferred_updates is None or not primary_key:
                raise ValueError(
                    f"Deferred foreign keys require tracked updates and a primary key: {table.name}"
                )
            for row in rows:
                update_values = {
                    column_name: row[column_name]
                    for column_name in deferred_columns
                    if row.get(column_name) is not None
                }
                if update_values:
                    deferred_updates.append(
                        {
                            **{column.name: row[column.name] for column in primary_key},
                            **update_values,
                        }
                    )
                for column_name in deferred_columns:
                    row[column_name] = None
        target.execute(table.insert(), rows)
        copied += len(rows)
    return copied


def copy_all(
    source: Connection,
    target: Connection,
    tables: Sequence[Table],
    batch_size: int = 500,
    deferred_columns: Mapping[str, frozenset[str]] | None = None,
) -> dict[str, int]:
    """Copy all tables in the dependency order supplied by the caller."""
    deferred_columns = deferred_columns or {}
    pending_updates: dict[str, list[dict[str, object]]] = {}
    copied: dict[str, int] = {}
    for table in tables:
        updates: list[dict[str, object]] = []
        copied[table.name] = copy_table(
            source,
            target,
            table,
            batch_size=batch_size,
            deferred_columns=deferred_columns.get(table.name, frozenset()),
            deferred_updates=updates,
        )
        if updates:
            pending_updates[table.name] = updates

    table_by_name = {table.name: table for table in tables}
    for table_name, updates in pending_updates.items():
        table = table_by_name[table_name]
        primary_key = list(table.primary_key.columns)
        deferred_names = deferred_columns[table_name]
        for row in updates:
            target.execute(
                table.update().where(
                    and_(*(column == row[column.name] for column in primary_key))
                ),
                {name: row[name] for name in deferred_names if name in row},
            )
    return copied


def reset_postgres_sequences(
    target: Connection, tables: Sequence[Table]
) -> dict[str, int]:
    """Align owned PostgreSQL sequences with imported integer primary keys."""
    if target.dialect.name != "postgresql":
        return {}

    repaired: dict[str, int] = {}
    for table in tables:
        primary_key = list(table.primary_key.columns)
        if len(primary_key) != 1 or not isinstance(primary_key[0].type, Integer):
            continue
        column = primary_key[0]
        sequence_name = target.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": table.fullname, "column_name": column.name},
        ).scalar_one_or_none()
        if not sequence_name:
            continue

        max_id = target.execute(select(func.max(column))).scalar_one_or_none()
        value = int(max_id) if max_id is not None else 1
        target.execute(
            text("SELECT setval(CAST(:sequence_name AS regclass), :value, :is_called)"),
            {
                "sequence_name": sequence_name,
                "value": value,
                "is_called": max_id is not None,
            },
        )
        repaired[table.name] = int(max_id) if max_id is not None else 0
    return repaired
