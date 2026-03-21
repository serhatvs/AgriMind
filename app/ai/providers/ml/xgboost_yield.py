"""XGBoost-backed yield prediction provider."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.contracts.metadata import AITraceMetadata
from app.ai.contracts.yield_prediction import YieldPredictionInput, YieldPredictionOutput, YieldPredictor
from app.ai.training.yield_dataset import build_yield_training_dataset
from app.config import settings
from app.ml.yield_pipeline import YieldFeatureBundle, YieldPredictionPipeline
from app.ai.providers.stub.yield_prediction import DeterministicYieldPredictor

_PIPELINE_CACHE: dict[str, YieldPredictionPipeline] = {}


def default_model_dir() -> Path:
    """Return the default yield-model artifact directory."""

    configured_path = Path(settings.YIELD_MODEL_PATH)
    return configured_path.parent if configured_path.suffix else configured_path


class XGBoostYieldPredictionProvider(YieldPredictor):
    """Prediction provider backed by the current XGBoost yield pipeline."""

    def __init__(
        self,
        db: Session | None,
        *,
        model_dir: str | Path | None = None,
        fallback_predictor: YieldPredictor | None = None,
    ) -> None:
        self.db = db
        resolved_dir = Path(model_dir) if model_dir is not None else default_model_dir()
        if resolved_dir.suffix:
            resolved_dir = resolved_dir.parent
        self._model_dir = resolved_dir
        self._fallback_predictor = fallback_predictor or DeterministicYieldPredictor(
            model_dir=self._model_dir / "deterministic_fallback"
        )

    @property
    def model_dir(self) -> Path:
        return self._model_dir

    def predict(self, request: YieldPredictionInput) -> YieldPredictionOutput:
        """Predict yield from the canonical yield-prediction input."""

        pipeline = self._get_pipeline()
        if pipeline is None:
            return self._fallback_prediction(
                request,
                reason=(
                    "Yield model artifact was not found or could not be loaded; "
                    "used deterministic fallback."
                ),
            )
        features = YieldFeatureBundle.from_prediction_input(request)
        try:
            return pipeline.predict(features)
        except Exception:
            return self._fallback_prediction(
                request,
                reason="Yield model inference failed; used deterministic fallback.",
            )

    def train_model(
        self,
        *,
        sample_count: int = 600,
        random_seed: int = 20260319,
        save: bool = True,
        force: bool = False,
        min_real_samples: int | None = None,
    ) -> YieldPredictionPipeline:
        """Train the yield model from deterministic synthetic training data."""

        cache_key = str(self.model_dir.resolve())
        if not force and cache_key in _PIPELINE_CACHE:
            return _PIPELINE_CACHE[cache_key]

        dataset_bundle = build_yield_training_dataset(
            self.db,
            target_sample_count=sample_count,
            random_seed=random_seed,
            min_real_samples=min_real_samples,
        )
        pipeline = YieldPredictionPipeline().fit(
            dataset_bundle.samples,
            training_source=dataset_bundle.source_name,
            random_seed=random_seed,
        )
        if save:
            pipeline.save(self.model_dir)
        _PIPELINE_CACHE[cache_key] = pipeline
        return pipeline

    def _get_pipeline(self) -> YieldPredictionPipeline | None:
        cache_key = str(self.model_dir.resolve())
        cached = _PIPELINE_CACHE.get(cache_key)
        if cached is not None:
            return cached

        model_path = self.model_dir / "yield_model.json"
        metadata_path = self.model_dir / "yield_model_metadata.json"
        if model_path.exists() and metadata_path.exists():
            try:
                pipeline = YieldPredictionPipeline.load(self.model_dir)
            except (FileNotFoundError, RuntimeError, SQLAlchemyError, ValueError):
                return None
            _PIPELINE_CACHE[cache_key] = pipeline
            return pipeline
        return None

    def _fallback_prediction(
        self,
        request: YieldPredictionInput,
        *,
        reason: str,
    ) -> YieldPredictionOutput:
        output = self._fallback_predictor.predict(request)
        normalized_metadata = output.metadata.normalized()
        debug_info = {
            **(normalized_metadata.debug_info or {}),
            "fallback_reason": reason,
            "requested_provider": "xgboost_yield_prediction",
        }
        return replace(
            output,
            metadata=AITraceMetadata(
                provider_name=normalized_metadata.provider_name,
                provider_version=normalized_metadata.provider_version,
                generated_at=normalized_metadata.generated_at,
                confidence=normalized_metadata.confidence,
                debug_info=debug_info,
            ),
        )
