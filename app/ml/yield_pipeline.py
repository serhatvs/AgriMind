"""Reusable yield-prediction pipeline for field and crop combinations.

Example:
```python
from app.ml.mock_training_data import generate_mock_training_samples
from app.ml.yield_pipeline import YieldPredictionPipeline

samples = generate_mock_training_samples(sample_count=300)
pipeline = YieldPredictionPipeline().fit(samples)

bundle = samples[0].features
prediction = pipeline.predict(bundle)

print(prediction.predicted_yield)
print(prediction.yield_range_min, prediction.yield_range_max)
print(prediction.confidence)
```
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import random
from pathlib import Path
from typing import Any

from app.ai.contracts.metadata import AITraceMetadata
from app.ai.contracts.yield_prediction import (
    YieldPredictionInput,
    YieldPredictionOutput,
    build_yield_prediction_input_from_entities,
)
from app.config import settings
from app.models.crop_profile import CropProfile
from app.models.field import Field
from app.models.soil_test import SoilTest
from app.schemas.weather_history import ClimateSummary

try:
    from xgboost import Booster, DMatrix, train as xgb_train
except ImportError:  # pragma: no cover - exercised in environments without xgboost.
    Booster = None
    DMatrix = None
    xgb_train = None


NUMERIC_FEATURES = (
    "soil_ph",
    "soil_ec",
    "organic_matter_percent",
    "nitrogen_ppm",
    "phosphorus_ppm",
    "potassium_ppm",
    "calcium_ppm",
    "magnesium_ppm",
    "soil_depth_cm",
    "water_holding_capacity",
    "slope_percent",
    "area_hectares",
    "elevation_meters",
    "infrastructure_score",
    "crop_ideal_ph_min",
    "crop_ideal_ph_max",
    "crop_rooting_depth_cm",
    "crop_slope_tolerance",
    "crop_optimal_temp_min_c",
    "crop_optimal_temp_max_c",
    "crop_rainfall_requirement_mm",
    "crop_frost_tolerance_days",
    "crop_heat_tolerance_days",
    "climate_avg_temp",
    "climate_min_observed_temp",
    "climate_max_observed_temp",
    "climate_total_rainfall",
    "climate_frost_days",
    "climate_heat_days",
    "climate_avg_humidity",
    "climate_avg_wind_speed",
    "climate_avg_solar_radiation",
    "climate_weather_record_count",
)

CATEGORICAL_FEATURES = (
    "crop_name",
    "texture_class",
    "soil_drainage_class",
    "field_drainage_quality",
    "water_source_type",
    "aspect",
    "crop_water_requirement",
    "crop_drainage_requirement",
    "crop_frost_sensitivity",
    "crop_heat_sensitivity",
    "crop_salinity_tolerance",
    "crop_organic_matter_preference",
)

BOOLEAN_FEATURES = (
    "irrigation_available",
    "has_soil_test",
    "has_climate_summary",
)

NUMERIC_DEFAULTS = {
    "soil_ph": 6.5,
    "soil_ec": 1.2,
    "organic_matter_percent": 3.0,
    "nitrogen_ppm": 40.0,
    "phosphorus_ppm": 25.0,
    "potassium_ppm": 180.0,
    "calcium_ppm": 1650.0,
    "magnesium_ppm": 220.0,
    "soil_depth_cm": 110.0,
    "water_holding_capacity": 20.0,
    "slope_percent": 4.0,
    "area_hectares": 12.0,
    "elevation_meters": 250.0,
    "infrastructure_score": 60.0,
    "crop_ideal_ph_min": 6.0,
    "crop_ideal_ph_max": 7.0,
    "crop_rooting_depth_cm": 110.0,
    "crop_slope_tolerance": 8.0,
    "crop_optimal_temp_min_c": 16.0,
    "crop_optimal_temp_max_c": 26.0,
    "crop_rainfall_requirement_mm": 500.0,
    "crop_frost_tolerance_days": 12.0,
    "crop_heat_tolerance_days": 10.0,
    "climate_avg_temp": 20.0,
    "climate_min_observed_temp": 10.0,
    "climate_max_observed_temp": 28.0,
    "climate_total_rainfall": 480.0,
    "climate_frost_days": 5.0,
    "climate_heat_days": 6.0,
    "climate_avg_humidity": 58.0,
    "climate_avg_wind_speed": 4.0,
    "climate_avg_solar_radiation": 17.0,
    "climate_weather_record_count": 30.0,
}

MISSING_CATEGORY = "__missing__"
MODEL_FILENAME = "yield_model.json"
METADATA_FILENAME = "yield_model_metadata.json"
MODEL_VERSION = settings.YIELD_MODEL_VERSION


@dataclass(slots=True)
class YieldFeatureBundle:
    """Raw prediction features assembled from domain entities."""

    crop_name: str
    soil_ph: float | None
    soil_ec: float | None
    organic_matter_percent: float | None
    nitrogen_ppm: float | None
    phosphorus_ppm: float | None
    potassium_ppm: float | None
    calcium_ppm: float | None
    magnesium_ppm: float | None
    soil_depth_cm: float | None
    water_holding_capacity: float | None
    texture_class: str | None
    soil_drainage_class: str | None
    slope_percent: float
    irrigation_available: bool
    area_hectares: float
    elevation_meters: float | None
    field_drainage_quality: str
    infrastructure_score: int | None
    water_source_type: str | None
    aspect: str | None
    crop_ideal_ph_min: float | None
    crop_ideal_ph_max: float | None
    crop_water_requirement: str
    crop_drainage_requirement: str
    crop_frost_sensitivity: str | None
    crop_heat_sensitivity: str | None
    crop_salinity_tolerance: str | None
    crop_rooting_depth_cm: float | None
    crop_slope_tolerance: float | None
    crop_optimal_temp_min_c: float | None
    crop_optimal_temp_max_c: float | None
    crop_rainfall_requirement_mm: float | None
    crop_frost_tolerance_days: int | None
    crop_heat_tolerance_days: int | None
    crop_organic_matter_preference: str | None
    climate_avg_temp: float | None
    climate_min_observed_temp: float | None
    climate_max_observed_temp: float | None
    climate_total_rainfall: float | None
    climate_frost_days: int | None
    climate_heat_days: int | None
    climate_avg_humidity: float | None
    climate_avg_wind_speed: float | None
    climate_avg_solar_radiation: float | None
    climate_weather_record_count: int | None
    has_soil_test: bool = True
    has_climate_summary: bool = True

    @classmethod
    def from_prediction_input(
        cls,
        input_data: YieldPredictionInput,
    ) -> "YieldFeatureBundle":
        """Build a feature bundle from the canonical yield-prediction input."""

        soil = input_data.soil
        climate = input_data.climate
        return cls(
            crop_name=input_data.crop.crop_name,
            soil_ph=soil.ph if soil is not None else None,
            soil_ec=soil.ec if soil is not None else None,
            organic_matter_percent=soil.organic_matter_percent if soil is not None else None,
            nitrogen_ppm=soil.nitrogen_ppm if soil is not None else None,
            phosphorus_ppm=soil.phosphorus_ppm if soil is not None else None,
            potassium_ppm=soil.potassium_ppm if soil is not None else None,
            calcium_ppm=soil.calcium_ppm if soil is not None else None,
            magnesium_ppm=soil.magnesium_ppm if soil is not None else None,
            soil_depth_cm=soil.depth_cm if soil is not None else None,
            water_holding_capacity=soil.water_holding_capacity if soil is not None else None,
            texture_class=soil.texture_class if soil is not None else None,
            soil_drainage_class=soil.drainage_class if soil is not None else None,
            slope_percent=input_data.field.slope_percent,
            irrigation_available=input_data.field.irrigation_available,
            area_hectares=input_data.field.area_hectares,
            elevation_meters=input_data.field.elevation_meters,
            field_drainage_quality=input_data.field.drainage_quality,
            infrastructure_score=input_data.field.infrastructure_score,
            water_source_type=input_data.field.water_source_type,
            aspect=input_data.field.aspect,
            crop_ideal_ph_min=input_data.crop.ideal_ph_min,
            crop_ideal_ph_max=input_data.crop.ideal_ph_max,
            crop_water_requirement=input_data.crop.water_requirement_level,
            crop_drainage_requirement=input_data.crop.drainage_requirement,
            crop_frost_sensitivity=input_data.crop.frost_sensitivity,
            crop_heat_sensitivity=input_data.crop.heat_sensitivity,
            crop_salinity_tolerance=input_data.crop.salinity_tolerance,
            crop_rooting_depth_cm=input_data.crop.rooting_depth_cm,
            crop_slope_tolerance=input_data.crop.slope_tolerance,
            crop_optimal_temp_min_c=input_data.crop.optimal_temp_min_c,
            crop_optimal_temp_max_c=input_data.crop.optimal_temp_max_c,
            crop_rainfall_requirement_mm=input_data.crop.rainfall_requirement_mm,
            crop_frost_tolerance_days=input_data.crop.frost_tolerance_days,
            crop_heat_tolerance_days=input_data.crop.heat_tolerance_days,
            crop_organic_matter_preference=input_data.crop.organic_matter_preference,
            climate_avg_temp=climate.avg_temp if climate is not None else None,
            climate_min_observed_temp=climate.min_observed_temp if climate is not None else None,
            climate_max_observed_temp=climate.max_observed_temp if climate is not None else None,
            climate_total_rainfall=climate.total_rainfall if climate is not None else None,
            climate_frost_days=climate.frost_days if climate is not None else None,
            climate_heat_days=climate.heat_days if climate is not None else None,
            climate_avg_humidity=climate.avg_humidity if climate is not None else None,
            climate_avg_wind_speed=climate.avg_wind_speed if climate is not None else None,
            climate_avg_solar_radiation=climate.avg_solar_radiation if climate is not None else None,
            climate_weather_record_count=climate.weather_record_count if climate is not None else None,
            has_soil_test=soil is not None,
            has_climate_summary=climate is not None,
        )

    @classmethod
    def from_entities(
        cls,
        field_obj: Field,
        crop: CropProfile,
        soil_test: SoilTest | None = None,
        climate_summary: ClimateSummary | None = None,
    ) -> "YieldFeatureBundle":
        """Build a feature bundle from the current domain models."""

        return cls.from_prediction_input(
            build_yield_prediction_input_from_entities(
                field_obj,
                crop,
                soil_test=soil_test,
                climate_summary=climate_summary,
            )
        )

    def feature_snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the assembled features."""

        return {
            name: getattr(self, name)
            for name in (*NUMERIC_FEATURES, *CATEGORICAL_FEATURES, *BOOLEAN_FEATURES)
        }

    def missing_feature_ratio(self) -> float:
        """Estimate how incomplete the assembled raw feature set is."""

        values = [
            getattr(self, name)
            for name in (
                "soil_ph",
                "soil_ec",
                "organic_matter_percent",
                "nitrogen_ppm",
                "phosphorus_ppm",
                "potassium_ppm",
                "calcium_ppm",
                "magnesium_ppm",
                "soil_depth_cm",
                "water_holding_capacity",
                "texture_class",
                "soil_drainage_class",
                "elevation_meters",
                "water_source_type",
                "aspect",
                "crop_salinity_tolerance",
                "crop_ideal_ph_min",
                "crop_ideal_ph_max",
                "crop_frost_sensitivity",
                "crop_heat_sensitivity",
                "crop_rooting_depth_cm",
                "crop_slope_tolerance",
                "crop_optimal_temp_min_c",
                "crop_optimal_temp_max_c",
                "crop_rainfall_requirement_mm",
                "crop_frost_tolerance_days",
                "crop_heat_tolerance_days",
                "crop_organic_matter_preference",
                "climate_avg_temp",
                "climate_min_observed_temp",
                "climate_max_observed_temp",
                "climate_total_rainfall",
                "climate_frost_days",
                "climate_heat_days",
                "climate_avg_humidity",
                "climate_avg_wind_speed",
                "climate_avg_solar_radiation",
                "climate_weather_record_count",
            )
        ]
        missing = sum(value is None for value in values)
        return missing / len(values)


