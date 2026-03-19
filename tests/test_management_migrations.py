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


def test_crop_nutrient_target_migration_upgrade_and_downgrade(tmp_path):
    database_path = tmp_path / "crop_nutrient_targets.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _make_alembic_config(database_url)

    command.upgrade(config, "009")

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
                    organic_matter_preference,
                    growth_stages,
                    created_at,
                    updated_at
                ) VALUES (
                    1,
                    'Corn',
                    'Zea mays',
                    6.0,
                    6.8,
                    5.8,
                    7.2,
                    'high',
                    'moderate',
                    'high',
                    'medium',
                    'moderate',
                    '[]',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            )
        )

    command.upgrade(config, "010")

    upgraded_columns = {column["name"] for column in inspect(engine).get_columns("crop_profiles")}
    assert "target_nitrogen_ppm" in upgraded_columns
    assert "target_phosphorus_ppm" in upgraded_columns
    assert "target_potassium_ppm" in upgraded_columns

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT target_nitrogen_ppm, target_phosphorus_ppm, target_potassium_ppm
                FROM crop_profiles
                WHERE id = 1
                """
            )
        ).mappings().one()

    assert row["target_nitrogen_ppm"] is None
    assert row["target_phosphorus_ppm"] is None
    assert row["target_potassium_ppm"] is None

    command.downgrade(config, "009")

    downgraded_columns = {column["name"] for column in inspect(engine).get_columns("crop_profiles")}
    assert "target_nitrogen_ppm" not in downgraded_columns
    assert "target_phosphorus_ppm" not in downgraded_columns
    assert "target_potassium_ppm" not in downgraded_columns
