"""LLM-assisted agronomic explanation service grounded in deterministic ranking data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

import httpx

from app.config import settings
from app.engines.scoring_types import ScoreStatus
from app.schemas.agri_assistant import (
    AgriAssistantContext,
    AgriAssistantRankingRow,
    AgriAssistantResponse,
)
from app.schemas.ranking import RankFieldsResponse, RankedFieldRecommendation
from app.services.agri_assistant_prompts import (
    build_agri_assistant_system_prompt,
    build_agri_assistant_user_prompt,
)


def _dedupe_messages(messages: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for message in messages:
        normalized = message.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _positive_reasons(result: RankedFieldRecommendation) -> list[str]:
    excluded = {
        *result.explanation.weaknesses,
        *result.explanation.risks,
        *(blocker.message for blocker in result.blockers),
    }
    return [reason for reason in result.reasons if reason not in excluded]


def _relative_score_phrase(
    candidate: RankedFieldRecommendation,
    selected: RankedFieldRecommendation,
) -> str:
    if candidate.ranking_score > selected.ranking_score:
        relation = "higher"
    elif candidate.ranking_score < selected.ranking_score:
        relation = "lower"
    else:
        relation = "the same"

    return (
        f"{relation} ranking score than {selected.field_name} "
        f"({candidate.ranking_score:.1f} vs {selected.ranking_score:.1f})"
    )


def _select_ranked_result(
    ranking_response: RankFieldsResponse,
    selected_field_id: int | None,
) -> RankedFieldRecommendation:
    if not ranking_response.ranked_results:
        raise ValueError("No ranked fields available for assistant context")

    if selected_field_id is None:
        return ranking_response.ranked_results[0]

    for result in ranking_response.ranked_results:
        if result.field_id == selected_field_id:
            return result

    raise ValueError("Selected field is not present in the ranked results")


def _build_why_this_field(result: RankedFieldRecommendation) -> list[str]:
    highlights = _dedupe_messages(result.explanation.strengths + _positive_reasons(result))
    why_this_field = [
        (
            f"Rank #{result.rank} with ranking score {result.ranking_score:.1f}/100 "
            f"and agronomic score {result.total_score:.1f}/100."
        )
    ]
    why_this_field.extend(highlights[:3])
    return why_this_field


def _build_alternatives(
    ranking_response: RankFieldsResponse,
    selected: RankedFieldRecommendation,
) -> list[str]:
    alternatives: list[str] = []
    for candidate in ranking_response.ranked_results:
        if candidate.field_id == selected.field_id:
            continue

        upside_candidates = _dedupe_messages(candidate.explanation.strengths + _positive_reasons(candidate))
        strongest_upside = (
            upside_candidates[0]
            if upside_candidates
            else "No standout upside identified from current deterministic inputs."
        )
        tradeoff_candidates = _dedupe_messages(
            [blocker.message for blocker in candidate.blockers]
            + candidate.explanation.risks
            + candidate.explanation.weaknesses
        )
        tradeoff = (
            tradeoff_candidates[0]
            if tradeoff_candidates
            else "No additional drawback surfaced beyond the current score gap."
        )
        alternatives.append(
            (
                f"Rank #{candidate.rank} {candidate.field_name} "
                f"(ranking score {candidate.ranking_score:.1f}/100): strongest upside - {strongest_upside} "
                f"Relative score vs {selected.field_name}: {_relative_score_phrase(candidate, selected)}. "
                f"Main tradeoff - {tradeoff}"
            )
        )
        if len(alternatives) == 2:
            break

    return alternatives


def _build_risks(result: RankedFieldRecommendation) -> list[str]:
    return _dedupe_messages(
        [blocker.message for blocker in result.blockers]
        + result.explanation.risks
        + result.explanation.weaknesses
    )


def _build_missing_data(result: RankedFieldRecommendation) -> list[str]:
    missing_data: list[str] = []
    for component in result.breakdown.values():
        if component.status != ScoreStatus.MISSING:
            continue
        if component.reasons:
            missing_data.append(f"{component.label}: {component.reasons[0]}")
        else:
            missing_data.append(f"{component.label}: missing deterministic input.")

    if result.estimated_profit is None:
        missing_data.append("Estimated profit unavailable from current deterministic inputs.")

    missing_data = _dedupe_messages(missing_data)
    if missing_data:
        return missing_data
    return ["None detected from current deterministic inputs."]


def _build_ranking_table(ranking_response: RankFieldsResponse) -> list[AgriAssistantRankingRow]:
    return [
        AgriAssistantRankingRow(
            rank=result.rank,
            field_id=result.field_id,
            field_name=result.field_name,
            ranking_score=result.ranking_score,
            total_score=result.total_score,
            economic_score=result.economic_score,
            estimated_profit=result.estimated_profit,
        )
        for result in ranking_response.ranked_results
    ]


def build_agri_assistant_context(
    ranking_response: RankFieldsResponse,
    selected_field_id: int | None = None,
) -> AgriAssistantContext:
    """Build deterministic assistant context from ranking and explanation outputs."""

    selected = _select_ranked_result(ranking_response, selected_field_id)
    return AgriAssistantContext(
        crop=ranking_response.crop,
        selected_field_id=selected.field_id,
        selected_field_name=selected.field_name,
        selected_field_rank=selected.rank,
        selected_ranking_score=selected.ranking_score,
        selected_total_score=selected.total_score,
        why_this_field=_build_why_this_field(selected),
        alternatives=_build_alternatives(ranking_response, selected),
        risks=_build_risks(selected),
        missing_data=_build_missing_data(selected),
        ranking_table=_build_ranking_table(ranking_response),
    )


@dataclass(slots=True)
class LLMAnswer:
    """Normalized provider answer returned by the LLM client."""

    text: str
    model: str | None = None


class AgriAssistantProvider(Protocol):
    """Provider contract for agronomic assistant answer generation."""

    def generate_answer(self, *, system_prompt: str, user_prompt: str) -> LLMAnswer:
        """Return a text answer for the supplied prompts."""


class OpenAIResponsesClient:
    """Minimal OpenAI Responses API adapter used by the agronomic assistant."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
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
            text=self._extract_output_text(data),
            model=data.get("model"),
        )

    @staticmethod
    def _extract_output_text(payload: dict[str, object]) -> str:
        output = payload.get("output", [])
        if not isinstance(output, list):
            raise ValueError("OpenAI response did not include an output list.")

        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content", [])
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                if content_item.get("type") == "output_text":
                    text = content_item.get("text")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text.strip())

        if not chunks:
            raise ValueError("OpenAI response did not include any output_text content.")
        return "\n".join(chunks)


