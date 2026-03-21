"""Crop catalog read/write services backed by reflected database tables."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.reflection import reflect_tables, table_has_columns
from app.schemas.crop_profile import CropProfileRead
from app.schemas.crop_profile import CropProfileCreate
from app.schemas.crop_profile import CropProfileUpdate
from app.services import crop_service
from app.services.errors import ConflictError
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


def _supports_orm_crop_service(db: Session) -> bool:
    """Return whether the current schema matches the ORM-backed crop service."""

    return table_has_columns(
        db,
        "crop_profiles",
        "optimal_temp_min_c",
        "optimal_temp_max_c",
        "rainfall_requirement_mm",
        "growth_stages",
        "created_at",
        "updated_at",
    )


def _serialize_crop_model(crop: Any) -> dict[str, Any]:
    """Serialize an ORM crop record into the public response shape."""

    return CropProfileRead.model_validate(crop).model_dump()


def _build_insert_payload(
    crop_profiles_table,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Filter a create payload to reflected columns and hydrate required defaults."""

    filtered_payload = {
        key: value
        for key, value in payload.items()
        if key in crop_profiles_table.c
    }
    now = _utc_now()
    if "growth_stages" in crop_profiles_table.c and "growth_stages" not in filtered_payload:
        filtered_payload["growth_stages"] = []
    if "created_at" in crop_profiles_table.c and "created_at" not in filtered_payload:
        filtered_payload["created_at"] = now
    if "updated_at" in crop_profiles_table.c and "updated_at" not in filtered_payload:
        filtered_payload["updated_at"] = now
    return filtered_payload


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _serialize_crop_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "crop_name": row.get("crop_name"),
        "scientific_name": row.get("scientific_name"),
        "ideal_ph_min": row.get("ideal_ph_min"),
        "ideal_ph_max": row.get("ideal_ph_max"),
        "tolerable_ph_min": row.get("tolerable_ph_min"),
        "tolerable_ph_max": row.get("tolerable_ph_max"),
        "water_requirement_level": row.get("water_requirement_level"),
        "drainage_requirement": row.get("drainage_requirement"),
        "frost_sensitivity": row.get("frost_sensitivity"),
        "heat_sensitivity": row.get("heat_sensitivity"),
        "salinity_tolerance": row.get("salinity_tolerance"),
        "rooting_depth_cm": row.get("rooting_depth_cm"),
        "slope_tolerance": _coerce_float(row.get("slope_tolerance")),
        "optimal_temp_min_c": row.get("optimal_temp_min_c"),
        "optimal_temp_max_c": row.get("optimal_temp_max_c"),
        "tolerable_temp_min_c": row.get("tolerable_temp_min_c"),
        "tolerable_temp_max_c": row.get("tolerable_temp_max_c"),
        "rainfall_requirement_mm": row.get("rainfall_requirement_mm"),
        "preferred_rainfall_min_mm": row.get("preferred_rainfall_min_mm"),
        "preferred_rainfall_max_mm": row.get("preferred_rainfall_max_mm"),
        "frost_tolerance_days": row.get("frost_tolerance_days"),
        "heat_tolerance_days": row.get("heat_tolerance_days"),
        "target_nitrogen_ppm": row.get("target_nitrogen_ppm"),
        "target_phosphorus_ppm": row.get("target_phosphorus_ppm"),
        "target_potassium_ppm": row.get("target_potassium_ppm"),
        "organic_matter_preference": row.get("organic_matter_preference"),
        "notes": row.get("notes"),
        "growth_stages": row.get("growth_stages") or [],
        "created_at": _get_row_timestamp(row, "created_at"),
        "updated_at": _get_row_timestamp(row, "updated_at"),
    }


def _normalize_crop_id(crop_profiles_table, crop_id: int | str) -> int | str:
    """Coerce path ids to the reflected primary-key type when possible."""

    if not isinstance(crop_id, str):
        return crop_id

    try:
        python_type = crop_profiles_table.c.id.type.python_type
    except (AttributeError, NotImplementedError):
        return crop_id

    if python_type is int:
        try:
            return int(crop_id)
        except ValueError:
            return crop_id
    if python_type is UUID:
        try:
            return UUID(crop_id)
        except ValueError:
            return crop_id
    return crop_id


def _read_crop_row(db: Session, crop_id: int | str) -> Mapping[str, Any] | None:
    crop_profiles_table = reflect_tables(db, "crop_profiles")["crop_profiles"]
    normalized_crop_id = _normalize_crop_id(crop_profiles_table, crop_id)
    row = db.execute(
        select(crop_profiles_table).where(crop_profiles_table.c.id == normalized_crop_id)
    ).mappings().one_or_none()
    return row


