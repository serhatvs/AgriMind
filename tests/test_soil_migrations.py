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


def test_soil_test_migration_upgrade_and_downgrade(tmp_path):
    """Test that the soil test migration preserves and reshapes legacy rows."""
    database_path = tmp_path / "soil_test_migration.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _make_alembic_config(database_url)

    command.upgrade(config, "002")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO fields (
                    id,
                    name,
                    location_name,
                    area_hectares,
                    slope_percent,
                    irrigation_available,
                    infrastructure_score,
                    drainage_quality,
                    created_at,
                    updated_at
                ) VALUES (
                    1,
                    :name,
                    :location_name,
                    :area_hectares,
                    :slope_percent,
                    :irrigation_available,
                    :infrastructure_score,
                    :drainage_quality,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "name": "Legacy Field",
                "location_name": "Legacy Region",
                "area_hectares": 12.5,
                "slope_percent": 2.0,
                "irrigation_available": 1,
                "infrastructure_score": 50,
                "drainage_quality": "good",
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO soil_tests (
                    id,
                    field_id,
                    ph_level,
                    nitrogen_ppm,
                    phosphorus_ppm,
                    potassium_ppm,
                    organic_matter_percent,
                    soil_texture,
                    tested_at
                ) VALUES (
                    1,
                    1,
                    :ph_level,
                    :nitrogen_ppm,
                    :phosphorus_ppm,
                    :potassium_ppm,
                    :organic_matter_percent,
                    :soil_texture,
                    NULL
                )
                """
            ),
            {
                "ph_level": 6.4,
                "nitrogen_ppm": 42.0,
                "phosphorus_ppm": 28.0,
                "potassium_ppm": 190.0,
                "organic_matter_percent": 3.1,
                "soil_texture": "loamy",
            },
        )

    command.upgrade(config, "head")

    upgraded_columns = {column["name"] for column in inspect(engine).get_columns("soil_tests")}
    assert "ph" in upgraded_columns
    assert "texture_class" in upgraded_columns
    assert "sample_date" in upgraded_columns
    assert "created_at" in upgraded_columns
    assert "ph_level" not in upgraded_columns

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    ph,
                    texture_class,
                    sample_date,
                    created_at,
                    ec,
                    calcium_ppm,
                    magnesium_ppm
                FROM soil_tests
                WHERE id = 1
                """
            )
        ).mappings().one()

    assert row["ph"] == 6.4
    assert row["texture_class"] == "loamy"
    assert row["sample_date"] is not None
    assert row["created_at"] is not None
    assert row["ec"] is None
    assert row["calcium_ppm"] is None
    assert row["magnesium_ppm"] is None

    command.downgrade(config, "002")

    downgraded_columns = {column["name"] for column in inspect(engine).get_columns("soil_tests")}
    assert "ph_level" in downgraded_columns
    assert "soil_texture" in downgraded_columns
    assert "tested_at" in downgraded_columns
    assert "created_at" not in downgraded_columns
    assert "ph" not in downgraded_columns
