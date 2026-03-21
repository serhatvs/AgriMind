import asyncio

import pytest

from app import main
from app.ai.providers.ml.xgboost_yield import XGBoostYieldPredictionProvider
from app.ai.providers.rule_based.explanation import RuleBasedExplanationProvider
from app.ai.providers.rule_based.extraction import RuleBasedTextExtractionProvider
from app.ai.providers.rule_based.ranking_augmentation import RuleBasedRankingAugmentationProvider
from app.ai.providers.rule_based.risk import RuleBasedRiskScoringProvider
from app.ai.providers.rule_based.suitability import RuleBasedSuitabilityProvider
from app.ai.providers.stub.explanation import DeterministicExplanationProvider
from app.ai.providers.stub.extraction import StubExtractionProvider
from app.ai.providers.stub.risk import StubRiskScorer
from app.ai.providers.stub.yield_prediction import DeterministicYieldPredictor, StubYieldPredictor
from app.ai.registry import AIProviderRegistry
from app.config import Settings, settings


def test_ai_registry_resolves_default_providers(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    registry = AIProviderRegistry(settings)

    assert isinstance(registry.get_suitability_provider(), RuleBasedSuitabilityProvider)
    assert isinstance(registry.get_risk_provider(), RuleBasedRiskScoringProvider)
    assert isinstance(registry.get_explanation_provider(), RuleBasedExplanationProvider)
    assert isinstance(registry.get_ranking_augmentation_provider(), RuleBasedRankingAugmentationProvider)
    assert isinstance(registry.get_yield_prediction_provider(db=None), XGBoostYieldPredictionProvider)
    assert isinstance(registry.get_extraction_provider(), RuleBasedTextExtractionProvider)
    assert registry.get_assistant_provider() is None


def test_ai_registry_fails_fast_for_unknown_provider(monkeypatch):
    monkeypatch.setattr(settings, "AI_SUITABILITY_PROVIDER", "does-not-exist")

    registry = AIProviderRegistry(settings)

    with pytest.raises(ValueError, match="Unknown suitability provider"):
        registry.validate_configuration()


def test_ai_registry_supports_factory_overrides(monkeypatch):
    stub_provider = object()
    monkeypatch.setattr(settings, "AI_SUITABILITY_PROVIDER", "stub")

    registry = AIProviderRegistry(
        settings,
        suitability_factories={"stub": lambda **_: stub_provider},
    )

    assert registry.get_suitability_provider() is stub_provider


def test_ai_registry_resolves_normalized_short_provider_settings():
    config = Settings(
        _env_file=None,
        AI_SUITABILITY_PROVIDER="rule_based",
        AI_RANKING_AUGMENTATION_PROVIDER="rule_based",
        AI_ASSISTANT_PROVIDER="openai",
        YIELD_PROVIDER="stub",
        EXPLANATION_PROVIDER="deterministic",
        RISK_PROVIDER="stub",
        EXTRACTION_PROVIDER="stub",
        OPENAI_API_KEY=None,
    )

    registry = AIProviderRegistry(config)

    assert isinstance(registry.get_yield_prediction_provider(db=None), StubYieldPredictor)
    assert isinstance(registry.get_explanation_provider(), DeterministicExplanationProvider)
    assert isinstance(registry.get_risk_provider(), StubRiskScorer)
    assert isinstance(registry.get_extraction_provider(), StubExtractionProvider)


@pytest.mark.parametrize(
    ("field_name", "provider_id", "match"),
    [
        ("AI_YIELD_PROVIDER", "does-not-exist", "Unknown yield provider 'does-not-exist'"),
        ("AI_EXPLANATION_PROVIDER", "does-not-exist", "Unknown explanation provider 'does-not-exist'"),
        ("AI_RISK_PROVIDER", "does-not-exist", "Unknown risk provider 'does-not-exist'"),
        ("AI_EXTRACTION_PROVIDER", "does-not-exist", "Unknown extraction provider 'does-not-exist'"),
    ],
)
def test_ai_registry_fails_fast_for_unknown_canonical_provider_ids(
    monkeypatch,
    field_name,
    provider_id,
    match,
):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, field_name, provider_id)

    registry = AIProviderRegistry(settings)

    with pytest.raises(ValueError, match=match):
        registry.validate_configuration()


def test_ai_registry_lists_registered_provider_ids():
    registry = AIProviderRegistry(settings)

    assert registry.available_provider_ids("yield") == ("deterministic", "stub", "xgboost")
    assert registry.available_provider_ids("explanation") == ("deterministic", "rule_based")
    assert registry.available_provider_ids("risk") == ("rule_based", "stub")
    assert registry.available_provider_ids("extraction") == ("rule_based", "stub")


def test_ai_registry_supports_deterministic_yield_provider_alias():
    config = Settings(
        _env_file=None,
        YIELD_PROVIDER="deterministic",
        OPENAI_API_KEY=None,
    )

    registry = AIProviderRegistry(config)

    assert isinstance(registry.get_yield_prediction_provider(db=None), DeterministicYieldPredictor)


def test_main_lifespan_validates_ai_provider_configuration(monkeypatch):
    class _RecordingRegistry:
        def __init__(self) -> None:
            self.calls = 0

        def validate_configuration(self) -> None:
            self.calls += 1

    connection_checks = {"count": 0}
    engine_disposals = {"count": 0}

    registry = _RecordingRegistry()
    monkeypatch.setattr(main, "get_ai_provider_registry", lambda: registry)
    monkeypatch.setattr(
        main,
        "check_database_connection",
        lambda: connection_checks.__setitem__("count", connection_checks["count"] + 1),
    )
    monkeypatch.setattr(
        main,
        "dispose_database_engine",
        lambda: engine_disposals.__setitem__("count", engine_disposals["count"] + 1),
    )

    async def _exercise() -> None:
        async with main.lifespan(main.app):
            pass

    asyncio.run(_exercise())

    assert registry.calls == 1
    assert connection_checks["count"] == 1
    assert engine_disposals["count"] == 1