def _ensure_unique_crop_name(
    db: Session,
    crop_name: str,
    *,
    exclude_crop_id: int | str | None = None,
) -> None:
    crop_profiles_table = reflect_tables(db, "crop_profiles")["crop_profiles"]
    query = select(crop_profiles_table.c.id).where(
        func.lower(crop_profiles_table.c.crop_name) == crop_name.lower()
    )
    if exclude_crop_id is not None:
        normalized_crop_id = _normalize_crop_id(crop_profiles_table, exclude_crop_id)
        query = query.where(crop_profiles_table.c.id != normalized_crop_id)
    existing_crop_id = db.execute(query).scalar_one_or_none()
    if existing_crop_id is not None:
        raise ConflictError(f"Crop profile with name '{crop_name}' already exists")


def get_crop(db: Session, crop_id: int | str) -> dict[str, Any]:
    """Return a single crop profile row or raise a not-found service error."""

    if _supports_orm_crop_service(db):
        crop_profiles_table = reflect_tables(db, "crop_profiles")["crop_profiles"]
        normalized_crop_id = _normalize_crop_id(crop_profiles_table, crop_id)
        crop = crop_service.get_crop(db, normalized_crop_id)
        if crop is None:
            raise NotFoundError("Crop not found")
        return _serialize_crop_model(crop)

    row = _read_crop_row(db, crop_id)
    if row is None:
        raise NotFoundError("Crop not found")
    return _serialize_crop_row(row)


def list_crops(db: Session, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    """Return frontend-friendly crop rows from the live database schema."""

    if _supports_orm_crop_service(db):
        return [_serialize_crop_model(crop) for crop in crop_service.get_crops(db, skip=skip, limit=limit)]

    crop_profiles_table = reflect_tables(db, "crop_profiles")["crop_profiles"]
    query = select(crop_profiles_table)
    if "created_at" in crop_profiles_table.c:
        query = query.order_by(crop_profiles_table.c.created_at.desc(), crop_profiles_table.c.crop_name.asc())
    else:
        query = query.order_by(crop_profiles_table.c.crop_name.asc())
    rows = db.execute(query.offset(skip).limit(limit)).mappings().all()
    return [_serialize_crop_row(row) for row in rows]


def create_crop(db: Session, crop_data: CropProfileCreate) -> dict[str, Any]:
    """Insert a crop profile through the reflected live schema and return the stored row."""

    if _supports_orm_crop_service(db):
        return _serialize_crop_model(crop_service.create_crop(db, crop_data))

    _ensure_unique_crop_name(db, crop_data.crop_name)
    crop_profiles_table = reflect_tables(db, "crop_profiles")["crop_profiles"]
    payload = crop_data.model_dump(mode="json", exclude_none=True)
    filtered_payload = _build_insert_payload(crop_profiles_table, payload)
    crop_id = db.execute(
        insert(crop_profiles_table).values(**filtered_payload).returning(crop_profiles_table.c.id)
    ).scalar_one()
    _commit(db)
    row = _read_crop_row(db, crop_id)
    if row is None:
        raise NotFoundError("Crop not found")
    return _serialize_crop_row(row)


def update_crop(db: Session, crop_id: int | str, crop_data: CropProfileUpdate) -> dict[str, Any]:
    """Update a crop profile through the reflected live schema and return the stored row."""

    if _supports_orm_crop_service(db):
        crop_profiles_table = reflect_tables(db, "crop_profiles")["crop_profiles"]
        normalized_crop_id = _normalize_crop_id(crop_profiles_table, crop_id)
        return _serialize_crop_model(crop_service.update_crop(db, normalized_crop_id, crop_data))

    crop_profiles_table = reflect_tables(db, "crop_profiles")["crop_profiles"]
    normalized_crop_id = _normalize_crop_id(crop_profiles_table, crop_id)
    existing_row = _read_crop_row(db, normalized_crop_id)
    if existing_row is None:
        raise NotFoundError("Crop not found")

    payload = crop_data.model_dump(mode="json", exclude_unset=True)
    if "crop_name" in payload:
        _ensure_unique_crop_name(db, payload["crop_name"], exclude_crop_id=normalized_crop_id)
    filtered_payload = {
        key: value
        for key, value in payload.items()
        if key in crop_profiles_table.c
    }
    if "updated_at" in crop_profiles_table.c:
        filtered_payload["updated_at"] = _utc_now()
    if filtered_payload:
        db.execute(
            update(crop_profiles_table)
            .where(crop_profiles_table.c.id == normalized_crop_id)
            .values(**filtered_payload)
        )
        _commit(db)

    row = _read_crop_row(db, normalized_crop_id)
    if row is None:
        raise NotFoundError("Crop not found")
    return _serialize_crop_row(row)
