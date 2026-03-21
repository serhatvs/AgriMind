"""Provider-based orchestration for grounded agronomic assistant answers."""

from __future__ import annotations

from collections.abc import Iterable

from app.ai.contracts.assistant import AssistantAnswerProvider
from app.ai.providers.llm.prompt_builder import (
    build_agri_assistant_system_prompt,
    build_agri_assistant_user_prompt,
)
from app.ai.registry import get_ai_provider_registry
from app.engines.scoring_types import ScoreStatus
from app.schemas.agri_assistant import (
    AgriAssistantContext,
    AgriAssistantRankingRow,
    AgriAssistantResponse,
)
from app.schemas.ranking import RankFieldsResponse, RankedFieldRecommendation


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


class AgriAssistantOrchestrator:
    """Answer agronomic questions using deterministic context plus optional LLM phrasing."""

    def __init__(self, provider: AssistantAnswerProvider | None = None) -> None:
        self.provider = provider or get_ai_provider_registry().get_assistant_provider()

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
    provider: AssistantAnswerProvider | None = None,
) -> AgriAssistantResponse:
    """Compatibility wrapper that uses the default assistant orchestrator."""

    return AgriAssistantOrchestrator(provider=provider).ask_agri_assistant(question, context)
