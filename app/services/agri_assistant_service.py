"""Compatibility facade for provider-based agronomic assistant orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ai.contracts.assistant import AssistantAnswerProvider, LLMAnswer
from app.ai.orchestration.agri_assistant import (
    AgriAssistantOrchestrator,
    ask_agri_assistant,
    build_agri_assistant_context,
)

if TYPE_CHECKING:
    from app.ai.providers.llm.openai_responses import OpenAIResponsesClient


class AgriAssistantService(AgriAssistantOrchestrator):
    """Preserve the legacy service interface over the new assistant orchestrator."""

    def __init__(self, provider: AssistantAnswerProvider | None = None) -> None:
        super().__init__(provider=provider)


def __getattr__(name: str) -> object:
    """Lazily expose the legacy OpenAI client import for backward compatibility."""

    if name == "OpenAIResponsesClient":
        from app.ai.providers.llm.openai_responses import OpenAIResponsesClient

        return OpenAIResponsesClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AgriAssistantService",
    "AssistantAnswerProvider",
    "LLMAnswer",
    "OpenAIResponsesClient",
    "ask_agri_assistant",
    "build_agri_assistant_context",
]
