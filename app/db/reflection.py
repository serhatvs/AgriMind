"""Helpers for reflecting live database tables through a SQLAlchemy session."""

from __future__ import annotations

from sqlalchemy import MetaData, Table, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def _get_bind(session: Session) -> Engine:
    """Return the engine bound to the current SQLAlchemy session."""

    bind = session.get_bind()
    if bind is None:
        raise ValueError("Database session is not bound to an engine.")
    return bind


def reflect_tables(session: Session, *table_names: str) -> dict[str, Table]:
    """Reflect the requested tables from the live database schema."""

    metadata = MetaData()
    metadata.reflect(bind=_get_bind(session), only=table_names)
    missing = [table_name for table_name in table_names if table_name not in metadata.tables]
    if missing:
        raise ValueError(f"Required tables are missing from the database schema: {', '.join(sorted(missing))}")
    return {table_name: metadata.tables[table_name] for table_name in table_names}


def get_table_columns(session: Session, table_name: str) -> set[str]:
    """Return the set of reflected column names for a table."""

    inspector = inspect(_get_bind(session))
    return {column["name"] for column in inspector.get_columns(table_name)}


def table_has_columns(session: Session, table_name: str, *column_names: str) -> bool:
    """Return whether the table contains every requested column."""

    available_columns = get_table_columns(session, table_name)
    return all(column_name in available_columns for column_name in column_names)


def tables_exist(session: Session, *table_names: str) -> bool:
    """Return whether all requested tables exist in the current database."""

    inspector = inspect(_get_bind(session))
    available_tables = set(inspector.get_table_names())
    return all(table_name in available_tables for table_name in table_names)
