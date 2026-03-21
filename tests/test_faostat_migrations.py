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


def test_external_crop_statistics_migration_upgrade_and_downgrade(tmp_path):
    database_path = tmp_path / "external_crop_statistics.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _make_alembic_config(database_url)

    command.upgrade(config, "012")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "external_crop_statistics" in inspector.get_table_names()

    columns = {column["name"] for column in inspector.get_columns("external_crop_statistics")}
    assert {
        "id",
        "source_name",
        "country",
        "year",
        "crop_name",
        "statistic_type",
        "statistic_value",
        "unit",
        "created_at",
    }.issubset(columns)

    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("external_crop_statistics")
    }
    assert "uq_external_crop_statistics_country_year_crop_stat" in unique_constraints

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO external_crop_statistics (
                    id,
                    source_name,
                    country,
                    year,
                    crop_name,
                    statistic_type,
                    statistic_value,
                    unit,
                    created_at
                ) VALUES (
                    1,
                    'FAOSTAT',
                    'United States of America',
                    2023,
                    'Maize',
                    'production',
                    389694720.0,
                    't',
                    CURRENT_TIMESTAMP
                )
                """
            )
        )

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT country, year, crop_name, statistic_type, statistic_value
                FROM external_crop_statistics
                WHERE id = 1
                """
            )
        ).mappings().one()

    assert row["country"] == "United States of America"
    assert row["year"] == 2023
    assert row["crop_name"] == "Maize"
    assert row["statistic_type"] == "production"
    assert row["statistic_value"] == 389694720.0

    command.downgrade(config, "011")

    assert "external_crop_statistics" not in inspect(engine).get_table_names()
