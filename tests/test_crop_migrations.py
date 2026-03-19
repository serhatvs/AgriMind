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


def test_crop_profile_migration_upgrade_and_downgrade(tmp_path):
    """Test that the crop profile migration preserves legacy rows and reshapes columns."""
    database_path = tmp_path / "crop_profile_migration.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _make_alembic_config(database_url)

    command.upgrade(config, "003")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO crop_profiles (
                    id,
                    name,
                    variety,
                    min_ph,
                    max_ph,
                    optimal_ph_min,
                    optimal_ph_max,
                    min_nitrogen_ppm,
                    min_phosphorus_ppm,
                    min_potassium_ppm,
                    water_requirement,
                    drainage_requirement,
                    preferred_soil_textures,
                    min_area_hectares,
                    max_slope_percent
                ) VALUES (
                    1,
                    :name,
                    :variety,
                    :min_ph,
                    :max_ph,
                    :optimal_ph_min,
                    :optimal_ph_max,
                    :min_nitrogen_ppm,
                    :min_phosphorus_ppm,
                    :min_potassium_ppm,
                    :water_requirement,
                    :drainage_requirement,
                    :preferred_soil_textures,
                    :min_area_hectares,
                    :max_slope_percent
                )
                """
            ),
            {
                "name": "Wheat",
                "variety": "Winter",
                "min_ph": 5.5,
                "max_ph": 7.5,
                "optimal_ph_min": 6.0,
                "optimal_ph_max": 7.0,
                "min_nitrogen_ppm": 30.0,
                "min_phosphorus_ppm": 20.0,
                "min_potassium_ppm": 150.0,
                "water_requirement": "medium",
                "drainage_requirement": "good",
                "preferred_soil_textures": "loamy,silty",
                "min_area_hectares": 1.0,
                "max_slope_percent": 10.0,
            },
        )

    command.upgrade(config, "head")

    upgraded_columns = {column["name"] for column in inspect(engine).get_columns("crop_profiles")}
    assert "crop_name" in upgraded_columns
    assert "ideal_ph_min" in upgraded_columns
    assert "tolerable_ph_min" in upgraded_columns
    assert "water_requirement_level" in upgraded_columns
    assert "frost_sensitivity" in upgraded_columns
    assert "optimal_temp_min_c" in upgraded_columns
    assert "rainfall_requirement_mm" in upgraded_columns
    assert "created_at" in upgraded_columns
    assert "name" not in upgraded_columns
    assert "min_nitrogen_ppm" not in upgraded_columns

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    crop_name,
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
                    optimal_temp_min_c,
                    optimal_temp_max_c,
                    rainfall_requirement_mm,
                    frost_tolerance_days,
                    heat_tolerance_days,
                    organic_matter_preference,
                    notes,
                    created_at,
                    updated_at
                FROM crop_profiles
                WHERE id = 1
                """
            )
        ).mappings().one()

    assert row["crop_name"] == "Wheat"
    assert row["ideal_ph_min"] == 6.0
    assert row["ideal_ph_max"] == 7.0
    assert row["tolerable_ph_min"] == 5.5
    assert row["tolerable_ph_max"] == 7.5
    assert row["water_requirement_level"] == "medium"
    assert row["drainage_requirement"] == "good"
    assert row["frost_sensitivity"] == "medium"
    assert row["heat_sensitivity"] == "medium"
    assert row["salinity_tolerance"] is None
    assert row["rooting_depth_cm"] is None
    assert row["slope_tolerance"] == 10.0
    assert row["optimal_temp_min_c"] is None
    assert row["optimal_temp_max_c"] is None
    assert row["rainfall_requirement_mm"] is None
    assert row["frost_tolerance_days"] is None
    assert row["heat_tolerance_days"] is None
    assert row["organic_matter_preference"] == "moderate"
    assert row["notes"] == "Legacy variety: Winter"
    assert row["created_at"] is not None
    assert row["updated_at"] is not None

    command.downgrade(config, "003")

    downgraded_columns = {column["name"] for column in inspect(engine).get_columns("crop_profiles")}
    assert "name" in downgraded_columns
    assert "variety" in downgraded_columns
    assert "water_requirement" in downgraded_columns
    assert "max_slope_percent" in downgraded_columns
    assert "crop_name" not in downgraded_columns
    assert "frost_sensitivity" not in downgraded_columns
    assert "optimal_temp_min_c" not in downgraded_columns