@dataclass(slots=True)
class YieldTrainingSample:
    """Supervised training sample for the yield model."""

    features: YieldFeatureBundle
    yield_per_hectare: float


@dataclass(slots=True)
class YieldDataset:
    """Prepared dataset consumed by the learning algorithm."""

    X: list[list[float]]
    y: list[float]
    feature_names: list[str]


@dataclass(slots=True)
class YieldModelMetrics:
    """Model-evaluation metrics persisted with the trained model."""

    train_size: int
    test_size: int
    rmse: float
    mae: float


class YieldFeatureEncoder:
    """Encodes mixed agronomic features into a numeric matrix."""

    def __init__(self, category_levels: dict[str, list[str]] | None = None) -> None:
        self.category_levels = category_levels or {}

    def fit(self, bundles: list[YieldFeatureBundle]) -> "YieldFeatureEncoder":
        for feature_name in CATEGORICAL_FEATURES:
            values = {
                self._normalize_category(getattr(bundle, feature_name))
                for bundle in bundles
            }
            values.add(MISSING_CATEGORY)
            self.category_levels[feature_name] = sorted(values)
        return self

    def transform(self, bundles: list[YieldFeatureBundle]) -> list[list[float]]:
        return [self.transform_one(bundle) for bundle in bundles]

    def transform_one(self, bundle: YieldFeatureBundle) -> list[float]:
        vector: list[float] = []
        for feature_name in NUMERIC_FEATURES:
            value = getattr(bundle, feature_name)
            vector.append(float(NUMERIC_DEFAULTS[feature_name] if value is None else value))
            vector.append(1.0 if value is None else 0.0)

        for feature_name in BOOLEAN_FEATURES:
            vector.append(1.0 if getattr(bundle, feature_name) else 0.0)

        for feature_name in CATEGORICAL_FEATURES:
            value = self._normalize_category(getattr(bundle, feature_name))
            levels = self.category_levels.get(feature_name, [MISSING_CATEGORY])
            if value not in levels:
                value = MISSING_CATEGORY
            for level in levels:
                vector.append(1.0 if value == level else 0.0)
        return vector

    def feature_names(self) -> list[str]:
        names: list[str] = []
        for feature_name in NUMERIC_FEATURES:
            names.append(feature_name)
            names.append(f"{feature_name}__missing")
        for feature_name in BOOLEAN_FEATURES:
            names.append(feature_name)
        for feature_name in CATEGORICAL_FEATURES:
            for level in self.category_levels.get(feature_name, [MISSING_CATEGORY]):
                names.append(f"{feature_name}={level}")
        return names

    def to_metadata(self) -> dict[str, Any]:
        return {"category_levels": self.category_levels}

    @classmethod
    def from_metadata(cls, metadata: dict[str, Any]) -> "YieldFeatureEncoder":
        return cls(category_levels=metadata.get("category_levels", {}))

    @staticmethod
    def _normalize_category(value: Any) -> str:
        if value in {None, ""}:
            return MISSING_CATEGORY
        return str(value)