class AgriAssistantService:
    """Answer agronomic questions using deterministic context plus optional LLM phrasing."""

    def __init__(self, provider: AgriAssistantProvider | None = None) -> None:
        self.provider = provider or self._build_default_provider()

    def ask_agri_assistant(
        self,
        question: str,
        context: AgriAssistantContext,
    ) -> AgriAssistantResponse:
        """Return a grounded answer while keeping deterministic data authoritative."""

        if self.provider is None:
            return self._fallback_response(question, context)

        system_prompt = build_agri_assistant_system_prompt()
        user_prompt = build_agri_assistant_user_prompt(question, context)

        try:
            provider_answer = self.provider.generate_answer(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception:
            return self._fallback_response(question, context)

        answer_text = provider_answer.text.strip()
        if not answer_text:
            return self._fallback_response(question, context)

        return AgriAssistantResponse(
            selected_field_id=context.selected_field_id,
            selected_field_name=context.selected_field_name,
            answer=answer_text,
            why_this_field=context.why_this_field,
            alternatives=context.alternatives,
            risks=context.risks,
            missing_data=context.missing_data,
            used_fallback=False,
            model=provider_answer.model,
        )

    def _build_default_provider(self) -> AgriAssistantProvider | None:
        if not settings.OPENAI_API_KEY:
            return None

        return OpenAIResponsesClient(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            base_url=settings.OPENAI_BASE_URL,
            timeout_seconds=settings.OPENAI_TIMEOUT_SECONDS,
        )

    def _fallback_response(
        self,
        question: str,
        context: AgriAssistantContext,
    ) -> AgriAssistantResponse:
        return AgriAssistantResponse(
            selected_field_id=context.selected_field_id,
            selected_field_name=context.selected_field_name,
            answer=self._render_fallback_answer(question, context),
            why_this_field=context.why_this_field,
            alternatives=context.alternatives,
            risks=context.risks,
            missing_data=context.missing_data,
            used_fallback=True,
            model=None,
        )

    @staticmethod
    def _render_fallback_answer(
        question: str,
        context: AgriAssistantContext,
    ) -> str:
        _ = question
        reasons = "; ".join(context.why_this_field[:3])
        risks = (
            "; ".join(context.risks[:2])
            if context.risks
            else "No significant risks were identified from current deterministic inputs."
        )
        alternatives = (
            context.alternatives[0]
            if context.alternatives
            else "No alternative fields are available in the current ranking."
        )
        missing_data = "; ".join(context.missing_data[:2])

        return (
            f"Using the current deterministic ranking data, {context.selected_field_name} is "
            f"rank #{context.selected_field_rank} for {context.crop.crop_name}. "
            f"Why this field: {reasons} "
            f"Risks: {risks} "
            f"Best alternative: {alternatives} "
            f"Missing data: {missing_data}"
        )


def ask_agri_assistant(
    question: str,
    context: AgriAssistantContext,
    *,
    provider: AgriAssistantProvider | None = None,
) -> AgriAssistantResponse:
    """Convenience wrapper that instantiates the default assistant service."""

    return AgriAssistantService(provider=provider).ask_agri_assistant(question, context)
