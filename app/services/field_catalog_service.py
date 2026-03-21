"""Field catalog read/write services backed by reflected database tables."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.reflection import reflect_tables, table_has_columns
from app.schemas.field import FieldCreate
from app.schemas.field import FieldRead
from app.schemas.field import FieldUpdate
from app.services import field_service
from app.services.errors import NotFoundError


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def _get_row_timestamp(row: Mapping[str, Any], column_name: str) -> datetime:
    """Return a stable timestamp for response serialization."""

    timestamp = row.get(column_name)
    if isinstance(timestamp, datetime):
        return timestamp
    return _utc_now()


def _supports_orm_field_service(db: Session) -> bool:
    """Return whether the current schema matches the ORM-backed field service."""

    return table_has_columns(
        db,
        "fields",
        "drainage_quality",
        "created_at",
        "updated_at",
    )


def _serialize_field_model(field: Any) -> dict[str, Any]:
    """Serialize an ORM field record into the public response shape."""

    return FieldRead.model_validate(field).model_dump()


def _build_insert_payload(
    fields_table,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Filter a create payload to reflected columns and hydrate audit timestamps."""

    filtered_payload = {
        key: value
        for key, value in payload.items()
        if key in fields_table.c
    }
    now = _utc_now()
    if "created_at" in fields_table.c and "created_at" not in filtered_payload:
        filtered_payload["created_at"] = now
    if "updated_at" in fields_table.c and "updated_at" not in filtered_payload:
        filtered_payload["updated_at"] = now
    return filtered_payload


def _serialize_field_row(row: Mapping[str, Any]) -> dict[str, Any]:
    infrastructure_score = row.get("infrastructure_score")
    if infrastructure_score is not None:
        infrastructure_score = int(round(float(infrastructure_score)))

    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "location_name": row.get("location_name"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "area_hectares": row.get("area_hectares"),
        "elevation_meters": row.get("elevation_meters"),
        "slope_percent": row.get("slope_percent"),
        "aspect": row.get("aspect"),
        "irrigation_available": row.get("irrigation_available"),
        "water_source_type": row.get("water_source_type"),
        "infrastructure_score": infrastructure_score,
        "drainage_quality": row.get("drainage_quality"),
        "notes": row.get("notes"),
        "created_at": _get_row_timestamp(row, "created_at"),
        "updated_at": _get_row_timestamp(row, "updated_at"),
    }


def _normalize_field_id(fields_table, field_id: int | str) -> int | str:
    """Coerce path ids to the reflected primary-key type when possible."""

    if not isinstance(field_id, str):
        return field_id

    try:
        python_type = fields_table.c.id.type.python_type
    except (AttributeError, NotImplementedError):
        return field_id

    if python_type is int:
        try:
            return int(field_id)
        except ValueError:
            return field_id
    if python_type is UUID:
        try:
            return UUID(field_id)
        except ValueError:
            return field_id
    return field_id


def _read_field_row(db: Session, field_id: int | str) -> Mapping[str, Any] | None:
    fields_table = reflect_tables(db, "fields")["fields"]
    normalized_field_id = _normalize_field_id(fields_table, field_id)
    row = db.execute(
        select(fields_table).where(fields_table.c.id == normalized_field_id)
    ).mappings().one_or_none()
    return row


def get_field(db: Session, field_id: int | str) -> dict[str, Any]:
    """Return a single field row or raise a not-found service error."""

    if _supports_orm_field_service(db):
        fields_table = reflect_tables(db, "fields")["fields"]
        normalized_field_id = _normalize_field_id(fields_table, field_id)
        field = field_service.get_field(db, normalized_field_id)
        if field is None:
            raise NotFoundError("Field not found")
        return _serialize_field_model(field)

    row = _read_field_row(db, field_id)
    if row is None:
        raise NotFoundError("Field not found")
    return _serialize_field_row(row)


def list_fields(db: Session, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    """Return frontend-friendly field rows from the live database schema."""

    if _supports_orm_field_service(db):
        return [_serialize_field_model(field) for field in field_service.get_fields(db, skip=skip, limit=limit)]

    fields_table = reflect_tables(db, "fields")["fields"]
    query = select(fields_table)
    if "created_at" in fields_table.c:
        query = query.order_by(fields_table.c.created_at.desc(), fields_table.c.name.asc())
    else:
        query = query.order_by(fields_table.c.name.asc())
    rows = db.execute(query.offset(skip).limit(limit)).mappings().all()
    return [_serialize_field_row(row) for row in rows]


def create_field(db: Session, field_data: FieldCreate) -> dict[str, Any]:
    """Insert a field through the reflected live schema and return the stored row."""

    if _supports_orm_field_service(db):
        return _serialize_field_model(field_service.create_field(db, field_data))

    fields_table = reflect_tables(db, "fields")["fields"]
    payload = field_data.model_dump(mode="json", exclude_none=True)
    filtered_payload = _build_insert_payload(fields_table, payload)
    field_id = db.execute(
        insert(fields_table).values(**filtered_payload).returning(fields_table.c.id)
    ).scalar_one()
    _commit(db)
    row = _read_field_row(db, field_id)
    if row is None:
        raise NotFoundError("Field not found")
    return _serialize_field_row(row)


def update_field(db: Session, field_id: int | str, field_data: FieldUpdate) -> dict[str, Any]:
    """Update a field through the reflected live schema and return the stored row."""

    if _supports_orm_field_service(db):
        fields_table = reflect_tables(db, "fields")["fields"]
        normalized_field_id = _normalize_field_id(fields_table, field_id)
        field = field_service.update_field(db, normalized_field_id, field_data)
        if field is None:
            raise NotFoundError("Field not found")
        return _serialize_field_model(field)

    fields_table = reflect_tables(db, "fields")["fields"]
    normalized_field_id = _normalize_field_id(fields_table, field_id)
    existing_row = _read_field_row(db, normalized_field_id)
    if existing_row is None:
        raise NotFoundError("Field not found")

    payload = field_data.model_dump(mode="json", exclude_unset=True)
    filtered_payload = {
        key: value
        for key, value in payload.items()
        if key in fields_table.c
    }
    if "updated_at" in fields_table.c:
        filtered_payload["updated_at"] = _utc_now()
    if filtered_payload:
        db.execute(
            update(fields_table)
            .where(fields_table.c.id == normalized_field_id)
            .values(**filtered_payload)
        )
        _commit(db)

    row = _read_field_row(db, normalized_field_id)
    if row is None:
        raise NotFoundError("Field not found")
    return _serialize_field_row(row)


def delete_field(db: Session, field_id: int | str) -> None:
    """Delete a field through the reflected live schema."""

    if _supports_orm_field_service(db):
        fields_table = reflect_tables(db, "fields")["fields"]
        normalized_field_id = _normalize_field_id(fields_table, field_id)
        field_service.delete_field(db, normalized_field_id)
        return

    fields_table = reflect_tables(db, "fields")["fields"]
    normalized_field_id = _normalize_field_id(fields_table, field_id)
    existing_row = _read_field_row(db, normalized_field_id)
    if existing_row is None:
        raise NotFoundError("Field not found")

    db.execute(delete(fields_table).where(fields_table.c.id == normalized_field_id))
    _commit(db)
