import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, create_engine

from app.db_migration.schema import (
    deferred_foreign_key_columns,
    ordered_tables,
    require_empty_target,
    target_row_counts,
)


def build_metadata() -> MetaData:
    metadata = MetaData()
    Table("parents", metadata, Column("id", Integer, primary_key=True))
    Table(
        "children",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", ForeignKey("parents.id"), nullable=False),
    )
    return metadata


def test_orders_referenced_table_before_dependent_table():
    names = [table.name for table in ordered_tables(build_metadata())]

    assert names == ["parents", "children"]


def test_table_order_is_deterministic():
    metadata = build_metadata()

    assert [t.name for t in ordered_tables(metadata)] == [
        t.name for t in ordered_tables(metadata)
    ]


def test_target_row_counts_reads_each_table():
    metadata = build_metadata()
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(metadata.tables["parents"].insert(), {"id": 1})
        counts = target_row_counts(connection, ordered_tables(metadata))

    assert counts == {"parents": 1, "children": 0}


def test_require_empty_target_accepts_zero_counts():
    require_empty_target({"users": 0, "roles": 0})


def test_require_empty_target_rejects_existing_rows():
    with pytest.raises(ValueError, match="not empty"):
        require_empty_target({"users": 1, "roles": 0})


def test_nullable_cycle_is_deferred_for_two_phase_copy():
    metadata = MetaData()
    Table(
        "left_rows",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("right_id", ForeignKey("right_rows.id"), nullable=True),
    )
    Table(
        "right_rows",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("left_id", ForeignKey("left_rows.id"), nullable=True),
    )

    deferred = deferred_foreign_key_columns(metadata)

    assert deferred == {
        "left_rows": frozenset({"right_id"}),
        "right_rows": frozenset({"left_id"}),
    }
    assert {table.name for table in ordered_tables(metadata)} == {
        "left_rows",
        "right_rows",
    }


def test_non_nullable_cycle_is_rejected():
    metadata = MetaData()
    Table(
        "left_rows",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("right_id", ForeignKey("right_rows.id"), nullable=False),
    )
    Table(
        "right_rows",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("left_id", ForeignKey("left_rows.id"), nullable=False),
    )

    with pytest.raises(ValueError, match="non-nullable foreign key cycle"):
        deferred_foreign_key_columns(metadata)
