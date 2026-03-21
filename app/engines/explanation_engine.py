"""Compatibility façade for provider-backed explanation generation."""

from app.ai.providers.rule_based.explanation import (
    COMPONENT_ORDER,
    RuleBasedExplanationProvider,
    build_ranked_field_explanation,
    build_suitability_explanation,
    generate_explanation,
)

__all__ = [
    "COMPONENT_ORDER",
    "RuleBasedExplanationProvider",
    "build_ranked_field_explanation",
    "build_suitability_explanation",
    "generate_explanation",
]
