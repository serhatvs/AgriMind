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


def test_feedback_loop_migration_adds_closed_loop_tables(tmp_path):
    """Head migration should add feedback tables and their key constraints."""

    database_path = tmp_path / "feedback_loop_migration.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _make_alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)

    assert {
        "recommendation_runs",
        "recommendation_results",
        "user_decisions",
        "season_results",
    }.issubset(set(inspector.get_table_names()))

    recommendation_results_pk = inspector.get_pk_constraint("recommendation_results")
    assert recommendation_results_pk["constrained_columns"] == ["recommendation_run_id", "field_id"]
    recommendation_results_uniques = inspector.get_unique_constraints("recommendation_results")
    assert any(
        constraint["column_names"] == ["recommendation_run_id", "rank"]
        for constraint in recommendation_results_uniques
    )

    user_decisions_pk = inspector.get_pk_constraint("user_decisions")
    season_results_pk = inspector.get_pk_constraint("season_results")
    assert user_decisions_pk["constrained_columns"] == ["recommendation_run_id"]
    assert season_results_pk["constrained_columns"] == ["recommendation_run_id"]

    recommendation_runs_fks = inspector.get_foreign_keys("recommendation_runs")
    recommendation_results_fks = inspector.get_foreign_keys("recommendation_results")
    user_decisions_fks = inspector.get_foreign_keys("user_decisions")
    season_results_fks = inspector.get_foreign_keys("season_results")

    assert any(fk["referred_table"] == "crop_profiles" and fk["referred_columns"] == ["id"] for fk in recommendation_runs_fks)
    assert any(fk["referred_table"] == "recommendation_runs" for fk in recommendation_results_fks)
    assert any(fk["referred_table"] == "fields" for fk in recommendation_results_fks)
    assert any(fk["referred_table"] == "recommendation_runs" for fk in user_decisions_fks)
    assert any(fk["referred_table"] == "fields" for fk in user_decisions_fks)
    assert any(fk["referred_table"] == "recommendation_runs" for fk in season_results_fks)
    assert any(fk["referred_table"] == "fields" for fk in season_results_fks)
    assert any(fk["referred_table"] == "crop_profiles" for fk in season_results_fks)

    season_columns = {column["name"] for column in inspector.get_columns("season_results")}
    assert {"recommendation_run_id", "field_id", "crop_id", "yield", "actual_cost", "notes"} == season_columns
