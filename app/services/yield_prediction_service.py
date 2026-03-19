"""Service layer for yield predictions.

Example:
```python
from app.services.yield_prediction_service import YieldPredictionService

service = YieldPredictionService(db)
prediction = service.predict_yield(field_id=1, crop_id=2)

print(prediction.predicted_yield_per_hectare)
print(prediction.predicted_yield_range.min, prediction.predicted_yield_range.max)
print(prediction.confidence_score)
```
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ml.mock_training_data import build_mock_crop_profiles, generate_mock_training_samples
from app.ml.yield_pipeline import YieldFeatureBundle, YieldPredictionPipeline
from app.schemas.yield_prediction import YieldPredictionResult
from app.services.crop_service import get_crop, get_crops
from app.services.field_service import get_field
from app.services.soil_service import get_latest_soil_test_for_field
from app.services.weather_service import WeatherService

DEFAULT_MODEL_DIR = Path("artifacts") / "yield_model"
_PIPELINE_CACHE: dict[str, YieldPredictionPipeline] = {}


class YieldPredictionService:
    """Prediction service backed by an XGBoost yield pipeline."""

    def __init__(
        self,
        db: Session | None,
        *,
        model_dir: str | Path | None = None,
    ) -> None:
        self.db = db
        self.model_dir = Path(model_dir) if model_dir is not None else DEFAULT_MODEL_DIR

    def predict_yield(self, field_id: int, crop_id: int) -> YieldPredictionResult:
        """Predict expected yield for a field and crop combination."""

        if self.db is None:
            raise ValueError("A database session is required to predict by field_id and crop_id.")

        field_obj = get_field(self.db, field_id)
        if field_obj is None:
            raise ValueError(f"Field with id {field_id} not found")

        crop = get_crop(self.db, crop_id)
        if crop is None:
            raise ValueError(f"Crop with id {crop_id} not found")

        soil_test = get_latest_soil_test_for_field(self.db, field_id)
        climate_summary = WeatherService(self.db).get_climate_summary(field_id)
        return self.predict_for_entities(
            field_obj,
            crop,
            soil_test=soil_test,
            climate_summary=climate_summary,
        )

    def predict_for_entities(
        self,
        field_obj,
        crop,
        *,
        soil_test=None,
        climate_summary=None,
    ) -> YieldPredictionResult:
        """Predict yield from fully or partially assembled domain objects."""

        pipeline = self._get_or_train_pipeline()
        features = YieldFeatureBundle.from_entities(
            field_obj,
            crop,
            soil_test=soil_test,
            climate_summary=climate_summary,
        )
        return pipeline.predict(features, field_id=field_obj.id, crop_id=crop.id)

    def train_model(
        self,
        *,
        sample_count: int = 600,
        random_seed: int = 20260319,
        save: bool = True,
        force: bool = False,
    ) -> YieldPredictionPipeline:
        """Train the yield model from deterministic synthetic training data."""

        cache_key = str(self.model_dir.resolve())
        if not force and cache_key in _PIPELINE_CACHE:
            return _PIPELINE_CACHE[cache_key]

        crop_profiles = self._load_reference_crops()
        samples = generate_mock_training_samples(
            crop_profiles=crop_profiles,
            sample_count=sample_count,
            random_seed=random_seed,
        )
        pipeline = YieldPredictionPipeline().fit(
            samples,
            training_source="synthetic_mock_data",
            random_seed=random_seed,
        )
        if save:
            pipeline.save(self.model_dir)
        _PIPELINE_CACHE[cache_key] = pipeline
        return pipeline

    def _get_or_train_pipeline(self) -> YieldPredictionPipeline:
        cache_key = str(self.model_dir.resolve())
        cached = _PIPELINE_CACHE.get(cache_key)
        if cached is not None:
            return cached

        model_path = self.model_dir / "yield_model.json"
        metadata_path = self.model_dir / "yield_model_metadata.json"
        if model_path.exists() and metadata_path.exists():
            pipeline = YieldPredictionPipeline.load(self.model_dir)
            _PIPELINE_CACHE[cache_key] = pipeline
            return pipeline

        return self.train_model(save=False)

    def _load_reference_crops(self):
        if self.db is None:
            return build_mock_crop_profiles()
        try:
            crops = get_crops(self.db, skip=0, limit=1000)
        except SQLAlchemyError:
            return build_mock_crop_profiles()
        return crops or build_mock_crop_profiles()
