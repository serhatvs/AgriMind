"""Seed runner that targets the live PostgreSQL schema through reflected tables."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import MetaData, Table, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.seeds.data import SEED_TAG, SeedDataset, build_seed_dataset

SEED_NAMESPACE = UUID("85c612cc-a746-4a40-b7ca-c50f9c58f0ac")
REQUIRED_TABLES = ("fields", "soil_tests", "crop_profiles", "weather_history")
OPTIONAL_TABLES = ("crop_economic_profiles",)


@dataclass(frozen=True, slots=True)
class SeedTables:
    """Reflected SQLAlchemy table objects used by the seed runner."""

    fields: Table
    soil_tests: Table
    crop_profiles: Table
    weather_history: Table
    crop_economic_profiles: Table | None = None


@dataclass(frozen=True, slots=True)
class SeedSummary:
    """Human-readable counts describing one seed run."""

    crops_created: int
    crops_updated: int
    economic_profiles_created: int
    economic_profiles_updated: int
    fields_created: int
    fields_updated: int
    soil_tests_created: int
    soil_tests_updated: int
    weather_rows_created: int
    weather_rows_updated: int

    def render(self) -> str:
        """Format the seed outcome for CLI output."""

        return (
            "Seed refresh complete: "
            f"5 crops ({self.crops_created} created, {self.crops_updated} updated), "
            f"5 economic profiles ({self.economic_profiles_created} created, {self.economic_profiles_updated} updated), "
            f"10 fields ({self.fields_created} created, {self.fields_updated} updated), "
            f"10 soil tests ({self.soil_tests_created} created, {self.soil_tests_updated} updated), "
            f"{self.weather_rows_created + self.weather_rows_updated} weather rows "
            f"({self.weather_rows_created} created, {self.weather_rows_updated} updated)."
        )


def _utcnow() -> datetime:
    """Return a naive UTC timestamp suitable for the live schema."""

    return datetime.now(UTC).replace(tzinfo=None)


def _seed_uuid(entity: str, slug: str) -> str:
    """Return a deterministic UUID string for a seed-managed entity."""

    return str(uuid5(SEED_NAMESPACE, f"{entity}:{slug}"))


def _seed_note(entity: str, slug: str, description: str) -> str:
    """Return a recognizable marker used to identify seed-managed rows."""

    return f"{SEED_TAG} {entity}_slug={slug} | {description}"


def _normalize_value(value: Any) -> Any:
    """Normalize enums into DB-friendly scalar values."""

    if isinstance(value, Enum):
        return value.value
    return value


def _filter_columns(table: Table, values: dict[str, Any]) -> dict[str, Any]:
    """Drop keys that are not present in the reflected live schema."""

    supported_columns = set(table.c.keys())
    return {
        key: _normalize_value(value)
        for key, value in values.items()
        if key in supported_columns
    }


def reflect_seed_tables(engine: Engine) -> SeedTables:
    """Reflect the live tables used by the demo seed runner."""

    metadata = MetaData()
    metadata.reflect(bind=engine, only=(*REQUIRED_TABLES, *OPTIONAL_TABLES))
    missing = [table_name for table_name in REQUIRED_TABLES if table_name not in metadata.tables]
    if missing:
        raise ValueError(f"Seed cannot run because required tables are missing: {', '.join(sorted(missing))}")

    return SeedTables(
        fields=metadata.tables["fields"],
        soil_tests=metadata.tables["soil_tests"],
        crop_profiles=metadata.tables["crop_profiles"],
        weather_history=metadata.tables["weather_history"],
        crop_economic_profiles=metadata.tables.get("crop_economic_profiles"),
    )


def _row_exists(session: Session, table: Table, row_id: str) -> bool:
    """Return whether the target table already contains the given primary key."""

    return session.execute(
        select(table.c.id).where(table.c.id == row_id)
    ).scalar_one_or_none() is not None


def _upsert_row(session: Session, table: Table, values: dict[str, Any]) -> str:
    """Insert or update one row by deterministic seed id."""

    payload = _filter_columns(table, values)
    row_id = payload["id"]
    if _row_exists(session, table, row_id):
        update_payload = {key: value for key, value in payload.items() if key not in {"id", "created_at"}}
        session.execute(update(table).where(table.c.id == row_id).values(**update_payload))
        return "updated"

    session.execute(insert(table).values(**payload))
    return "created"


def _seed_crop_profiles(session: Session, table: Table, dataset: SeedDataset) -> tuple[int, int]:
    """Upsert the canonical crop profiles."""

    created = 0
    updated = 0
    now = _utcnow()

    for spec in dataset.crops:
        action = _upsert_row(
            session,
            table,
            {
                "id": _seed_uuid("crop", spec.slug),
                "crop_name": spec.crop_name,
                "scientific_name": spec.scientific_name,
                "ideal_ph_min": spec.ideal_ph_min,
                "ideal_ph_max": spec.ideal_ph_max,
                "tolerable_ph_min": spec.tolerable_ph_min,
                "tolerable_ph_max": spec.tolerable_ph_max,
                "water_requirement_level": spec.water_requirement_level,
                "drainage_requirement": spec.drainage_requirement,
                "frost_sensitivity": spec.frost_sensitivity,
                "heat_sensitivity": spec.heat_sensitivity,
                "salinity_tolerance": spec.salinity_tolerance,
                "rooting_depth_cm": spec.rooting_depth_cm,
                "slope_tolerance": f"{spec.slope_tolerance:.1f}",
                "organic_matter_preference": spec.organic_matter_preference,
                "notes": _seed_note("crop", spec.slug, spec.description),
                "created_at": now,
                "updated_at": now,
            },
        )
        if action == "created":
            created += 1
        else:
            updated += 1

    return created, updated


def _seed_crop_economic_profiles(
    session: Session,
    table: Table | None,
    dataset: SeedDataset,
) -> tuple[int, int]:
    """Upsert crop-level economic profiles when the target table exists."""

    if table is None:
        return 0, 0

    created = 0
    updated = 0
    now = _utcnow()

    for spec in dataset.economic_profiles:
        action = _upsert_row(
            session,
            table,
            {
                "id": _seed_uuid("crop_economic_profile", spec.crop_slug),
                "crop_name": spec.crop_name,
                "average_market_price_per_unit": spec.average_market_price_per_unit,
                "price_unit": spec.price_unit,
                "base_cost_per_hectare": spec.base_cost_per_hectare,
                "irrigation_cost_factor": spec.irrigation_cost_factor,
                "fertilizer_cost_factor": spec.fertilizer_cost_factor,
                "labor_cost_factor": spec.labor_cost_factor,
                "risk_cost_factor": spec.risk_cost_factor,
                "region": spec.region,
                "created_at": now,
                "updated_at": now,
            },
        )
        if action == "created":
            created += 1
        else:
            updated += 1

    return created, updated


def _seed_fields(session: Session, table: Table, dataset: SeedDataset) -> tuple[int, int]:
    """Upsert the demo field inventory."""

    created = 0
    updated = 0
    now = _utcnow()

    for spec in dataset.fields:
        action = _upsert_row(
            session,
            table,
            {
                "id": _seed_uuid("field", spec.slug),
                "name": spec.name,
                "location_name": spec.location_name,
                "latitude": spec.latitude,
                "longitude": spec.longitude,
                "area_hectares": spec.area_hectares,
                "elevation_meters": spec.elevation_meters,
                "slope_percent": spec.slope_percent,
                "aspect": spec.aspect,
                "irrigation_available": spec.irrigation_available,
                "water_source_type": spec.water_source_type,
                "infrastructure_score": spec.infrastructure_score,
                "notes": _seed_note("field", spec.slug, spec.description),
                "created_at": now,
                "updated_at": now,
            },
        )
        if action == "created":
            created += 1
        else:
            updated += 1

    return created, updated


def _seed_soil_tests(session: Session, table: Table, dataset: SeedDataset) -> tuple[int, int]:
    """Upsert one latest soil test per seeded field."""

    created = 0
    updated = 0
    now = _utcnow()

    for spec in dataset.soils:
        action = _upsert_row(
            session,
            table,
            {
                "id": _seed_uuid("soil", spec.field_slug),
                "field_id": _seed_uuid("field", spec.field_slug),
                "sample_date": spec.sample_date,
                "ph": spec.ph,
                "ec": spec.ec,
                "organic_matter_percent": spec.organic_matter_percent,
                "nitrogen_ppm": spec.nitrogen_ppm,
                "phosphorus_ppm": spec.phosphorus_ppm,
                "potassium_ppm": spec.potassium_ppm,
                "calcium_ppm": spec.calcium_ppm,
                "magnesium_ppm": spec.magnesium_ppm,
                "texture_class": spec.texture_class,
                "drainage_class": spec.drainage_class,
                "depth_cm": spec.depth_cm,
                "water_holding_capacity": spec.water_holding_capacity,
                "notes": _seed_note("soil", spec.field_slug, spec.description),
                "created_at": now,
            },
        )
        if action == "created":
            created += 1
        else:
            updated += 1

    return created, updated


def _seed_weather_history(session: Session, table: Table, dataset: SeedDataset) -> tuple[int, int]:
    """Upsert recent weather history for all seeded fields."""

    created = 0
    updated = 0
    now = _utcnow()

    for spec in dataset.weather:
        weather_slug = f"{spec.field_slug}:{spec.weather_date.isoformat()}"
        action = _upsert_row(
            session,
            table,
            {
                "id": _seed_uuid("weather", weather_slug),
                "field_id": _seed_uuid("field", spec.field_slug),
                "weather_date": spec.weather_date,
                "min_temp": spec.min_temp,
                "max_temp": spec.max_temp,
                "avg_temp": spec.avg_temp,
                "rainfall_mm": spec.rainfall_mm,
                "humidity": spec.humidity,
                "wind_speed": spec.wind_speed,
                "solar_radiation": spec.solar_radiation,
                "et0": spec.et0,
                "created_at": now,
            },
        )
        if action == "created":
            created += 1
        else:
            updated += 1

    return created, updated


def run_seed(session: Session) -> SeedSummary:
    """Populate the existing database with deterministic, idempotent demo data."""

    tables = reflect_seed_tables(session.get_bind())
    dataset = build_seed_dataset()

    crops_created, crops_updated = _seed_crop_profiles(session, tables.crop_profiles, dataset)
    economic_profiles_created, economic_profiles_updated = _seed_crop_economic_profiles(
        session,
        tables.crop_economic_profiles,
        dataset,
    )
    fields_created, fields_updated = _seed_fields(session, tables.fields, dataset)
    soil_tests_created, soil_tests_updated = _seed_soil_tests(session, tables.soil_tests, dataset)
    weather_rows_created, weather_rows_updated = _seed_weather_history(session, tables.weather_history, dataset)

    return SeedSummary(
        crops_created=crops_created,
        crops_updated=crops_updated,
        economic_profiles_created=economic_profiles_created,
        economic_profiles_updated=economic_profiles_updated,
        fields_created=fields_created,
        fields_updated=fields_updated,
        soil_tests_created=soil_tests_created,
        soil_tests_updated=soil_tests_updated,
        weather_rows_created=weather_rows_created,
        weather_rows_updated=weather_rows_updated,
    )


def seed() -> SeedSummary:
    """Create a managed DB session, run the seed, and commit atomically."""

    session = SessionLocal()
    try:
        summary = run_seed(session)
        session.commit()
        return summary
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    """CLI entrypoint for seeding the live AgriMind database."""

    summary = seed()
    print(summary.render())
    print("Run `python seed.py` to refresh the deterministic demo dataset.")


if __name__ == "__main__":
    main()
