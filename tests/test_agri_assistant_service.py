import json

import httpx
import pytest

from app.engines.scoring_types import ScoreStatus
from app.schemas.agri_assistant import AgriAssistantContext, AgriAssistantRankingRow
from app.schemas.explanation import FieldExplanation
from app.schemas.ranking import (
    CropSummary,
    RankFieldsResponse,
    RankedFieldRecommendation,
    ScoreBlockerRead,
    ScoreComponentRead,
)
from app.services.agri_assistant_prompts import (
    build_agri_assistant_system_prompt,
    build_agri_assistant_user_prompt,
)
from app.services.agri_assistant_service import (
    AgriAssistantService,
    LLMAnswer,
    OpenAIResponsesClient,
    build_agri_assistant_context,
)


def _make_component(
    key: str,
    label: str,
    *,
    status: ScoreStatus = ScoreStatus.IDEAL,
    reasons: list[str] | None = None,
) -> ScoreComponentRead:
    return ScoreComponentRead(
        key=key,
        label=label,
        weight=1.0,
        awarded_points=10.0 if status is not ScoreStatus.MISSING else 0.0,
        max_points=10.0,
        status=status,
        reasons=reasons or [],
    )


def _make_ranked_result(
    *,
    rank: int,
    field_id: int,
    field_name: str,
    ranking_score: float,
    total_score: float,
    economic_score: float,
    estimated_profit: float | None,
    strengths: list[str] | None = None,
    weaknesses: list[str] | None = None,
    risks: list[str] | None = None,
    blockers: list[str] | None = None,
    reasons: list[str] | None = None,
    breakdown: dict[str, ScoreComponentRead] | None = None,
) -> RankedFieldRecommendation:
    return RankedFieldRecommendation(
        rank=rank,
        field_id=field_id,
        field_name=field_name,
        total_score=total_score,
        economic_score=economic_score,
        estimated_profit=estimated_profit,
        ranking_score=ranking_score,
        breakdown=breakdown
        or {
            "soil_compatibility": _make_component(
                "soil_compatibility",
                "Soil compatibility",
                reasons=["Soil depth is within the crop rooting requirement."],
            )
        },
        blockers=[
            ScoreBlockerRead(code=f"blocker_{index}", dimension="water", message=message)
            for index, message in enumerate(blockers or [], start=1)
        ],
        reasons=reasons or [],
        explanation=FieldExplanation(
            short_explanation=f"{field_name} summary",
            detailed_explanation=f"{field_name} detailed explanation",
            strengths=strengths or [],
            weaknesses=weaknesses or [],
            risks=risks or [],
        ),
    )


def _make_ranking_response() -> RankFieldsResponse:
    return RankFieldsResponse(
        crop=CropSummary(id=1, crop_name="Corn", scientific_name="Zea mays"),
        total_fields_evaluated=3,
        ranked_results=[
            _make_ranked_result(
                rank=1,
                field_id=101,
                field_name="Field Alpha",
                ranking_score=88.4,
                total_score=86.0,
                economic_score=0.0,
                estimated_profit=None,
                strengths=[
                    "pH is within ideal range.",
                    "Field has irrigation available.",
                ],
                weaknesses=["Drainage is below crop requirement."],
                risks=["Drainage is below crop requirement."],
                blockers=["No irrigation available for a high water-demand crop."],
                reasons=[
                    "pH is within ideal range.",
                    "Field has irrigation available.",
                    "High profit due to high yield and low cost.",
                    "Drainage is below crop requirement.",
                ],
                breakdown={
                    "climate_compatibility": _make_component(
                        "climate_compatibility",
                        "Climate compatibility",
                        status=ScoreStatus.MISSING,
                        reasons=["Climate summary unavailable."],
                    ),
                    "soil_compatibility": _make_component(
                        "soil_compatibility",
                        "Soil compatibility",
                        reasons=["Soil depth is within the crop rooting requirement."],
                    ),
                },
            ),
            _make_ranked_result(
                rank=2,
                field_id=102,
                field_name="Field Beta",
                ranking_score=75.0,
                total_score=72.0,
                economic_score=0.0,
                estimated_profit=None,
                strengths=["Field has irrigation available."],
                weaknesses=["Field slope exceeds the crop tolerance."],
                risks=[],
                blockers=[],
                reasons=["Field has irrigation available."],
            ),
            _make_ranked_result(
                rank=3,
                field_id=103,
                field_name="Field Gamma",
                ranking_score=61.5,
                total_score=60.0,
                economic_score=0.0,
                estimated_profit=1200.0,
                strengths=["Organic matter is acceptable for this crop."],
                weaknesses=["Rainfall insufficient."],
                risks=["Rainfall insufficient."],
                blockers=[],
                reasons=["Organic matter is acceptable for this crop."],
            ),
        ],
    )


