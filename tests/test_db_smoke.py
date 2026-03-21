from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from sqlalchemy import MetaData, Table, delete, insert, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import check_database_connection, create_engine_from_settings, create_session_factory


def _load_smoke_database_url() -> str | None:
    """Resolve the live smoke-test database URL without using the sqlite test default."""

    explicit_url = os.getenv("AGRIMIND_SMOKE_DATABASE_URL")
    if explicit_url:
        return explicit_url

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return None

    dotenv_url = dotenv_values(env_path).get("DATABASE_URL")
    if isinstance(dotenv_url, str) and dotenv_url.strip():
        return dotenv_url.strip()
    return None


@pytest.fixture(scope="session")
def smoke_database_url() -> str:
    """Return the configured PostgreSQL URL for live DB smoke tests."""

    database_url = _load_smoke_database_url()
    if not database_url:
        pytest.skip("Smoke DB URL is not configured. Set AGRIMIND_SMOKE_DATABASE_URL or add DATABASE_URL to .env.")

    backend_name = make_url(database_url).get_backend_name()
    if backend_name != "postgresql":
        pytest.skip(f"Smoke DB tests require PostgreSQL, got {backend_name!r}.")
    return database_url


@pytest.fixture(scope="session")
def smoke_engine(smoke_database_url: str) -> Engine:
    """Create an engine for the live PostgreSQL smoke tests."""

    engine = create_engine_from_settings(Settings(_env_file=None, DATABASE_URL=smoke_database_url))
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def smoke_session_factory(smoke_engine: Engine) -> sessionmaker[Session]:
    """Return the project session factory bound to the live smoke-test database."""

    return create_session_factory(smoke_engine)


@pytest.fixture(scope="session")
def smoke_tables(smoke_engine: Engine) -> dict[str, Table]:
    """Reflect the core live tables used by the smoke suite."""

    metadata = MetaData()
    metadata.reflect(bind=smoke_engine, only=("fields", "crop_profiles", "soil_tests"))
    return {
        "fields": metadata.tables["fields"],
        "crop_profiles": metadata.tables["crop_profiles"],
        "soil_tests": metadata.tables["soil_tests"],
    }


@pytest.fixture
def smoke_tag() -> str:
    """Return a unique tag used to isolate and clean smoke-test rows."""

    return f"[db-smoke:{uuid4()}]"


@pytest.fixture
def smoke_session(
    smoke_session_factory: sessionmaker[Session],
    smoke_tables: dict[str, Table],
    smoke_tag: str,
) -> Session:
    """Yield a live PostgreSQL session and clean up all rows created by the test."""

    session = smoke_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

        cleanup_session = smoke_session_factory()
        try:
            cleanup_session.execute(
                delete(smoke_tables["soil_tests"]).where(smoke_tables["soil_tests"].c.notes.like(f"{smoke_tag}%"))
            )
            cleanup_session.execute(
                delete(smoke_tables["fields"]).where(smoke_tables["fields"].c.notes.like(f"{smoke_tag}%"))
            )
            cleanup_session.execute(
                delete(smoke_tables["crop_profiles"]).where(
                    smoke_tables["crop_profiles"].c.notes.like(f"{smoke_tag}%")
                )
            )
            cleanup_session.commit()
        finally:
            cleanup_session.close()


@pytest.fixture
def field_payload(smoke_tag: str) -> dict[str, object]:
    """Return a realistic field payload for the smoke suite."""

    return {
        "name": f"Smoke Field {smoke_tag}",
        "location_name": "Konya Demo Parcel",
        "latitude": 37.8746,
        "longitude": 32.4932,
        "area_hectares": 14.2,
        "elevation_meters": 1018.0,
        "slope_percent": 2.7,
        "aspect": "south",
        "irrigation_available": True,
        "water_source_type": "well",
        "infrastructure_score": 74.0,
        "notes": f"{smoke_tag} field",
    }


@pytest.fixture
def crop_payload(smoke_tag: str) -> dict[str, object]:
    """Return a realistic crop profile payload for the smoke suite."""

    return {
        "crop_name": f"Smoke Corn {smoke_tag}",
        "scientific_name": "Zea mays",
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 6.8,
        "tolerable_ph_min": 5.7,
        "tolerable_ph_max": 7.2,
        "water_requirement_level": "high",
        "drainage_requirement": "moderate",
        "frost_sensitivity": "high",
        "heat_sensitivity": "medium",
        "salinity_tolerance": "moderate",
        "rooting_depth_cm": 150.0,
        "slope_tolerance": "8.0",
        "organic_matter_preference": "moderate",
        "notes": f"{smoke_tag} crop",
    }


