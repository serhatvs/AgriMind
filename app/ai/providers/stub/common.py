"""Shared helpers used by deterministic stub providers."""

from __future__ import annotations

import json
from collections.abc import Mapping

STUB_PROVIDER_MARKER = "stub provider"
STUB_PROVIDER_SUFFIX = f"({STUB_PROVIDER_MARKER})"


def clamp(value: float, lower: float, upper: float) -> float:
    """Clamp `value` to the inclusive `[lower, upper]` range."""

    return max(lower, min(value, upper))


def round_stable(value: float) -> float:
    """Round float output consistently for user-facing placeholder values."""

    return round(float(value), 2)


def normalize_text(text: str) -> str:
    """Collapse whitespace so stub output remains stable across payload shapes."""

    return " ".join(text.split())


def as_sentence(text: str) -> str:
    """Return a trimmed sentence with terminal punctuation."""

    normalized = normalize_text(text)
    if not normalized:
        return ""
    if normalized.endswith((".", "!", "?")):
        return normalized
    return f"{normalized}."


def dedupe_messages(messages: list[str]) -> list[str]:
    """Preserve message order while removing empty or duplicate entries."""

    seen: set[str] = set()
    ordered: list[str] = []
    for message in messages:
        normalized = normalize_text(message)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def with_stub_suffix(text: str) -> str:
    """Append a stable stub marker to the supplied message."""

    normalized = normalize_text(text).rstrip(".")
    if not normalized:
        return STUB_PROVIDER_SUFFIX
    if normalized.endswith(STUB_PROVIDER_SUFFIX):
        return normalized
    return f"{normalized}. {STUB_PROVIDER_SUFFIX}"


def stable_payload_summary(payload: Mapping[str, object]) -> str:
    """Return a stable JSON summary used when no text payload can be extracted."""

    summary = {"keys": sorted(str(key) for key in payload)}
    return json.dumps(summary, sort_keys=True)
