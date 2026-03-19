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


def test_weather_history_migration_upgrade_and_downgrade(tmp_path):
    """Test that the weather history migration creates and removes the new table cleanly."""
    database_path = tmp_path / "weather_history_migration.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _make_alembic_config(database_url)

    command.upgrade(config, "004")

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
                "name": "Weather Field",
                "location_name": "Weather Region",
                "area_hectares": 12.5,
                "slope_percent": 2.0,
                "irrigation_available": 1,
                "infrastructure_score": 50,
                "drainage_quality": "good",
            },
        )

    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert "weather_history" in inspector.get_table_names()

    columns = {column["name"] for column in inspector.get_columns("weather_history")}
    assert {
        "id",
        "field_id",
        "date",
        "min_temp",
        "max_temp",
        "avg_temp",
        "rainfall_mm",
        "humidity",
        "wind_speed",
        "solar_radiation",
        "et0",
        "created_at",
    }.issubset(columns)

    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("weather_history")
    }
    assert "uq_weather_history_field_id_date" in unique_constraints

    check_constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("weather_history")
    }
    assert "ck_weather_history_temperature_order" in check_constraints
    assert "ck_weather_history_humidity_range" in check_constraints

    indexes = {
        index["name"]
        for index in inspector.get_indexes("weather_history")
    }
    assert "ix_weather_history_field_id" in indexes

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO weather_history (
                    id,
                    field_id,
                    date,
                    min_temp,
                    max_temp,
                    avg_temp,
                    rainfall_mm,
                    humidity,
                    wind_speed,
                    solar_radiation,
                    et0,
                    created_at
                ) VALUES (
                    1,
                    1,
                    :date,
                    :min_temp,
                    :max_temp,
                    :avg_temp,
                    :rainfall_mm,
                    :humidity,
                    :wind_speed,
                    :solar_radiation,
                    :et0,
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "date": "2026-03-19",
                "min_temp": 8.0,
                "max_temp": 20.0,
                "avg_temp": 14.0,
                "rainfall_mm": 5.0,
                "humidity": 62.0,
                "wind_speed": 12.0,
                "solar_radiation": 18.0,
                "et0": 3.4,
            },
        )

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT field_id, avg_temp, rainfall_mm
                FROM weather_history
                WHERE id = 1
                """
            )
        ).mappings().one()

    assert row["field_id"] == 1
    assert row["avg_temp"] == 14.0
    assert row["rainfall_mm"] == 5.0

    command.downgrade(config, "004")

    assert "weather_history" not in inspect(engine).get_table_names()
