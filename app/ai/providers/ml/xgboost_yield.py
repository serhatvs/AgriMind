"""XGBoost-backed yield prediction provider."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.contracts.yield_prediction import YieldPredictionInput, YieldPredictionOutput, YieldPredictor
from app.config import settings
from app.ml.mock_training_data import build_mock_crop_profiles, generate_mock_training_samples
from app.ml.yield_pipeline import YieldFeatureBundle, YieldPredictionPipeline
from app.services.crop_service import get_crops

_PIPELINE_CACHE: dict[str, YieldPredictionPipeline] = {}


def default_model_dir() -> Path:
    """Return the default yield-model artifact directory."""

    return Path(settings.YIELD_MODEL_DIR)


class XGBoostYieldPredictionProvider(YieldPredictor):
    """Prediction provider backed by the current XGBoost yield pipeline."""

    def __init__(
        self,
        db: Session | None,
        *,
        model_dir: str | Path | None = None,
    ) -> None:
        self.db = db
        self._model_dir = Path(model_dir) if model_dir is not None else default_model_dir()

    @property
    def model_dir(self) -> Path:
        return self._model_dir

    def predict(self, request: YieldPredictionInput) -> YieldPredictionOutput:
        """Predict yield from the canonical yield-prediction input."""

        pipeline = self._get_or_train_pipeline()
        features = YieldFeatureBundle.from_prediction_input(request)
        return pipeline.predict(features)

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
