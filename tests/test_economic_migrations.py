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


def test_crop_economics_migration_upgrade_and_downgrade(tmp_path):
    database_path = tmp_path / "crop_economics_migration.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _make_alembic_config(database_url)

    command.upgrade(config, "006")

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
                    150.0,
                    8.0,
                    'moderate',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            )
        )

    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert "crop_prices" in inspector.get_table_names()
    assert "input_costs" in inspector.get_table_names()
    assert "crop_economic_profiles" in inspector.get_table_names()

    crop_price_columns = {column["name"] for column in inspector.get_columns("crop_prices")}
    assert {"id", "crop_id", "price_per_ton"}.issubset(crop_price_columns)

    input_cost_columns = {column["name"] for column in inspector.get_columns("input_costs")}
    assert {"id", "crop_id", "fertilizer_cost", "water_cost", "labor_cost"}.issubset(input_cost_columns)

    economic_profile_columns = {column["name"] for column in inspector.get_columns("crop_economic_profiles")}
    assert {
        "id",
        "crop_name",
        "average_market_price_per_unit",
        "price_unit",
        "base_cost_per_hectare",
        "irrigation_cost_factor",
        "fertilizer_cost_factor",
        "labor_cost_factor",
        "risk_cost_factor",
        "region",
    }.issubset(economic_profile_columns)

    crop_price_uniques = {constraint["name"] for constraint in inspector.get_unique_constraints("crop_prices")}
    input_cost_uniques = {constraint["name"] for constraint in inspector.get_unique_constraints("input_costs")}
    assert "uq_crop_prices_crop_id" in crop_price_uniques
    assert "uq_input_costs_crop_id" in input_cost_uniques

    crop_price_checks = {constraint["name"] for constraint in inspector.get_check_constraints("crop_prices")}
    input_cost_checks = {constraint["name"] for constraint in inspector.get_check_constraints("input_costs")}
    economic_profile_checks = {
        constraint["name"] for constraint in inspector.get_check_constraints("crop_economic_profiles")
    }
    assert "ck_crop_prices_price_per_ton_positive" in crop_price_checks
    assert "ck_input_costs_fertilizer_cost_non_negative" in input_cost_checks
    assert "ck_crop_economic_profiles_average_market_price_positive" in economic_profile_checks

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO crop_prices (id, crop_id, price_per_ton)
                VALUES (1, 1, 210.0)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO input_costs (id, crop_id, fertilizer_cost, water_cost, labor_cost)
                VALUES (1, 1, 240.0, 165.0, 130.0)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO crop_economic_profiles (
                    id,
                    crop_name,
                    average_market_price_per_unit,
                    price_unit,
                    base_cost_per_hectare,
                    irrigation_cost_factor,
                    fertilizer_cost_factor,
                    labor_cost_factor,
                    risk_cost_factor,
                    region,
                    created_at,
                    updated_at
                ) VALUES (
                    1,
                    'Corn',
                    210.0,
                    'ton',
                    360.0,
                    0.18,
                    0.22,
                    0.11,
                    0.06,
                    NULL,
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
                SELECT cp.price_per_ton, ic.water_cost, cep.average_market_price_per_unit
                FROM crop_prices cp
                JOIN input_costs ic ON ic.crop_id = cp.crop_id
                JOIN crop_economic_profiles cep ON LOWER(cep.crop_name) = 'corn'
                WHERE cp.crop_id = 1
                """
            )
        ).mappings().one()

    assert row["price_per_ton"] == 210.0
    assert row["water_cost"] == 165.0
    assert row["average_market_price_per_unit"] == 210.0

    command.downgrade(config, "006")

    downgraded_tables = inspect(engine).get_table_names()
    assert "crop_prices" not in downgraded_tables
    assert "input_costs" not in downgraded_tables
    assert "crop_economic_profiles" not in downgraded_tables
