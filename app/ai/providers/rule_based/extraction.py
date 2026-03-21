"""Rule-based extraction provider used for deterministic payload normalization."""

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


class RuleBasedTextExtractionProvider(ExtractionProvider):
    """Default extraction provider for deterministic text normalization."""

    def extract(self, request: ExtractionInput | ExtractionRequest) -> ExtractionOutput:
        """Return normalized structured output for canonical or payload-based requests."""

        input_data = self._coerce_input(request)
        normalized_text = " ".join(input_data.raw_text.split())
        if not normalized_text:
            raise ValueError("Extraction input did not include any usable raw text.")

        return ExtractionOutput(
            normalized_json={
                "text": normalized_text,
                "source_type": input_data.source_type,
                "source_url": input_data.source_url,
                "extraction_kind": input_data.extraction_kind,
            },
            missing_fields=[],
            metadata=AITraceMetadata(
                provider_name="rule_based",
                provider_version="v1",
                generated_at=datetime.now(timezone.utc),
                confidence=0.95,
                debug_info={
                    "payload_format": "llm_response_text"
                    if isinstance(request, ExtractionRequest)
                    else "raw_text",
                    "extraction_kind": input_data.extraction_kind,
                },
            ),
        )

    def extract_output_text(self, payload: Mapping[str, object]) -> str:
        """Compatibility wrapper retained for payload-based response parsing."""

        return self.extract(ExtractionRequest(payload=payload)).text

    def _coerce_input(self, request: ExtractionInput | ExtractionRequest) -> ExtractionInput:
        if isinstance(request, ExtractionInput):
            return request
        return build_extraction_input_from_payload(request.payload, strict=True)