def test_build_agri_assistant_context_defaults_to_top_ranked_field_and_preserves_response():
    ranking_response = _make_ranking_response()
    original_payload = ranking_response.model_dump()

    context = build_agri_assistant_context(ranking_response)

    assert context.selected_field_id == 101
    assert context.selected_field_name == "Field Alpha"
    assert context.why_this_field[0] == "Rank #1 with ranking score 88.4/100 and agronomic score 86.0/100."
    assert "pH is within ideal range." in context.why_this_field
    assert any("Field Beta" in alternative for alternative in context.alternatives)
    assert any("Field Gamma" in alternative for alternative in context.alternatives)
    assert context.risks == [
        "No irrigation available for a high water-demand crop.",
        "Drainage is below crop requirement.",
    ]
    assert context.missing_data == [
        "Climate compatibility: Climate summary unavailable.",
        "Estimated profit unavailable from current deterministic inputs.",
    ]
    assert ranking_response.model_dump() == original_payload


def test_prompt_rendering_includes_required_sections_and_normalizes_empty_lists():
    context = AgriAssistantContext(
        crop=CropSummary(id=1, crop_name="Corn", scientific_name="Zea mays"),
        selected_field_id=101,
        selected_field_name="Field Alpha",
        selected_field_rank=1,
        selected_ranking_score=88.4,
        selected_total_score=86.0,
        why_this_field=["Rank #1 with ranking score 88.4/100 and agronomic score 86.0/100."],
        alternatives=[],
        risks=[],
        missing_data=[],
        ranking_table=[
            AgriAssistantRankingRow(
                rank=1,
                field_id=101,
                field_name="Field Alpha",
                ranking_score=88.4,
                total_score=86.0,
                economic_score=0.0,
                estimated_profit=None,
            )
        ],
    )

    system_prompt = build_agri_assistant_system_prompt()
    user_prompt = build_agri_assistant_user_prompt("Why this field?", context)

    assert "deterministic ranking output and explanation output are the only sources of truth" in system_prompt.lower()
    assert "Question:" in user_prompt
    assert "Why this field:" in user_prompt
    assert "Alternatives:" in user_prompt
    assert "Risks:" in user_prompt
    assert "Missing data:" in user_prompt
    assert "Ranking table:" in user_prompt
    assert "No alternative fields are available in the current ranking." in user_prompt
    assert "No significant risks were identified from current deterministic inputs." in user_prompt
    assert "None detected from current deterministic inputs." in user_prompt


class _StubProvider:
    def __init__(self, answer: str, model: str | None = "gpt-test") -> None:
        self.answer = answer
        self.model = model

    def generate_answer(self, *, system_prompt: str, user_prompt: str) -> LLMAnswer:
        assert "deterministic" in system_prompt.lower()
        assert "Field Alpha" in user_prompt
        return LLMAnswer(text=self.answer, model=self.model)


class _ErrorProvider:
    def generate_answer(self, *, system_prompt: str, user_prompt: str) -> LLMAnswer:
        raise httpx.ReadTimeout("timed out")


def test_assistant_service_returns_provider_answer_and_preserves_sections():
    context = build_agri_assistant_context(_make_ranking_response())
    service = AgriAssistantService(provider=_StubProvider("Grounded answer."))

    response = service.ask_agri_assistant("Why this field?", context)

    assert response.answer == "Grounded answer."
    assert response.used_fallback is False
    assert response.model == "gpt-test"
    assert response.why_this_field == context.why_this_field
    assert response.missing_data == context.missing_data


def test_assistant_service_falls_back_when_provider_errors():
    context = build_agri_assistant_context(_make_ranking_response())
    service = AgriAssistantService(provider=_ErrorProvider())

    response = service.ask_agri_assistant("What are the risks?", context)

    assert response.used_fallback is True
    assert response.model is None
    assert "Using the current deterministic ranking data" in response.answer
    assert "Field Alpha" in response.answer


def test_openai_client_posts_expected_payload_and_extracts_text():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "model": "gpt-4.1-mini-2025-04-14",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Grounded answer.",
                            }
                        ],
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    client = OpenAIResponsesClient(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://api.openai.com/v1",
        timeout_seconds=5.0,
        client_factory=lambda: httpx.Client(
            transport=transport,
            base_url="https://api.openai.com/v1",
            headers={
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json",
            },
        ),
    )

    answer = client.generate_answer(system_prompt="system", user_prompt="user")

    assert answer.text == "Grounded answer."
    assert answer.model == "gpt-4.1-mini-2025-04-14"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["authorization"] == "Bearer test-key"
    assert captured["payload"] == {
        "model": "gpt-4.1-mini",
        "store": False,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": "system"}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "user"}],
            },
        ],
    }


def test_openai_client_raises_when_output_text_is_missing():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"model": "gpt-4.1-mini", "output": []})
    )
    client = OpenAIResponsesClient(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://api.openai.com/v1",
        timeout_seconds=5.0,
        client_factory=lambda: httpx.Client(transport=transport, base_url="https://api.openai.com/v1"),
    )

    with pytest.raises(ValueError, match="output_text"):
        client.generate_answer(system_prompt="system", user_prompt="user")
