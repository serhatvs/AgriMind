"""Train and persist the MVP yield model."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.yield_prediction_service import YieldPredictionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the AgriMind yield prediction model.")
    parser.add_argument(
        "--output-dir",
        default=str(Path("artifacts") / "yield_model"),
        help="Directory where the trained model artifacts will be written.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=600,
        help="Number of deterministic synthetic training samples to generate.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Retrain even if a cached in-process model already exists.",
    )
    args = parser.parse_args()

    db = None
    try:
        try:
            from app.database import SessionLocal

            db = SessionLocal()
        except Exception:
            db = None

        service = YieldPredictionService(db, model_dir=args.output_dir)
        pipeline = service.train_model(sample_count=args.samples, save=True, force=args.force)
    finally:
        if db is not None:
            db.close()

    metrics = pipeline.metrics
    print(f"Saved yield model to {Path(args.output_dir).resolve()}")
    if metrics is not None:
        print(
            "Metrics:",
            f"train_size={metrics.train_size}",
            f"test_size={metrics.test_size}",
            f"rmse={metrics.rmse}",
            f"mae={metrics.mae}",
        )


if __name__ == "__main__":
    main()
