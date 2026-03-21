"""OpenAI Responses API provider for grounded agronomic answers."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import httpx

from app.ai.contracts.assistant import AssistantAnswerProvider, LLMAnswer
from app.ai.contracts.extraction import ExtractionProvider, ExtractionRequest
from app.ai.providers.rule_based.extraction import RuleBasedTextExtractionProvider


class OpenAIResponsesClient(AssistantAnswerProvider):
    """Minimal OpenAI Responses API adapter used by the agronomic assistant."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        extraction_provider: ExtractionProvider | None = None,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.extraction_provider = extraction_provider or RuleBasedTextExtractionProvider()
        self.client_factory = client_factory or self._default_client_factory

    def _default_client_factory(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    def generate_answer(self, *, system_prompt: str, user_prompt: str) -> LLMAnswer:
        payload = {
            "model": self.model,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_prompt,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_prompt,
                        }
                    ],
                },
            ],
        }

        with self.client_factory() as client:
            response = client.post("/responses", json=payload)
            response.raise_for_status()

        data = response.json()
        return LLMAnswer(
            text=self.extraction_provider.extract(ExtractionRequest(payload=data)).text,
            model=data.get("model"),
        )

    @staticmethod
    def _extract_output_text(payload: Mapping[str, object]) -> str:
        """Compatibility helper retained for older callers and tests."""

        return RuleBasedTextExtractionProvider().extract(ExtractionRequest(payload=payload)).text
