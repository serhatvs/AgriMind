"""Build training datasets for the yield prediction MVP."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from random import Random
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.contracts.yield_prediction import build_yield_prediction_input_from_entities
from app.config import settings
from app.db.reflection import reflect_tables, table_has_columns, tables_exist
from app.ml.mock_training_data import build_mock_crop_profiles, generate_mock_training_samples
from app.ml.yield_pipeline import YieldFeatureBundle, YieldTrainingSample
from app.services.weather_service import WeatherService


@dataclass(slots=True)
class YieldTrainingDatasetBundle:
    """Prepared supervised dataset plus provenance metadata."""

    samples: list[YieldTrainingSample]
    source_name: str
    real_sample_count: int
    synthetic_sample_count: int


def build_yield_training_dataset(
    db: Session | None,
    *,
    target_sample_count: int | None = None,
    random_seed: int | None = None,
    min_real_samples: int | None = None,
) -> YieldTrainingDatasetBundle:
    """Build the yield training dataset from real labels when available, else bootstrap data."""

    resolved_target = target_sample_count or settings.YIELD_TRAINING_SAMPLE_COUNT
    resolved_seed = random_seed or settings.YIELD_TRAINING_RANDOM_SEED
    resolved_min_real = min_real_samples or settings.YIELD_MIN_REAL_TRAINING_SAMPLES

    real_samples = _load_real_training_samples(db) if db is not None else []
    synthetic_needed = max(resolved_target - len(real_samples), 0)
    use_only_synthetic = len(real_samples) < resolved_min_real

    if use_only_synthetic:
        real_samples = []
        synthetic_needed = resolved_target

    synthetic_samples = generate_mock_training_samples(
        crop_profiles=build_mock_crop_profiles(),
        sample_count=synthetic_needed,
        random_seed=resolved_seed,
    )

    samples = [*real_samples, *synthetic_samples]
    Random(resolved_seed).shuffle(samples)

    if real_samples and synthetic_samples:
        source_name = "season_results_proxy+synthetic_bootstrap"
    elif real_samples:
        source_name = "season_results_proxy"
    else:
        source_name = "synthetic_bootstrap"

    return YieldTrainingDatasetBundle(
        samples=samples,
        source_name=source_name,
        real_sample_count=len(real_samples),
        synthetic_sample_count=len(synthetic_samples),
    )


def _load_real_training_samples(db: Session) -> list[YieldTrainingSample]:
    if not tables_exist(db, "season_results", "fields", "crop_profiles"):
        return []

    reflected = reflect_tables(db, "season_results", "fields", "crop_profiles")
    season_results_table = reflected["season_results"]
    fields_table = reflected["fields"]
    crop_profiles_table = reflected["crop_profiles"]
    season_yield_column = _season_yield_column_name(db)
    if season_yield_column is None:
        return []

    season_rows = db.execute(select(season_results_table)).mappings().all()
    if not season_rows:
        return []

    field_rows = {
        row["id"]: row
        for row in db.execute(select(fields_table)).mappings().all()
    }
    crop_rows = {
        row["id"]: row
        for row in db.execute(select(crop_profiles_table)).mappings().all()
    }
    soil_rows = _load_latest_soils(db)
    weather_service = WeatherService(db)

    samples: list[YieldTrainingSample] = []
    for season_row in season_rows:
        yield_value = _coerce_float(season_row.get(season_yield_column))
        if yield_value is None or yield_value <= 0:
            continue

        field_id = season_row.get("field_id")
        crop_id = season_row.get("crop_id")
        field_row = field_rows.get(field_id)
        crop_row = crop_rows.get(crop_id)
        if field_row is None or crop_row is None:
            continue

        field_proxy = _build_field_proxy(field_row, soil_rows.get(field_id))
        crop_proxy = _build_crop_proxy(crop_row)
        soil_proxy = _build_soil_proxy(soil_rows.get(field_id))
        climate_summary = weather_service.get_climate_summary(field_id)

        input_data = build_yield_prediction_input_from_entities(
            field_proxy,
            crop_proxy,
            soil_test=soil_proxy,
            climate_summary=climate_summary,
        )
        samples.append(
            YieldTrainingSample(
                features=YieldFeatureBundle.from_prediction_input(input_data),
                yield_per_hectare=yield_value,
            )
        )
    return samples


def _season_yield_column_name(db: Session) -> str | None:
    if table_has_columns(db, "season_results", "yield"):
        return "yield"
    if table_has_columns(db, "season_results", "yield_amount"):
        return "yield_amount"
    return None


def _load_latest_soils(db: Session) -> dict[int | str | UUID, Mapping[str, Any]]:
    if not tables_exist(db, "soil_tests"):
        return {}
    soil_tests_table = reflect_tables(db, "soil_tests")["soil_tests"]
    query = select(soil_tests_table)
    if "sample_date" in soil_tests_table.c and "created_at" in soil_tests_table.c:
        query = query.order_by(
            soil_tests_table.c.field_id.asc(),
            soil_tests_table.c.sample_date.desc(),
            soil_tests_table.c.created_at.desc(),
        )
    rows = db.execute(query).mappings().all()
    latest_by_field_id: dict[int | str | UUID, Mapping[str, Any]] = {}
    for row in rows:
        field_id = row["field_id"]
        if field_id not in latest_by_field_id:
            latest_by_field_id[field_id] = row
    return latest_by_field_id


def _build_field_proxy(field_row: Mapping[str, Any], soil_row: Mapping[str, Any] | None) -> SimpleNamespace:
    drainage_quality = (
        field_row.get("drainage_quality")
        or (soil_row.get("drainage_class") if soil_row is not None else None)
        or "moderate"
    )
    return SimpleNamespace(
        id=field_row.get("id"),
        name=field_row.get("name") or "Field",
        area_hectares=_coerce_float(field_row.get("area_hectares")) or 0.0,
        slope_percent=_coerce_float(field_row.get("slope_percent")) or 0.0,
        irrigation_available=bool(field_row.get("irrigation_available")),
        drainage_quality=drainage_quality,
        elevation_meters=_coerce_float(field_row.get("elevation_meters")),
        infrastructure_score=_coerce_int(field_row.get("infrastructure_score")),
        water_source_type=field_row.get("water_source_type"),
        aspect=field_row.get("aspect"),
    )


def _build_crop_proxy(crop_row: Mapping[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=crop_row.get("id"),
        crop_name=crop_row.get("crop_name") or "Unknown crop",
        ideal_ph_min=_coerce_float(crop_row.get("ideal_ph_min")),
        ideal_ph_max=_coerce_float(crop_row.get("ideal_ph_max")),
        water_requirement_level=crop_row.get("water_requirement_level") or "medium",
        drainage_requirement=crop_row.get("drainage_requirement") or "moderate",
        frost_sensitivity=crop_row.get("frost_sensitivity") or "medium",
        heat_sensitivity=crop_row.get("heat_sensitivity") or "medium",
        salinity_tolerance=crop_row.get("salinity_tolerance"),
        rooting_depth_cm=_coerce_float(crop_row.get("rooting_depth_cm")),
        slope_tolerance=_coerce_float(crop_row.get("slope_tolerance")),
        optimal_temp_min_c=_coerce_float(crop_row.get("optimal_temp_min_c")),
        optimal_temp_max_c=_coerce_float(crop_row.get("optimal_temp_max_c")),
        rainfall_requirement_mm=_coerce_float(crop_row.get("rainfall_requirement_mm")),
        frost_tolerance_days=_coerce_int(crop_row.get("frost_tolerance_days")),
        heat_tolerance_days=_coerce_int(crop_row.get("heat_tolerance_days")),
        organic_matter_preference=crop_row.get("organic_matter_preference"),
    )


def _build_soil_proxy(soil_row: Mapping[str, Any] | None) -> SimpleNamespace | None:
    if soil_row is None:
        return None
    return SimpleNamespace(
        id=soil_row.get("id"),
        field_id=soil_row.get("field_id"),
        ph=_coerce_float(soil_row.get("ph")),
        ec=_coerce_float(soil_row.get("ec")),
        organic_matter_percent=_coerce_float(soil_row.get("organic_matter_percent")),
        nitrogen_ppm=_coerce_float(soil_row.get("nitrogen_ppm")),
        phosphorus_ppm=_coerce_float(soil_row.get("phosphorus_ppm")),
        potassium_ppm=_coerce_float(soil_row.get("potassium_ppm")),
        calcium_ppm=_coerce_float(soil_row.get("calcium_ppm")),
        magnesium_ppm=_coerce_float(soil_row.get("magnesium_ppm")),
        texture_class=soil_row.get("texture_class"),
        drainage_class=soil_row.get("drainage_class"),
        depth_cm=_coerce_float(soil_row.get("depth_cm")),
        water_holding_capacity=_coerce_float(soil_row.get("water_holding_capacity")),
        sample_date=soil_row.get("sample_date"),
    )


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
