"""Schema inspection helpers for safe database migration."""

from collections.abc import Mapping, Sequence

from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.sql.ddl import sort_tables


def _strongly_connected_components(metadata: MetaData) -> list[frozenset[str]]:
    graph: dict[str, set[str]] = {name: set() for name in metadata.tables}
    for table in metadata.tables.values():
        for foreign_key in table.foreign_keys:
            graph[table.name].add(foreign_key.column.table.name)

    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[frozenset[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in graph[node]:
            if neighbor not in indices:
                visit(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

        if lowlinks[node] == indices[node]:
            component: set[str] = set()
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.add(member)
                if member == node:
                    break
            if len(component) > 1 or node in graph[node]:
                components.append(frozenset(component))

    for name in graph:
        if name not in indices:
            visit(name)
    return components


def _cycle_constraints(metadata: MetaData):
    component_by_table = {
        table_name: component
        for component in _strongly_connected_components(metadata)
        for table_name in component
    }
    constraints = []
    for table in metadata.tables.values():
        for constraint in table.foreign_key_constraints:
            source_component = component_by_table.get(table.name)
            if source_component is None:
                continue
            if all(
                element.column.table.name in source_component
                for element in constraint.elements
            ):
                constraints.append(constraint)
    return constraints


def deferred_foreign_key_columns(
    metadata: MetaData,
) -> dict[str, frozenset[str]]:
    """Return nullable cyclic FK columns that require two-phase copying."""
    deferred: dict[str, set[str]] = {}
    for constraint in _cycle_constraints(metadata):
        for element in constraint.elements:
            column = element.parent
            if not column.nullable:
                raise ValueError(
                    "Cannot migrate non-nullable foreign key cycle: "
                    f"{column.table.name}.{column.name}"
                )
            deferred.setdefault(column.table.name, set()).add(column.name)
    return {name: frozenset(columns) for name, columns in deferred.items()}


def ordered_tables(metadata: MetaData) -> list[Table]:
    """Return tables in deterministic foreign-key dependency order."""
    cycle_foreign_key_ids = {
        id(element)
        for constraint in _cycle_constraints(metadata)
        for element in constraint.elements
    }
    tables = list(
        sort_tables(
            metadata.tables.values(),
            skip_fn=lambda foreign_key: id(foreign_key) in cycle_foreign_key_ids,
        )
    )
    if len(tables) != len(metadata.tables):
        raise ValueError("Unable to derive a complete foreign-key table order")
    return tables


def target_row_counts(
    connection: Connection, tables: Sequence[Table]
) -> dict[str, int]:
    """Count existing rows in every application table."""
    return {
        table.name: int(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
        )
        for table in tables
    }


def require_empty_target(counts: Mapping[str, int]) -> None:
    """Refuse migration when any target application table already has data."""
    populated = {name: count for name, count in counts.items() if count}
    if populated:
        details = ", ".join(f"{name}={count}" for name, count in sorted(populated.items()))
        raise ValueError(f"Target database is not empty: {details}")
