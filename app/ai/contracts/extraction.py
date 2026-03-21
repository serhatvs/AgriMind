"""Canonical contracts and compatibility helpers for structured extraction providers.

Example:
```python
from app.ai.contracts.extraction import ExtractionInput
from app.ai.providers.stub.extraction import StubExtractionProvider

provider = StubExtractionProvider()
output = provider.extract(
    ExtractionInput(
        raw_text="Apply NPK 20-20-20 at 180 kg/ha before planting.",
        source_url="https://example.com/fertilizer-guide",
        source_type="webpage",
        extraction_kind="fertilizer",
    )
)

print(output.normalized_json)
print(output.missing_fields)
print(output.provider_name, output.provider_version)
```
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from app.ai.contracts.metadata import AITraceMetadata


@dataclass(slots=True)
class ExtractionInput:
    """Canonical structured-extraction input used by ingestion-capable providers."""

    raw_text: str
    source_url: str | None
    source_type: str
    extraction_kind: str


@dataclass(slots=True)
class ExtractionRequest:
    """Compatibility wrapper for payload-based extraction callers."""

    payload: Mapping[str, object]


@dataclass(slots=True)
class ExtractionOutput:
    """Canonical structured-extraction output returned by extraction providers."""

    normalized_json: dict[str, object]
    missing_fields: list[str] = field(default_factory=list)
    metadata: AITraceMetadata = field(
        default_factory=lambda: AITraceMetadata(
            provider_name="unknown",
            provider_version=None,
            generated_at=datetime.now(timezone.utc),
            confidence=None,
        )
    )

    @property
    def confidence(self) -> float | None:
        return self.metadata.confidence

    @property
    def provider_name(self) -> str:
        return self.metadata.provider_name

    @property
    def provider_version(self) -> str | None:
        return self.metadata.provider_version

    @property
    def generated_at(self) -> datetime:
        return self.metadata.generated_at

    @property
    def debug_info(self) -> dict[str, object] | None:
        return self.metadata.debug_info

    @property
    def text(self) -> str:
        """Compatibility text view used by legacy assistant payload normalization."""

        for key in ("text", "normalized_text", "summary", "answer"):
            value = self.normalized_json.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return json.dumps(self.normalized_json, sort_keys=True)


class ExtractionProvider(Protocol):
    """Extract normalized structured data from raw text and source metadata."""

    def extract(self, request: ExtractionInput) -> ExtractionOutput:
        """Return normalized structured data for `request`."""


def build_extraction_input_from_payload(
    payload: Mapping[str, object],
    *,
    source_url: str | None = None,
    source_type: str = "provider_payload",
    extraction_kind: str = "llm_response_text",
    strict: bool = False,
) -> ExtractionInput:
    """Convert a compatibility payload into the canonical extraction input."""

    return ExtractionInput(
        raw_text=_extract_text_from_payload(payload, strict=strict),
        source_url=source_url,
        source_type=source_type,
        extraction_kind=extraction_kind,
    )


def _extract_text_from_payload(payload: Mapping[str, object], *, strict: bool) -> str:
    for key in ("normalized_text", "text", "message"):
        value = payload.get(key)
        if isinstance(value, str):
            normalized = _normalize_text(value)
            if normalized:
                return normalized

    output = payload.get("output", [])
    if not isinstance(output, list):
        if strict:
            raise ValueError("OpenAI response did not include an output list.")
        return json.dumps({"keys": sorted(str(key) for key in payload)}, sort_keys=True)

    chunks: list[str] = []
    for item in output:
        if not isinstance(item, Mapping):
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, Mapping):
                continue
            text = content_item.get("text")
            if isinstance(text, str):
                normalized = _normalize_text(text)
                if normalized:
                    chunks.append(normalized)
    if chunks:
        return "\n".join(chunks)
    if strict:
        raise ValueError("OpenAI response did not include any output_text content.")

    return json.dumps({"keys": sorted(str(key) for key in payload)}, sort_keys=True)


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


ExtractionResult = ExtractionOutput
TextExtractionProvider = ExtractionProvider
