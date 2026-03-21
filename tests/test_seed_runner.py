from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, Float, MetaData, String, Table, Text, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.seeds.runner import run_seed


def _build_live_like_schema(metadata: MetaData) -> None:
    Table(
        "fields",
        metadata,
        Column("id", String, primary_key=True),
        Column("name", Text, nullable=False),
        Column("location_name", Text),
        Column("latitude", Float),
        Column("longitude", Float),
        Column("area_hectares", Float),
        Column("elevation_meters", Float),
        Column("slope_percent", Float),
        Column("aspect", Text),
        Column("irrigation_available", Boolean, nullable=False),
        Column("water_source_type", Text),
        Column("infrastructure_score", Float),
        Column("notes", Text),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )
    Table(
        "soil_tests",
        metadata,
        Column("id", String, primary_key=True),
        Column("field_id", String, nullable=False),
        Column("sample_date", Date, nullable=False),
        Column("ph", Float),
        Column("ec", Float),
        Column("organic_matter_percent", Float),
        Column("nitrogen_ppm", Float),
        Column("phosphorus_ppm", Float),
        Column("potassium_ppm", Float),
        Column("calcium_ppm", Float),
        Column("magnesium_ppm", Float),
        Column("texture_class", Text),
        Column("drainage_class", Text),
        Column("depth_cm", Float),
        Column("water_holding_capacity", Float),
        Column("notes", Text),
        Column("created_at", DateTime, nullable=False),
    )
    Table(
        "crop_profiles",
        metadata,
        Column("id", String, primary_key=True),
        Column("crop_name", Text, nullable=False),
        Column("scientific_name", Text),
        Column("ideal_ph_min", Float),
        Column("ideal_ph_max", Float),
        Column("tolerable_ph_min", Float),
        Column("tolerable_ph_max", Float),
        Column("water_requirement_level", Text),
        Column("drainage_requirement", Text),
        Column("frost_sensitivity", Text),
        Column("heat_sensitivity", Text),
        Column("salinity_tolerance", Text),
        Column("rooting_depth_cm", Float),
        Column("slope_tolerance", Text),
        Column("organic_matter_preference", Text),
        Column("notes", Text),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )
    Table(
        "crop_economic_profiles",
        metadata,
        Column("id", String, primary_key=True),
        Column("crop_name", Text, nullable=False),
        Column("average_market_price_per_unit", Float, nullable=False),
        Column("price_unit", Text, nullable=False),
        Column("base_cost_per_hectare", Float, nullable=False),
        Column("irrigation_cost_factor", Float, nullable=False),
        Column("fertilizer_cost_factor", Float, nullable=False),
        Column("labor_cost_factor", Float, nullable=False),
        Column("risk_cost_factor", Float, nullable=False),
        Column("region", Text),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )
    Table(
        "weather_history",
        metadata,
        Column("id", String, primary_key=True),
        Column("field_id", String),
        Column("weather_date", Date, nullable=False),
        Column("min_temp", Float),
        Column("max_temp", Float),
        Column("avg_temp", Float),
        Column("rainfall_mm", Float),
        Column("humidity", Float),
        Column("wind_speed", Float),
        Column("solar_radiation", Float),
        Column("et0", Float),
        Column("created_at", DateTime, nullable=False),
    )


def _count(session: Session, table_name: str) -> int:
    return session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()


def test_run_seed_populates_expected_demo_counts():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    _build_live_like_schema(metadata)
    metadata.create_all(engine)
    SessionTesting = sessionmaker(bind=engine)

    with SessionTesting() as session:
        summary = run_seed(session)
        session.commit()

        assert summary.crops_created == 5
        assert summary.economic_profiles_created == 5
        assert summary.fields_created == 10
        assert summary.soil_tests_created == 10
        assert summary.weather_rows_created == 280
        assert _count(session, "crop_profiles") == 5
        assert _count(session, "crop_economic_profiles") == 5
        assert _count(session, "fields") == 10
        assert _count(session, "soil_tests") == 10
        assert _count(session, "weather_history") == 280


def test_run_seed_is_idempotent_for_seed_managed_rows():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    _build_live_like_schema(metadata)
    metadata.create_all(engine)
    SessionTesting = sessionmaker(bind=engine)

    with SessionTesting() as session:
        first_summary = run_seed(session)
        session.commit()
        second_summary = run_seed(session)
        session.commit()

        assert first_summary.crops_created == 5
        assert first_summary.economic_profiles_created == 5
        assert second_summary.crops_updated == 5
        assert second_summary.economic_profiles_updated == 5
        assert second_summary.fields_updated == 10
        assert second_summary.soil_tests_updated == 10
        assert second_summary.weather_rows_updated == 280
        assert _count(session, "crop_profiles") == 5
        assert _count(session, "crop_economic_profiles") == 5
        assert _count(session, "fields") == 10
        assert _count(session, "soil_tests") == 10
        assert _count(session, "weather_history") == 280
