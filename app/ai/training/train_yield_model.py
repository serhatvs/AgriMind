"""CLI runner for training the MVP yield model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ai.providers.ml.xgboost_yield import XGBoostYieldPredictionProvider
from app.config import settings
from app.db.session import SessionLocal


def default_model_dir() -> Path:
    """Return the configured artifact directory for training output."""

    configured_path = Path(settings.YIELD_MODEL_PATH)
    return configured_path.parent if configured_path.suffix else configured_path


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for yield model training."""

    parser = argparse.ArgumentParser(description="Train the AgriMind yield prediction model.")
    parser.add_argument("--model-dir", type=Path, default=default_model_dir())
    parser.add_argument("--sample-count", type=int, default=settings.YIELD_TRAINING_SAMPLE_COUNT)
    parser.add_argument("--random-seed", type=int, default=settings.YIELD_TRAINING_RANDOM_SEED)
    parser.add_argument("--min-real-samples", type=int, default=settings.YIELD_MIN_REAL_TRAINING_SAMPLES)
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Train the yield model and print a compact JSON summary."""

    parser = build_parser()
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        provider = XGBoostYieldPredictionProvider(
            db,
            model_dir=args.model_dir,
        )
        pipeline = provider.train_model(
            sample_count=args.sample_count,
            random_seed=args.random_seed,
            save=not args.no_save,
            force=args.force,
            min_real_samples=args.min_real_samples,
        )

    metrics = pipeline.metrics
    print(
        json.dumps(
            {
                "provider_name": "xgboost_yield_prediction",
                "provider_version": settings.YIELD_MODEL_VERSION,
                "model_dir": str(args.model_dir),
                "training_source": pipeline.training_source,
                "train_size": metrics.train_size if metrics is not None else 0,
                "test_size": metrics.test_size if metrics is not None else 0,
                "rmse": metrics.rmse if metrics is not None else None,
                "mae": metrics.mae if metrics is not None else None,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
