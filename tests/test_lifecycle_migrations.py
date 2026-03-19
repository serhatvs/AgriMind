import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_crop_lifecycle_migration_upgrade_and_downgrade(tmp_path):
    database_path = tmp_path / "crop_lifecycle_migration.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _make_alembic_config(database_url)

    command.upgrade(config, "007")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO crop_profiles (
                    id,
                    crop_name,
                    scientific_name,
                    ideal_ph_min,
                    ideal_ph_max,
                    tolerable_ph_min,
                    tolerable_ph_max,
                    water_requirement_level,
                    drainage_requirement,
                    frost_sensitivity,
                    heat_sensitivity,
                    salinity_tolerance,
                    rooting_depth_cm,
                    slope_tolerance,
                    organic_matter_preference,
                    created_at,
                    updated_at
                ) VALUES (
                    1,
                    'Wheat',
                    'Triticum aestivum',
                    6.0,
                    7.0,
                    5.5,
                    7.5,
                    'medium',
                    'good',
                    'medium',
                    'medium',
                    'low',
                    120.0,
                    10.0,
                    'moderate',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            )
        )

    command.upgrade(config, "009")

    inspector = inspect(engine)
    assert "field_crop_cycles" in inspector.get_table_names()
    assert "growth_stages" in {column["name"] for column in inspector.get_columns("crop_profiles")}

    cycle_columns = {column["name"] for column in inspector.get_columns("field_crop_cycles")}
    assert {"id", "field_id", "crop_id", "sowing_date", "current_stage", "created_at", "updated_at"}.issubset(
        cycle_columns
    )

    cycle_uniques = {constraint["name"] for constraint in inspector.get_unique_constraints("field_crop_cycles")}
    assert "uq_field_crop_cycles_field_id" in cycle_uniques

    cycle_indexes = {index["name"] for index in inspector.get_indexes("field_crop_cycles")}
    assert "ix_field_crop_cycles_crop_id" in cycle_indexes

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT growth_stages
                FROM crop_profiles
                WHERE id = 1
                """
            )
        ).mappings().one()

    growth_stages = row["growth_stages"]
    if isinstance(growth_stages, str):
        growth_stages = json.loads(growth_stages)
    assert growth_stages == []

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO fields (
                    id,
                    name,
                    location_name,
                    latitude,
                    longitude,
                    area_hectares,
                    elevation_meters,
                    slope_percent,
                    irrigation_available,
                    infrastructure_score,
                    drainage_quality,
                    created_at,
                    updated_at
                ) VALUES (
                    1,
                    'Lifecycle Field',
                    'Lifecycle Valley',
                    39.1012,
                    -94.5788,
                    8.0,
                    215.0,
                    1.5,
                    1,
                    82,
                    'good',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO field_crop_cycles (
                    id,
                    field_id,
                    crop_id,
                    sowing_date,
                    current_stage,
                    created_at,
                    updated_at
                ) VALUES (
                    1,
                    1,
                    1,
                    '2026-03-01',
                    'germination',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            )
        )

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT current_stage
                FROM field_crop_cycles
                WHERE field_id = 1 AND crop_id = 1
                """
            )
        ).mappings().one()

    assert row["current_stage"] == "germination"

    command.downgrade(config, "008")

    downgraded_tables = inspect(engine).get_table_names()
    assert "field_crop_cycles" not in downgraded_tables
    assert "growth_stages" not in {column["name"] for column in inspect(engine).get_columns("crop_profiles")}
