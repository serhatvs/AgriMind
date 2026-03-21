"""Provider-based orchestration for yield prediction."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.contracts.yield_prediction import (
    YieldPredictionContext,
    YieldPredictionInput,
    YieldPredictionOutput,
    YieldPredictionRequest,
    YieldPredictor,
    adapt_yield_prediction_output,
    build_yield_prediction_input_from_context,
    build_yield_prediction_input_from_entities,
)
from app.ai.features.yield_prediction import build_yield_prediction_input
from app.ai.registry import get_ai_provider_registry
from app.schemas.yield_prediction import YieldPredictionResult


class YieldPredictionOrchestrator:
    """Resolve and delegate to the configured yield prediction provider."""

    def __init__(
        self,
        db: Session | None,
        *,
        model_dir: str | Path | None = None,
        provider: YieldPredictor | None = None,
    ) -> None:
        self.db = db
        self.provider = provider or get_ai_provider_registry().get_yield_prediction_provider(
            db=db,
            model_dir=model_dir,
        )

    @property
    def model_dir(self) -> Path:
        return self.provider.model_dir

    def predict(self, request: YieldPredictionInput) -> YieldPredictionOutput:
        """Predict yield using the canonical provider input."""

        return self.provider.predict(request)

    def predict_from_context(self, request: YieldPredictionContext) -> YieldPredictionResult:
        """Predict yield using a compatibility ORM context."""

        input_data = build_yield_prediction_input_from_context(request)
        return adapt_yield_prediction_output(input_data, self.predict(input_data))

    def predict_yield(self, field_id: int, crop_id: int) -> YieldPredictionResult:
        """Predict expected yield for a persisted field and crop combination."""

        if self.db is None:
            raise ValueError("A database session is required to predict by field_id and crop_id.")

        request = YieldPredictionRequest(field_id=field_id, crop_id=crop_id)
        input_data = build_yield_prediction_input(self.db, request.field_id, request.crop_id)
        return adapt_yield_prediction_output(input_data, self.predict(input_data))

    def predict_for_entities(
        self,
        field_obj,
        crop,
        *,
        soil_test=None,
        climate_summary=None,
    ) -> YieldPredictionResult:
        """Predict yield from fully or partially assembled domain objects."""

        input_data = build_yield_prediction_input_from_entities(
            field_obj,
            crop,
            soil_test=soil_test,
            climate_summary=climate_summary,
        )
        return adapt_yield_prediction_output(input_data, self.predict(input_data))

    def train_model(
        self,
        *,
        sample_count: int = 600,
        random_seed: int = 20260319,
        save: bool = True,
        force: bool = False,
    ) -> object:
        """Train or refresh the underlying yield model."""

        trainer = getattr(self.provider, "train_model")
        return trainer(
            sample_count=sample_count,
            random_seed=random_seed,
            save=save,
            force=force,
        )
