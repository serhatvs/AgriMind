"""Compatibility facade for provider-based yield prediction."""

from __future__ import annotations

from pathlib import Path

from app.ai.orchestration.yield_prediction import YieldPredictionOrchestrator
from app.config import settings

_configured_model_path = Path(settings.YIELD_MODEL_PATH)
DEFAULT_MODEL_DIR = _configured_model_path.parent if _configured_model_path.suffix else _configured_model_path


class YieldPredictionService(YieldPredictionOrchestrator):
    """Preserve the legacy service interface over the configured yield provider."""

    def __init__(self, db, *, model_dir: str | Path | None = None) -> None:
        super().__init__(db, model_dir=model_dir)


def __getattr__(name: str) -> object:
    """Lazily expose legacy ML symbols without coupling selection to one provider."""

    if name == "_PIPELINE_CACHE":
        from app.ai.providers.ml.xgboost_yield import _PIPELINE_CACHE

        return _PIPELINE_CACHE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["DEFAULT_MODEL_DIR", "YieldPredictionService", "_PIPELINE_CACHE"]
