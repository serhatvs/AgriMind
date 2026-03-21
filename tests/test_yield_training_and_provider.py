import json
from pathlib import Path

from app.ai.contracts.yield_prediction import (
    YieldClimateSummary,
    YieldCropSummary,
    YieldFieldSummary,
    YieldPredictionInput,
    YieldSoilSummary,
)
from app.ai.providers.ml.xgboost_yield import XGBoostYieldPredictionProvider, _PIPELINE_CACHE
from app.ai.training import train_yield_model
from app.ml.mock_training_data import generate_mock_training_samples
from app.ml.yield_pipeline import YieldPredictionPipeline


def _sample_prediction_input() -> YieldPredictionInput:
    return YieldPredictionInput(
        field=YieldFieldSummary(
            field_id=101,
            name="Training Field",
            area_hectares=14.0,
            slope_percent=2.5,
            irrigation_available=True,
            drainage_quality="good",
            elevation_meters=320.0,
            infrastructure_score=74,
            water_source_type="well",
            aspect="south",
        ),
        soil=YieldSoilSummary(
            soil_test_id=9,
            ph=6.4,
            ec=1.1,
            organic_matter_percent=3.8,
            nitrogen_ppm=62.0,
            phosphorus_ppm=31.0,
            potassium_ppm=210.0,
            calcium_ppm=1680.0,
            magnesium_ppm=215.0,
            depth_cm=130.0,
            water_holding_capacity=22.0,
            texture_class="loamy",
            drainage_class="good",
            sample_date=None,
        ),
        crop=YieldCropSummary(
            crop_id=5,
            crop_name="Corn",
            water_requirement_level="high",
            drainage_requirement="moderate",
            salinity_tolerance="moderate",
            rooting_depth_cm=150.0,
            slope_tolerance=8.0,
            optimal_temp_min_c=18.0,
            optimal_temp_max_c=30.0,
            rainfall_requirement_mm=550.0,
            frost_tolerance_days=4,
            heat_tolerance_days=18,
            organic_matter_preference="moderate",
            ideal_ph_min=6.0,
            ideal_ph_max=6.8,
            frost_sensitivity="high",
            heat_sensitivity="medium",
        ),
        climate=YieldClimateSummary(
            avg_temp=22.0,
            min_observed_temp=11.0,
            max_observed_temp=31.0,
            total_rainfall=520.0,
            frost_days=1,
            heat_days=4,
            avg_humidity=58.0,
            avg_wind_speed=3.6,
            avg_solar_radiation=17.8,
            weather_record_count=30,
        ),
    )


def test_xgboost_provider_falls_back_cleanly_when_model_artifact_is_missing(tmp_path):
    model_dir = tmp_path / "missing_model"
    _PIPELINE_CACHE.pop(str(model_dir.resolve()), None)
    provider = XGBoostYieldPredictionProvider(db=None, model_dir=model_dir)

    prediction = provider.predict(_sample_prediction_input())

    assert prediction.predicted_yield > 0
    assert prediction.provider_name == "deterministic_yield_prediction"
    assert prediction.debug_info is not None
    assert prediction.debug_info["requested_provider"] == "xgboost_yield_prediction"
    assert "fallback_reason" in prediction.debug_info


def test_xgboost_provider_loads_saved_model_and_predicts(tmp_path):
    model_dir = tmp_path / "yield_model"
    samples = generate_mock_training_samples(sample_count=120, random_seed=123)
    pipeline = YieldPredictionPipeline().fit(
        samples,
        random_seed=123,
        training_source="synthetic_bootstrap",
    )
    pipeline.save(model_dir)
    _PIPELINE_CACHE.pop(str(model_dir.resolve()), None)

    provider = XGBoostYieldPredictionProvider(db=None, model_dir=model_dir)
    prediction = provider.predict(_sample_prediction_input())

    assert prediction.predicted_yield > 0
    assert prediction.provider_name == "xgboost_yield_prediction"
    assert prediction.training_source == "synthetic_bootstrap"
    assert prediction.debug_info is not None
    assert prediction.debug_info["metrics"] is not None


def test_train_yield_model_cli_trains_and_saves_artifacts(db, tmp_path, monkeypatch, capsys):
    model_dir = tmp_path / "cli_yield_model"

    class _SessionContext:
        def __enter__(self):
            return db

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(train_yield_model, "SessionLocal", lambda: _SessionContext())

    exit_code = train_yield_model.main(
        [
            "--model-dir",
            str(model_dir),
            "--sample-count",
            "40",
            "--random-seed",
            "321",
            "--min-real-samples",
            "1",
            "--force",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["provider_name"] == "xgboost_yield_prediction"
    assert payload["provider_version"]
    assert payload["training_source"]
    assert Path(model_dir, "yield_model.json").exists()
    assert Path(model_dir, "yield_model_metadata.json").exists()
