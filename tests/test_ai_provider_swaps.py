from types import SimpleNamespace

from app.ai.contracts.assistant import LLMAnswer
from app.ai.orchestration.agri_assistant import AgriAssistantOrchestrator
from app.ai.orchestration.ranking import RankingOrchestrator
from app.engines.scoring_types import SuitabilityResult
from app.schemas.agri_assistant import AgriAssistantContext, AgriAssistantRankingRow
from app.schemas.ranking import CropSummary


class _StubSuitabilityProvider:
    def calculate_suitability(self, field_obj, crop, soil_test, climate_summary=None):
        score = 91.0 if field_obj.id == 2 else 54.0
        return SuitabilityResult(
            field_id=field_obj.id,
            crop_id=crop.id,
            soil_test_id=None,
            total_score=score,
            score_breakdown={},
            penalties=[],
            blockers=[],
            reasons=[f"stub score for {field_obj.name}"],
        )


class _PassThroughRankingAugmentationProvider:
    def apply_ranking_scores(self, candidates, *, economics_enabled):
        for candidate in candidates:
            candidate.economic_score = 0.0
            candidate.ranking_score = candidate.scoring_result.total_score


class _StubAssistantProvider:
    def generate_answer(self, *, system_prompt: str, user_prompt: str) -> LLMAnswer:
        assert "deterministic" in system_prompt.lower()
        assert "Field Alpha" in user_prompt
        return LLMAnswer(text="Injected provider answer.", model="stub-assistant")


def test_ranking_orchestrator_supports_provider_swaps_without_business_logic_changes():
    fields = [
        SimpleNamespace(id=1, name="Field Alpha"),
        SimpleNamespace(id=2, name="Field Beta"),
    ]
    crop = SimpleNamespace(id=7)

    ranking = RankingOrchestrator(
        suitability_provider=_StubSuitabilityProvider(),
        ranking_augmentation_provider=_PassThroughRankingAugmentationProvider(),
    ).rank_fields_for_crop(fields, crop, soil_tests={1: None, 2: None})

    assert [entry.field_id for entry in ranking.ranked_fields] == [2, 1]
    assert ranking.ranked_fields[0].reasons == ["stub score for Field Beta"]
    assert ranking.ranked_fields[1].ranking_score == 54.0


def test_agri_assistant_orchestrator_supports_provider_swaps():
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

    response = AgriAssistantOrchestrator(provider=_StubAssistantProvider()).ask_agri_assistant(
        "Why this field?",
        context,
    )

    assert response.answer == "Injected provider answer."
    assert response.used_fallback is False
    assert response.model == "stub-assistant"
