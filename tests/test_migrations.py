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


def test_field_migration_upgrade_and_downgrade(tmp_path):
    """Test that the field expansion migration preserves and reshapes existing rows."""
    database_path = tmp_path / "field_migration.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _make_alembic_config(database_url)

    command.upgrade(config, "001")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO fields (
                    id,
                    name,
                    location,
                    area_hectares,
                    slope_percent,
                    irrigation_available,
                    drainage_quality,
                    created_at,
                    updated_at
                ) VALUES (
                    1,
                    :name,
                    :location,
                    :area_hectares,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL
                )
                """
            ),
            {
                "name": "Legacy Field",
                "location": "Legacy Region",
                "area_hectares": 12.5,
            },
        )

    command.upgrade(config, "head")

    upgraded_columns = {column["name"] for column in inspect(engine).get_columns("fields")}
    assert "location_name" in upgraded_columns
    assert "location" not in upgraded_columns
    assert "latitude" in upgraded_columns
    assert "infrastructure_score" in upgraded_columns

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    location_name,
                    slope_percent,
                    irrigation_available,
                    drainage_quality,
                    infrastructure_score,
                    created_at,
                    updated_at
                FROM fields
                WHERE id = 1
                """
            )
        ).mappings().one()

    assert row["location_name"] == "Legacy Region"
    assert row["slope_percent"] == 0.0
    assert row["irrigation_available"] in (0, False)
    assert row["drainage_quality"] == "moderate"
    assert row["infrastructure_score"] == 0
    assert row["created_at"] is not None
    assert row["updated_at"] is not None

    command.downgrade(config, "001")

    downgraded_columns = {column["name"] for column in inspect(engine).get_columns("fields")}
    assert "location" in downgraded_columns
    assert "location_name" not in downgraded_columns
    assert "latitude" not in downgraded_columns
    assert "infrastructure_score" not in downgraded_columns
