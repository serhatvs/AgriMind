"""Registry and provider resolution for the pluggable AI layer."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.ai.contracts.assistant import AssistantAnswerProvider
from app.ai.contracts.explanation import ExplanationProvider
from app.ai.contracts.extraction import ExtractionProvider
from app.ai.contracts.ranking import RankingAugmentationProvider
from app.ai.contracts.risk import RiskScorer
from app.ai.contracts.suitability import SuitabilityProvider
from app.ai.contracts.yield_prediction import YieldPredictor
from app.ai.providers.llm.openai_responses import OpenAIResponsesClient
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
from app.config import Settings, settings

ProviderFactory = Callable[..., Any]


class AIProviderRegistry:
    """Resolve AI providers from canonical settings while supporting test overrides."""

    def __init__(
        self,
        settings_obj: Settings = settings,
        *,
        suitability_factories: dict[str, ProviderFactory] | None = None,
        risk_factories: dict[str, ProviderFactory] | None = None,
        explanation_factories: dict[str, ProviderFactory] | None = None,
        ranking_augmentation_factories: dict[str, ProviderFactory] | None = None,
        yield_factories: dict[str, ProviderFactory] | None = None,
        assistant_factories: dict[str, ProviderFactory] | None = None,
        extraction_factories: dict[str, ProviderFactory] | None = None,
    ) -> None:
        self.settings = settings_obj
        self._suitability_factories = {
            "rule_based": lambda **_: RuleBasedSuitabilityProvider(),
            **(suitability_factories or {}),
        }
        self._risk_factories = {
            "rule_based": lambda **_: RuleBasedRiskScoringProvider(),
            "stub": lambda **_: StubRiskScorer(),
            **(risk_factories or {}),
        }
        self._explanation_factories = {
            "rule_based": lambda **kwargs: RuleBasedExplanationProvider(
                risk_provider=kwargs.get("risk_provider"),
            ),
            "deterministic": lambda **kwargs: DeterministicExplanationProvider(
                risk_provider=kwargs.get("risk_provider"),
            ),
            **(explanation_factories or {}),
        }
        self._ranking_augmentation_factories = {
            "rule_based": lambda **_: RuleBasedRankingAugmentationProvider(),
            **(ranking_augmentation_factories or {}),
        }
        self._yield_factories = {
            "deterministic": lambda **kwargs: DeterministicYieldPredictor(
                model_dir=kwargs.get("model_dir"),
            ),
            "xgboost": lambda **kwargs: XGBoostYieldPredictionProvider(
                db=kwargs.get("db"),
                model_dir=kwargs.get("model_dir"),
                fallback_predictor=DeterministicYieldPredictor(
                    model_dir=kwargs.get("model_dir"),
                ),
            ),
            "stub": lambda **kwargs: StubYieldPredictor(
                model_dir=kwargs.get("model_dir"),
            ),
            **(yield_factories or {}),
        }
        self._assistant_factories = {
            "openai": lambda **kwargs: self._build_openai_provider(
                extraction_provider=kwargs.get("extraction_provider"),
                client_factory=kwargs.get("client_factory"),
            ),
            "none": lambda **_: None,
            **(assistant_factories or {}),
        }
        self._extraction_factories = {
            "rule_based": lambda **_: RuleBasedTextExtractionProvider(),
            "stub": lambda **_: StubExtractionProvider(),
            **(extraction_factories or {}),
        }
        self._factories_by_capability = {
            "suitability": self._suitability_factories,
            "risk": self._risk_factories,
            "explanation": self._explanation_factories,
            "ranking augmentation": self._ranking_augmentation_factories,
            "yield": self._yield_factories,
            "assistant": self._assistant_factories,
            "extraction": self._extraction_factories,
        }

    def available_provider_ids(self, capability: str) -> tuple[str, ...]:
        """Return the registered provider ids for a capability."""

        factories = self._factories_by_capability.get(capability)
        if factories is None:
            known_capabilities = ", ".join(sorted(self._factories_by_capability))
            raise ValueError(
                f"Unknown provider capability '{capability}'. Available capabilities: {known_capabilities}"
            )
        return tuple(sorted(factories))

    def _resolve_factory(
        self,
        capability: str,
        provider_id: str,
        factories: dict[str, ProviderFactory],
    ) -> ProviderFactory:
        factory = factories.get(provider_id)
        if factory is None:
            available = ", ".join(self.available_provider_ids(capability))
            raise ValueError(
                f"Unknown {capability} provider '{provider_id}'. Available providers: {available}"
            )
        return factory

    def _build_provider(
        self,
        capability: str,
        provider_id: str,
        factories: dict[str, ProviderFactory],
        **kwargs: object,
    ) -> object:
        factory = self._resolve_factory(capability, provider_id, factories)
        return factory(**kwargs)

    def get_suitability_provider(self) -> SuitabilityProvider:
        return self._build_provider(
            "suitability",
            self.settings.AI_SUITABILITY_PROVIDER,
            self._suitability_factories,
        )

    def get_risk_provider(self) -> RiskScorer:
        return self._build_provider(
            "risk",
            self.settings.AI_RISK_PROVIDER,
            self._risk_factories,
        )

    def get_explanation_provider(self) -> ExplanationProvider:
        return self._build_provider(
            "explanation",
            self.settings.AI_EXPLANATION_PROVIDER,
            self._explanation_factories,
            risk_provider=self.get_risk_provider(),
        )

    def get_ranking_augmentation_provider(self) -> RankingAugmentationProvider:
        return self._build_provider(
            "ranking augmentation",
            self.settings.AI_RANKING_AUGMENTATION_PROVIDER,
            self._ranking_augmentation_factories,
        )

    def get_yield_prediction_provider(
        self,
        *,
        db,
        model_dir: str | Path | None = None,
    ) -> YieldPredictor:
        return self._build_provider(
            "yield",
            self.settings.AI_YIELD_PROVIDER,
            self._yield_factories,
            db=db,
            model_dir=model_dir or self.settings.YIELD_MODEL_PATH,
        )

    def get_extraction_provider(self) -> ExtractionProvider:
        return self._build_provider(
            "extraction",
            self.settings.AI_EXTRACTION_PROVIDER,
            self._extraction_factories,
        )

    def get_assistant_provider(
        self,
        *,
        extraction_provider: ExtractionProvider | None = None,
        client_factory: Callable[..., object] | None = None,
    ) -> AssistantAnswerProvider | None:
        return self._build_provider(
            "assistant",
            self.settings.AI_ASSISTANT_PROVIDER,
            self._assistant_factories,
            extraction_provider=extraction_provider or self.get_extraction_provider(),
            client_factory=client_factory,
        )

    def validate_configuration(self) -> None:
        """Fail fast when provider ids are unknown or factories cannot be resolved."""

        self.get_suitability_provider()
        self.get_risk_provider()
        self.get_explanation_provider()
        self.get_ranking_augmentation_provider()
        self.get_yield_prediction_provider(db=None)
        self.get_extraction_provider()
        self.get_assistant_provider()

    def _build_openai_provider(
        self,
        *,
        extraction_provider: ExtractionProvider | None = None,
        client_factory: Callable[..., object] | None = None,
    ) -> AssistantAnswerProvider | None:
        if not self.settings.OPENAI_API_KEY:
            return None

        return OpenAIResponsesClient(
            api_key=self.settings.OPENAI_API_KEY,
            model=self.settings.OPENAI_MODEL,
            base_url=self.settings.OPENAI_BASE_URL,
            timeout_seconds=self.settings.OPENAI_TIMEOUT_SECONDS,
            extraction_provider=extraction_provider,
            client_factory=client_factory,
        )


def get_ai_provider_registry(settings_obj: Settings = settings) -> AIProviderRegistry:
    """Return a provider registry bound to the supplied settings object."""

    return AIProviderRegistry(settings_obj=settings_obj)
