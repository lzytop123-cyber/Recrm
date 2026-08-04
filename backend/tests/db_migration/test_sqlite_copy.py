import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, UniqueConstraint
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError

from app.db_migration.copy import copy_all, copy_table, reset_postgres_sequences
from app.db_migration.schema import deferred_foreign_key_columns, ordered_tables


def build_metadata(*, unique_child_name: bool = False) -> MetaData:
    metadata = MetaData()
    Table(
        "parents",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(50), nullable=False),
    )
    child_args = [UniqueConstraint("name")] if unique_child_name else []
    Table(
        "children",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", ForeignKey("parents.id"), nullable=False),
        Column("name", String(50), nullable=False),
        *child_args,
    )
    return metadata


def test_copy_table_preserves_primary_keys_and_values():
    metadata = build_metadata()
    source_engine = create_engine("sqlite:///:memory:")
    target_engine = create_engine("sqlite:///:memory:")
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)
    parents = metadata.tables["parents"]
    with source_engine.begin() as source:
        source.execute(parents.insert(), [{"id": 7, "name": "Root"}])

    with source_engine.connect() as source, target_engine.begin() as target:
        copied = copy_table(source, target, parents, batch_size=1)
    with target_engine.connect() as target:
        row = target.execute(select(parents)).mappings().one()

    assert copied == 1
    assert dict(row) == {"id": 7, "name": "Root"}


def test_copy_all_uses_dependency_order():
    metadata = build_metadata()
    source_engine = create_engine("sqlite:///:memory:")
    target_engine = create_engine("sqlite:///:memory:")
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)
    with source_engine.begin() as source:
        source.execute(metadata.tables["parents"].insert(), {"id": 1, "name": "P"})
        source.execute(
            metadata.tables["children"].insert(),
            {"id": 2, "parent_id": 1, "name": "C"},
        )

    with source_engine.connect() as source, target_engine.begin() as target:
        copied = copy_all(source, target, list(metadata.sorted_tables))

    assert copied == {"parents": 1, "children": 1}


def test_outer_transaction_rolls_back_all_rows_on_copy_failure():
    source_metadata = build_metadata()
    target_metadata = build_metadata(unique_child_name=True)
    source_engine = create_engine("sqlite:///:memory:")
    target_engine = create_engine("sqlite:///:memory:")
    source_metadata.create_all(source_engine)
    target_metadata.create_all(target_engine)
    with source_engine.begin() as source:
        source.execute(source_metadata.tables["parents"].insert(), {"id": 1, "name": "P"})
        source.execute(
            source_metadata.tables["children"].insert(),
            [
                {"id": 1, "parent_id": 1, "name": "duplicate"},
                {"id": 2, "parent_id": 1, "name": "duplicate"},
            ],
        )

    with pytest.raises(IntegrityError):
        with source_engine.connect() as source, target_engine.begin() as target:
            copy_all(source, target, list(target_metadata.sorted_tables), batch_size=10)

    with target_engine.connect() as target:
        parent_count = target.execute(
            select(func.count()).select_from(target_metadata.tables["parents"])
        ).scalar_one()
    assert parent_count == 0


def test_sequence_repair_is_skipped_for_non_postgresql_target():
    metadata = build_metadata()
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)

    with engine.begin() as connection:
        repaired = reset_postgres_sequences(connection, list(metadata.sorted_tables))

    assert repaired == {}


def test_copy_all_restores_nullable_cyclic_foreign_keys_after_insert():
    metadata = MetaData()
    left = Table(
        "left_rows",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("right_id", ForeignKey("right_rows.id"), nullable=True),
    )
    right = Table(
        "right_rows",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("left_id", ForeignKey("left_rows.id"), nullable=True),
    )
    source_engine = create_engine("sqlite:///:memory:")
    target_engine = create_engine("sqlite:///:memory:")

    @event.listens_for(target_engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    metadata.create_all(source_engine)
    metadata.create_all(target_engine)
    with source_engine.begin() as source:
        source.execute(left.insert(), {"id": 1, "right_id": 2})
        source.execute(right.insert(), {"id": 2, "left_id": 1})

    with source_engine.connect() as source, target_engine.begin() as target:
        copied = copy_all(
            source,
            target,
            ordered_tables(metadata),
            deferred_columns=deferred_foreign_key_columns(metadata),
        )

    with target_engine.connect() as target:
        left_row = target.execute(select(left)).mappings().one()
        right_row = target.execute(select(right)).mappings().one()

    assert copied == {"left_rows": 1, "right_rows": 1}
    assert left_row["right_id"] == 2
    assert right_row["left_id"] == 1
