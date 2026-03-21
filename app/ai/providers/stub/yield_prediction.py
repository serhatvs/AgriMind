"""Deterministic placeholder yield predictor used in development and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.ai.contracts.metadata import AITraceMetadata
from app.ai.contracts.yield_prediction import YieldPredictionInput, YieldPredictionOutput, YieldPredictor
from app.ai.providers.stub.common import clamp, round_stable


class DeterministicYieldPredictor(YieldPredictor):
    """Return realistic but deterministic placeholder yield predictions."""

    def __init__(self, *, model_dir: str | Path | None = None) -> None:
        self._model_dir = Path(model_dir) if model_dir is not None else Path("artifacts") / "stub_yield"
        self.requests: list[YieldPredictionInput] = []

    @property
    def model_dir(self) -> Path:
        """Return the placeholder artifact directory for the deterministic provider."""

        return self._model_dir

    def predict(self, request: YieldPredictionInput) -> YieldPredictionOutput:
        """Return deterministic placeholder yield output from normalized summaries."""

        self.requests.append(request)
        predicted_yield = self._estimate_yield(request)
        confidence = self._estimate_confidence(request)
        margin = self._estimate_margin(confidence)
        return YieldPredictionOutput(
            predicted_yield=predicted_yield,
            predicted_yield_min=round_stable(clamp(predicted_yield - margin, 0.0, predicted_yield)),
            predicted_yield_max=round_stable(predicted_yield + margin),
            metadata=AITraceMetadata(
                provider_name="deterministic_yield_prediction",
                provider_version="v1",
                generated_at=datetime.now(timezone.utc),
                confidence=confidence,
                debug_info={
                    "fallback": True,
                    "has_soil": request.soil is not None,
                    "has_climate": request.climate is not None,
                    "field_irrigated": request.field.irrigation_available,
                },
            ),
            training_source="deterministic_heuristics",
        )

    def train_model(
        self,
        *,
        sample_count: int = 0,
        random_seed: int = 20260320,
        save: bool = False,
        force: bool = False,
    ) -> dict[str, object]:
        """Return deterministic metadata for legacy training calls against the stub."""

        return {
            "provider_name": "deterministic_yield_prediction",
            "provider_version": "v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sample_count": sample_count,
            "random_seed": random_seed,
            "save": save,
            "force": force,
        }

    def _estimate_yield(self, request: YieldPredictionInput) -> float:
        score = 6.1
        field = request.field
        crop = request.crop
        soil = request.soil
        climate = request.climate

        if field.irrigation_available:
            score += 0.55

        slope = float(field.slope_percent or 0.0)
        if slope <= 5:
            score += 0.35
        elif slope <= 12:
            score += 0.15
        else:
            score -= 0.3

        drainage = str(field.drainage_quality or "").strip().lower()
        if drainage == "good":
            score += 0.3
        elif drainage in {"moderate", "fair"}:
            score += 0.1
        else:
            score -= 0.2

        if soil is not None:
            score += 0.22
            if soil.ph is not None:
                if crop.ideal_ph_min is not None and crop.ideal_ph_max is not None and crop.ideal_ph_min <= soil.ph <= crop.ideal_ph_max:
                    score += 0.15
                elif 5.5 <= soil.ph <= 7.5:
                    score += 0.05
                else:
                    score -= 0.15

            if soil.organic_matter_percent is not None and soil.organic_matter_percent >= 3.0:
                score += 0.1
            if soil.nitrogen_ppm is not None and soil.nitrogen_ppm >= 40:
                score += 0.12
            if soil.phosphorus_ppm is not None and soil.phosphorus_ppm >= 25:
                score += 0.07
            if soil.potassium_ppm is not None and soil.potassium_ppm >= 180:
                score += 0.07
            if soil.ec is not None and soil.ec > 3.0:
                score -= 0.18

        if climate is not None:
            score += 0.22
            climate_signal = 0.0
            if (
                crop.optimal_temp_min_c is not None
                and crop.optimal_temp_max_c is not None
                and climate.avg_temp is not None
            ):
                if crop.optimal_temp_min_c <= climate.avg_temp <= crop.optimal_temp_max_c:
                    climate_signal += 0.16
                else:
                    climate_signal -= 0.12

            if crop.rainfall_requirement_mm is not None and climate.total_rainfall is not None:
                if climate.total_rainfall >= crop.rainfall_requirement_mm * 0.75:
                    climate_signal += 0.1
                else:
                    climate_signal -= 0.14
            if climate.frost_days is not None and crop.frost_tolerance_days is not None:
                climate_signal += 0.05 if climate.frost_days <= crop.frost_tolerance_days else -0.1
            if climate.heat_days is not None and crop.heat_tolerance_days is not None:
                climate_signal += 0.05 if climate.heat_days <= crop.heat_tolerance_days else -0.1
            score += climate_signal

        return round_stable(clamp(score, 4.8, 9.3))

    def _estimate_confidence(self, request: YieldPredictionInput) -> float:
        field = request.field
        crop = request.crop
        present_signals = [
            request.soil is not None,
            request.climate is not None,
            bool(field.irrigation_available),
            bool(field.drainage_quality),
            field.slope_percent is not None,
            crop.optimal_temp_min_c is not None or crop.rainfall_requirement_mm is not None,
        ]
        completeness = sum(1 for signal in present_signals if signal) / len(present_signals)
        bonus = 0.02 if request.soil is not None and request.climate is not None else 0.0
        confidence = 0.64 + (completeness * 0.12) + bonus
        return round_stable(clamp(confidence, 0.64, 0.78))

    def _estimate_margin(self, confidence: float) -> float:
        margin = 1.08 - ((confidence - 0.6) * 1.1)
        return round_stable(clamp(margin, 0.8, 1.05))


class StubYieldPredictor(DeterministicYieldPredictor):
    """Compatibility alias retained for configured stub-provider selection."""
