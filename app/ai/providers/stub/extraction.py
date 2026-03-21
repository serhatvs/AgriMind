"""Deterministic stub extraction provider for development and tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from app.ai.contracts.extraction import (
    ExtractionInput,
    ExtractionOutput,
    ExtractionProvider,
    ExtractionRequest,
    build_extraction_input_from_payload,
)
from app.ai.contracts.metadata import AITraceMetadata
from app.ai.providers.stub.common import normalize_text


class StubExtractionProvider(ExtractionProvider):
    """Return deterministic structured mock extraction output for ingestion flows."""

    def extract(self, request: ExtractionInput | ExtractionRequest) -> ExtractionOutput:
        """Return deterministic structured output from raw text or compatibility payloads."""

        input_data = self._coerce_input(request)
        normalized_text = normalize_text(input_data.raw_text)

        if input_data.extraction_kind == "fertilizer":
            return self._build_fertilizer_output(input_data, normalized_text)
        if input_data.extraction_kind in {"crop_requirement", "crop_requirements"}:
            return self._build_crop_requirements_output(input_data, normalized_text)
        if input_data.extraction_kind == "irrigation":
            return self._build_irrigation_output(input_data, normalized_text)
        return self._build_text_output(input_data, normalized_text)

    def extract_output_text(self, payload: Mapping[str, object]) -> str:
        """Compatibility wrapper that returns extracted text directly."""

        return self.extract(ExtractionRequest(payload=payload)).text

    def _coerce_input(self, request: ExtractionInput | ExtractionRequest) -> ExtractionInput:
        if isinstance(request, ExtractionInput):
            return request
        return build_extraction_input_from_payload(request.payload)

    def _build_fertilizer_output(
        self,
        input_data: ExtractionInput,
        normalized_text: str,
    ) -> ExtractionOutput:
        return ExtractionOutput(
            normalized_json={
                "fertilizer_name": "NPK 20-20-20",
                "application_rate_kg_per_ha": 180,
                "application_stage": "pre-plant",
                "nutrient_analysis": {
                    "nitrogen_percent": 20,
                    "phosphorus_percent": 20,
                    "potassium_percent": 20,
                },
                "source_url": input_data.source_url,
                "source_type": input_data.source_type,
                "raw_excerpt": normalized_text[:160],
            },
            missing_fields=["application_window"],
            metadata=self._metadata(
                input_data,
                confidence=0.83,
                normalized_text=normalized_text,
            ),
        )

    def _build_crop_requirements_output(
        self,
        input_data: ExtractionInput,
        normalized_text: str,
    ) -> ExtractionOutput:
        return ExtractionOutput(
            normalized_json={
                "crop_name": "Corn",
                "optimal_ph_min": 6.0,
                "optimal_ph_max": 6.8,
                "water_requirement_level": "high",
                "drainage_requirement": "moderate",
                "rooting_depth_cm": 150,
                "source_url": input_data.source_url,
                "source_type": input_data.source_type,
                "raw_excerpt": normalized_text[:160],
            },
            missing_fields=["heat_tolerance_days"],
            metadata=self._metadata(
                input_data,
                confidence=0.8,
                normalized_text=normalized_text,
            ),
        )

    def _build_irrigation_output(
        self,
        input_data: ExtractionInput,
        normalized_text: str,
    ) -> ExtractionOutput:
        return ExtractionOutput(
            normalized_json={
                "irrigation_method": "drip",
                "recommended_frequency": "weekly",
                "target_application_mm": 35,
                "season_stage": "vegetative",
                "water_source": "well",
                "source_url": input_data.source_url,
                "source_type": input_data.source_type,
                "raw_excerpt": normalized_text[:160],
            },
            missing_fields=["distribution_uniformity"],
            metadata=self._metadata(
                input_data,
                confidence=0.78,
                normalized_text=normalized_text,
            ),
        )

    def _build_text_output(
        self,
        input_data: ExtractionInput,
        normalized_text: str,
    ) -> ExtractionOutput:
        text = normalized_text or "No structured extraction input was provided."
        prefix = "Stub extraction result:"
        return ExtractionOutput(
            normalized_json={
                "text": f"{prefix} {text}",
                "source_url": input_data.source_url,
                "source_type": input_data.source_type,
                "extraction_kind": input_data.extraction_kind,
            },
            missing_fields=[] if normalized_text else ["raw_text"],
            metadata=self._metadata(
                input_data,
                confidence=0.8 if normalized_text else 0.52,
                normalized_text=normalized_text,
            ),
        )

    def _metadata(
        self,
        input_data: ExtractionInput,
        *,
        confidence: float,
        normalized_text: str,
    ) -> AITraceMetadata:
        return AITraceMetadata(
            provider_name="deterministic_stub_provider",
            provider_version="v1",
            generated_at=datetime.now(timezone.utc),
            confidence=confidence,
            debug_info={
                "stub": True,
                "source_type": input_data.source_type,
                "source_url": input_data.source_url,
                "extraction_kind": input_data.extraction_kind,
                "raw_text_present": bool(normalized_text),
            },
        )

