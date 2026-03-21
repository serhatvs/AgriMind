"""Application service for ranking fields for a selected crop."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.contracts.metadata import AITraceMetadata
from app.ai.contracts.explanation import ExplanationOutput, adapt_explanation_output
from app.ai.features.explanation import build_explanation_input
from app.ai.orchestration.ranking import RankedFieldResultInternal, RankingOrchestrator
from app.ai.registry import AIProviderRegistry, get_ai_provider_registry
from app.schemas.ai_metadata import AITraceMetadataRead
from app.schemas.ranking import (
    CropSummary,
    RankFieldsResponse,
    RankedFieldProviderMetadata,
    RankedFieldRecommendation,
    ScoreBlockerRead,
    ScoreComponentRead,
)
from app.services.crop_service import get_crop
from app.services.economic_service import EconomicService
from app.services.field_service import get_all_fields, get_fields_by_ids
from app.services.soil_service import get_latest_soil_test_for_field
from app.services.weather_service import WeatherService


def _serialize_breakdown(breakdown: dict[str, object]) -> dict[str, ScoreComponentRead]:
    return {
        key: ScoreComponentRead.model_validate(component)
        for key, component in breakdown.items()
    }


def _serialize_blockers(blockers: list[object]) -> list[ScoreBlockerRead]:
    return [ScoreBlockerRead.model_validate(blocker) for blocker in blockers]


def _serialize_trace_metadata(metadata: AITraceMetadata) -> AITraceMetadataRead:
    normalized = metadata.normalized()
    return AITraceMetadataRead(
        provider_name=normalized.provider_name,
        provider_version=normalized.provider_version,
        generated_at=normalized.generated_at,
        confidence=normalized.confidence,
        debug_info=normalized.debug_info,
    )


def _serialize_provider_metadata(
    entry: RankedFieldResultInternal,
    *,
    explanation_output: ExplanationOutput,
    registry: AIProviderRegistry,
) -> RankedFieldProviderMetadata:
    yield_prediction = entry.yield_prediction
    generated_at = explanation_output.generated_at
    risk_metadata_payload = (explanation_output.debug_info or {}).get("risk_provider_metadata")
    risk_provider_metadata = None
    if isinstance(risk_metadata_payload, dict):
        risk_generated_at = risk_metadata_payload.get("generated_at")
        if isinstance(risk_generated_at, str):
            try:
                parsed_risk_generated_at = datetime.fromisoformat(risk_generated_at)
            except ValueError:
                parsed_risk_generated_at = generated_at
        else:
            parsed_risk_generated_at = generated_at
        risk_provider_metadata = _serialize_trace_metadata(
            AITraceMetadata(
                provider_name=str(risk_metadata_payload.get("provider_name", registry.settings.AI_RISK_PROVIDER)),
                provider_version=(
                    str(risk_metadata_payload["provider_version"])
                    if risk_metadata_payload.get("provider_version") is not None
                    else None
                ),
                generated_at=parsed_risk_generated_at,
                confidence=(
                    float(risk_metadata_payload["confidence"])
                    if risk_metadata_payload.get("confidence") is not None
                    else None
                ),
                debug_info=(
                    risk_metadata_payload.get("debug_info")
                    if isinstance(risk_metadata_payload.get("debug_info"), dict)
                    else None
                ),
            )
        )
    return RankedFieldProviderMetadata(
        agronomic_provider=_serialize_trace_metadata(
            AITraceMetadata(
                provider_name=registry.settings.AI_SUITABILITY_PROVIDER,
                provider_version=None,
                generated_at=generated_at,
                confidence=None,
                debug_info={"total_score": entry.agronomic_score},
            )
        ),
        ranking_provider=_serialize_trace_metadata(
            AITraceMetadata(
                provider_name=registry.settings.AI_RANKING_AUGMENTATION_PROVIDER,
                provider_version=None,
                generated_at=generated_at,
                confidence=entry.confidence_score,
                debug_info={
                    "ranking_score": entry.ranking_score,
                    "economic_score": entry.economic_score,
                },
            )
        ),
        explanation_provider=_serialize_trace_metadata(explanation_output.metadata),
        yield_provider=(
            _serialize_trace_metadata(
                AITraceMetadata(
                    provider_name=yield_prediction.training_source,
                    provider_version=yield_prediction.model_version,
                    generated_at=yield_prediction.metadata.generated_at,
                    confidence=yield_prediction.confidence_score,
                    debug_info=yield_prediction.metadata.debug_info,
                )
            )
            if yield_prediction is not None
            else None
        ),
        risk_provider=risk_provider_metadata
        or _serialize_trace_metadata(
            AITraceMetadata(
                provider_name=registry.settings.AI_RISK_PROVIDER,
                provider_version=None,
                generated_at=generated_at,
                confidence=explanation_output.confidence,
                debug_info={"risk_count": len(explanation_output.risks)},
            )
        ),
    )


def _serialize_ranking_metadata(
    entry: RankedFieldResultInternal,
    *,
    explanation_output: ExplanationOutput,
    registry: AIProviderRegistry,
) -> AITraceMetadataRead:
    return _serialize_trace_metadata(
        AITraceMetadata(
            provider_name=registry.settings.AI_RANKING_AUGMENTATION_PROVIDER,
            provider_version=None,
            generated_at=datetime.now(timezone.utc),
            confidence=entry.confidence_score or explanation_output.confidence,
            debug_info={
                "agronomic_provider": registry.settings.AI_SUITABILITY_PROVIDER,
                "explanation_provider": explanation_output.provider_name,
                "has_yield_prediction": entry.yield_prediction is not None,
            },
        )
    )


def _serialize_ranked_result(
    entry: RankedFieldResultInternal,
    *,
    explanation_provider,
    registry: AIProviderRegistry,
) -> RankedFieldRecommendation:
    explanation_output = explanation_provider.explain(build_explanation_input(entry))
    return RankedFieldRecommendation(
        rank=entry.rank,
        field_id=entry.field_id,
        field_name=entry.field_name,
        total_score=entry.total_score,
        agronomic_score=entry.agronomic_score,
        climate_score=entry.climate_score,
        economic_score=entry.economic_score,
        risk_score=entry.risk_score,
        confidence_score=entry.confidence_score,
        estimated_profit=entry.estimated_profit,
        predicted_yield=entry.predicted_yield,
        predicted_yield_range=entry.predicted_yield_range,
        ranking_score=entry.ranking_score,
        strengths=explanation_output.strengths,
        weaknesses=explanation_output.weaknesses,
        risks=explanation_output.risks,
        breakdown=_serialize_breakdown(entry.breakdown),
        blockers=_serialize_blockers(entry.blockers),
        reasons=entry.reasons,
        metadata=_serialize_ranking_metadata(
            entry,
            explanation_output=explanation_output,
            registry=registry,
        ),
        provider_metadata=_serialize_provider_metadata(
            entry,
            explanation_output=explanation_output,
            registry=registry,
        ),
        explanation=adapt_explanation_output(explanation_output),
    )


def _load_fields_for_ranking(db: Session, field_ids: list[int] | None) -> list[object]:
    if field_ids is None:
        return get_all_fields(db)
    return get_fields_by_ids(db, field_ids)


def get_ranked_fields_response(
    db: Session,
    crop_id: int,
    top_n: int | None = 5,
    field_ids: list[int] | None = None,
) -> RankFieldsResponse:
    """Build the ranking response payload for the POST /rank-fields endpoint."""

    crop = get_crop(db, crop_id)
    if crop is None:
        raise ValueError(f"Crop with id {crop_id} not found")

    fields = _load_fields_for_ranking(db, field_ids)
    if not fields:
        if field_ids is None:
            raise ValueError("No fields found for ranking")
        raise ValueError("No fields found for the provided field filter")

    soil_lookup = {
        field.id: get_latest_soil_test_for_field(db, field.id)
        for field in fields
    }
    weather_service = WeatherService(db)
    climate_lookup = {
        field.id: weather_service.get_climate_summary(field.id)
        for field in fields
    }
    economic_service = EconomicService(db)
    economic_lookup = {
        field.id: economic_service.calculate_profit(
            field,
            crop,
            soil_test=soil_lookup[field.id],
            climate_summary=climate_lookup[field.id],
        )
        for field in fields
    }
    registry = get_ai_provider_registry()
    explanation_provider = registry.get_explanation_provider()
    ranking = RankingOrchestrator(
        suitability_provider=registry.get_suitability_provider(),
        ranking_augmentation_provider=registry.get_ranking_augmentation_provider(),
    ).rank_fields_for_crop(
        fields,
        crop,
        soil_lookup,
        top_n=top_n,
        climate_summaries=climate_lookup,
        economic_assessments=economic_lookup,
    )

    return RankFieldsResponse(
        crop=CropSummary.model_validate(crop),
        total_fields_evaluated=len(fields),
        ranked_results=[
            _serialize_ranked_result(
                entry,
                explanation_provider=explanation_provider,
                registry=registry,
            )
            for entry in ranking.ranked_fields
        ],
    )