class YieldPredictionPipeline:
    """XGBoost-based pipeline for yield regression."""

    def __init__(
        self,
        encoder: YieldFeatureEncoder | None = None,
        model: Any | None = None,
        metrics: YieldModelMetrics | None = None,
        training_source: str = "unknown",
    ) -> None:
        self.encoder = encoder or YieldFeatureEncoder()
        self.model = model
        self.metrics = metrics
        self.training_source = training_source

    def build_dataset(self, samples: list[YieldTrainingSample]) -> YieldDataset:
        """Build the feature matrix `X` and target vector `y`."""

        if not self.encoder.category_levels:
            self.encoder.fit([sample.features for sample in samples])
        X = self.encoder.transform([sample.features for sample in samples])
        y = [sample.yield_per_hectare for sample in samples]
        return YieldDataset(X=X, y=y, feature_names=self.encoder.feature_names())

    def fit(
        self,
        samples: list[YieldTrainingSample],
        *,
        test_fraction: float = 0.2,
        random_seed: int = 20260319,
        training_source: str = "synthetic_mock_data",
    ) -> "YieldPredictionPipeline":
        """Fit the XGBoost regressor on prepared agronomic training data."""

        if Booster is None or DMatrix is None or xgb_train is None:
            raise RuntimeError(
                "xgboost is required for the yield prediction pipeline. "
                "Install dependencies from requirements.txt first."
            )
        if len(samples) < 10:
            raise ValueError("At least 10 samples are required to train the yield model.")

        train_samples, test_samples = _train_test_split(samples, test_fraction=test_fraction, seed=random_seed)

        self.encoder.fit([sample.features for sample in samples])
        train_dataset = self.build_dataset(train_samples)
        test_dataset = self.build_dataset(test_samples) if test_samples else None

        training_matrix = DMatrix(
            train_dataset.X,
            label=train_dataset.y,
            feature_names=train_dataset.feature_names,
        )
        self.model = xgb_train(
            params={
                "objective": "reg:squarederror",
                "max_depth": 5,
                "eta": 0.05,
                "subsample": 0.9,
                "colsample_bytree": 0.9,
                "alpha": 0.05,
                "lambda": 1.0,
                "seed": random_seed,
            },
            dtrain=training_matrix,
            num_boost_round=120,
        )

        evaluation_dataset = test_dataset or train_dataset
        evaluation_matrix = DMatrix(
            evaluation_dataset.X,
            feature_names=evaluation_dataset.feature_names,
        )
        predictions = [float(value) for value in self.model.predict(evaluation_matrix)]
        self.metrics = YieldModelMetrics(
            train_size=len(train_dataset.y),
            test_size=len(evaluation_dataset.y),
            rmse=_rmse(evaluation_dataset.y, predictions),
            mae=_mae(evaluation_dataset.y, predictions),
        )
        self.training_source = training_source
        return self

    def predict(
        self,
        features: YieldFeatureBundle,
    ) -> YieldPredictionOutput:
        """Predict a yield point estimate, range, and confidence score."""

        self._ensure_fitted()
        vector = self.encoder.transform_one(features)
        prediction = float(
            self.model.predict(DMatrix([vector], feature_names=self.encoder.feature_names()))[0]
        )
        predicted_yield = round(max(prediction, 0.0), 2)

        confidence = self._estimate_confidence(features)
        range_min, range_max = self._estimate_range(predicted_yield, confidence)

        return YieldPredictionOutput(
            predicted_yield=predicted_yield,
            predicted_yield_min=range_min,
            predicted_yield_max=range_max,
            metadata=AITraceMetadata(
                provider_name="xgboost_yield_prediction",
                provider_version=MODEL_VERSION,
                generated_at=datetime.now(timezone.utc),
                confidence=confidence,
                debug_info={
                    "training_source": self.training_source,
                    "missing_feature_ratio": round(features.missing_feature_ratio(), 4),
                    "metrics": asdict(self.metrics) if self.metrics is not None else None,
                },
            ),
            training_source=self.training_source,
        )

    def save(self, output_dir: str | Path) -> Path:
        """Persist the trained model and encoder metadata."""

        self._ensure_fitted()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(output_path / MODEL_FILENAME))
        metadata = {
            "encoder": self.encoder.to_metadata(),
            "metrics": asdict(self.metrics) if self.metrics is not None else None,
            "training_source": self.training_source,
            "model_version": MODEL_VERSION,
        }
        (output_path / METADATA_FILENAME).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return output_path

    @classmethod
    def load(cls, model_dir: str | Path) -> "YieldPredictionPipeline":
        """Load a previously persisted model pipeline."""

        if Booster is None:
            raise RuntimeError(
                "xgboost is required for the yield prediction pipeline. "
                "Install dependencies from requirements.txt first."
            )

        model_path = Path(model_dir)
        metadata = json.loads((model_path / METADATA_FILENAME).read_text(encoding="utf-8"))
        model = Booster()
        model.load_model(str(model_path / MODEL_FILENAME))
        metrics_payload = metadata.get("metrics")
        metrics = YieldModelMetrics(**metrics_payload) if metrics_payload is not None else None
        return cls(
            encoder=YieldFeatureEncoder.from_metadata(metadata.get("encoder", {})),
            model=model,
            metrics=metrics,
            training_source=metadata.get("training_source", "unknown"),
        )

    def _ensure_fitted(self) -> None:
        if self.model is None:
            raise RuntimeError("YieldPredictionPipeline must be trained or loaded before prediction.")

    def _estimate_confidence(self, features: YieldFeatureBundle) -> float:
        if self.metrics is None:
            return 0.5

        baseline_yield = 5.0
        error_ratio = self.metrics.rmse / baseline_yield
        model_confidence = max(0.35, min(0.92, 1.0 - min(error_ratio, 0.65)))
        completeness = 1.0 - features.missing_feature_ratio()
        confidence = model_confidence * (0.7 + (0.3 * completeness))
        return round(max(0.2, min(confidence, 0.95)), 2)

    def _estimate_range(self, prediction: float, confidence: float) -> tuple[float, float]:
        rmse_margin = self.metrics.rmse if self.metrics is not None else max(prediction * 0.15, 0.5)
        uncertainty_margin = prediction * max(0.08, (1.0 - confidence) * 0.4)
        margin = max(rmse_margin, uncertainty_margin)
        return round(max(0.0, prediction - margin), 2), round(prediction + margin, 2)


def _train_test_split(
    samples: list[YieldTrainingSample],
    *,
    test_fraction: float,
    seed: int,
) -> tuple[list[YieldTrainingSample], list[YieldTrainingSample]]:
    """Split the dataset deterministically without pulling in scikit-learn."""

    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1.")

    shuffled = list(samples)
    random.Random(seed).shuffle(shuffled)
    test_size = max(1, int(len(shuffled) * test_fraction))
    test_samples = shuffled[:test_size]
    train_samples = shuffled[test_size:]
    if not train_samples:
        raise ValueError("Training split is empty. Increase the number of samples or reduce test_fraction.")
    return train_samples, test_samples


def _rmse(actual: list[float], predicted: list[float]) -> float:
    squared_errors = [(truth - estimate) ** 2 for truth, estimate in zip(actual, predicted, strict=True)]
    return round(math.sqrt(sum(squared_errors) / len(squared_errors)), 4)


def _mae(actual: list[float], predicted: list[float]) -> float:
    absolute_errors = [abs(truth - estimate) for truth, estimate in zip(actual, predicted, strict=True)]
    return round(sum(absolute_errors) / len(absolute_errors), 4)
