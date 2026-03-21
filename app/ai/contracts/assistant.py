"""Contracts for natural-language answer generation providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class LLMAnswer:
    """Normalized answer returned by an assistant provider."""

    text: str
    model: str | None = None


class AssistantAnswerProvider(Protocol):
    """Provider contract for grounded assistant answer generation."""

    def generate_answer(self, *, system_prompt: str, user_prompt: str) -> LLMAnswer:
        """Return an answer produced from the supplied prompt pair."""