def _insert_field(
    session: Session,
    fields_table: Table,
    payload: dict[str, object],
):
    """Insert a field row and return its generated primary key."""

    return session.execute(
        insert(fields_table).values(**payload).returning(fields_table.c.id)
    ).scalar_one()


def _insert_crop_profile(
    session: Session,
    crop_profiles_table: Table,
    payload: dict[str, object],
):
    """Insert a crop profile row and return its generated primary key."""

    return session.execute(
        insert(crop_profiles_table).values(**payload).returning(crop_profiles_table.c.id)
    ).scalar_one()


def _insert_soil_test(
    session: Session,
    soil_tests_table: Table,
    *,
    field_id,
    notes: str,
):
    """Insert a soil test linked to a field and return its generated primary key."""

    return session.execute(
        insert(soil_tests_table)
        .values(
            field_id=field_id,
            sample_date=date(2026, 3, 21),
            ph=6.4,
            ec=0.7,
            organic_matter_percent=3.6,
            nitrogen_ppm=42.0,
            phosphorus_ppm=24.0,
            potassium_ppm=215.0,
            calcium_ppm=1630.0,
            magnesium_ppm=190.0,
            texture_class="loam",
            drainage_class="good",
            depth_cm=120.0,
            water_holding_capacity=24.0,
            notes=notes,
        )
        .returning(soil_tests_table.c.id)
    ).scalar_one()


def test_smoke_database_connection(smoke_engine: Engine):
    """The application can open a live PostgreSQL connection and execute a trivial query."""

    check_database_connection(smoke_engine)

    with smoke_engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar_one()

    assert result == 1


def test_smoke_insert_and_read_field(
    smoke_session: Session,
    smoke_session_factory: sessionmaker[Session],
    smoke_tables: dict[str, Table],
    field_payload: dict[str, object],
):
    """A field can be inserted into PostgreSQL and read back from a fresh session."""

    field_id = _insert_field(smoke_session, smoke_tables["fields"], field_payload)
    smoke_session.commit()

    with smoke_session_factory() as read_session:
        field_row = read_session.execute(
            select(smoke_tables["fields"]).where(smoke_tables["fields"].c.id == field_id)
        ).mappings().one()

    assert field_row["id"] == field_id
    assert field_row["name"] == field_payload["name"]
    assert field_row["irrigation_available"] is True


def test_smoke_insert_and_read_crop_profile(
    smoke_session: Session,
    smoke_session_factory: sessionmaker[Session],
    smoke_tables: dict[str, Table],
    crop_payload: dict[str, object],
):
    """A crop profile can be inserted into PostgreSQL and read back from a fresh session."""

    crop_id = _insert_crop_profile(smoke_session, smoke_tables["crop_profiles"], crop_payload)
    smoke_session.commit()

    with smoke_session_factory() as read_session:
        crop_row = read_session.execute(
            select(smoke_tables["crop_profiles"]).where(smoke_tables["crop_profiles"].c.id == crop_id)
        ).mappings().one()

    assert crop_row["id"] == crop_id
    assert crop_row["crop_name"] == crop_payload["crop_name"]
    assert crop_row["water_requirement_level"] == crop_payload["water_requirement_level"]


def test_smoke_insert_and_read_soil_test_linked_to_field(
    smoke_session: Session,
    smoke_session_factory: sessionmaker[Session],
    smoke_tables: dict[str, Table],
    field_payload: dict[str, object],
    smoke_tag: str,
):
    """A soil test can be inserted for a field and read back with the FK linkage intact."""

    field_id = _insert_field(smoke_session, smoke_tables["fields"], field_payload)
    soil_test_id = _insert_soil_test(
        smoke_session,
        smoke_tables["soil_tests"],
        field_id=field_id,
        notes=f"{smoke_tag} soil",
    )
    smoke_session.commit()

    with smoke_session_factory() as read_session:
        soil_row = read_session.execute(
            select(smoke_tables["soil_tests"]).where(smoke_tables["soil_tests"].c.id == soil_test_id)
        ).mappings().one()
        field_row = read_session.execute(
            select(smoke_tables["fields"]).where(smoke_tables["fields"].c.id == soil_row["field_id"])
        ).mappings().one()

    assert soil_row["id"] == soil_test_id
    assert soil_row["field_id"] == field_id
    assert soil_row["texture_class"] == "loam"
    assert field_row["id"] == field_id
    assert field_row["name"] == field_payload["name"]
