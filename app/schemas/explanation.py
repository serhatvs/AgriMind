"""Internal schemas for deterministic explanation output."""

from pydantic import BaseModel, ConfigDict


class FieldExplanation(BaseModel):
    """Structured explanation derived from suitability or ranking results."""

    model_config = ConfigDict(extra="forbid")

    short_explanation: str
    detailed_explanation: str
    strengths: list[str]
    weaknesses: list[str]
    risks: list[str]
