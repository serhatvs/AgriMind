"""Rule-based climate compatibility scoring provider."""

from __future__ import annotations

from dataclasses import dataclass

from app.engines.scoring_config import SuitabilityScoringConfig
from app.engines.scoring_types import ScoreComponent, ScoreStatus
from app.models.crop_profile import CropProfile
from app.schemas.weather_history import ClimateSummary


@dataclass(frozen=True, slots=True)
class _ClimateFactorScore:
    """Internal normalized factor score for climate compatibility."""

    ratio: float
    status: ScoreStatus
    reasons: list[str]


def _round_points(value: float) -> float:
    return round(value, 2)


def _clamp_ratio(value: float) -> float:
    return max(0.0, min(value, 1.0))


def _dedupe_messages(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for message in messages:
        if message not in seen:
            seen.add(message)
            ordered.append(message)
    return ordered


def _status_from_ratio(ratio: float) -> ScoreStatus:
    if ratio >= 0.95:
        return ScoreStatus.IDEAL
    if ratio >= 0.6:
        return ScoreStatus.ACCEPTABLE
    return ScoreStatus.LIMITED


def _missing_factor(message: str, config: SuitabilityScoringConfig) -> _ClimateFactorScore:
    return _ClimateFactorScore(
        ratio=config.thresholds.missing_climate_ratio,
        status=ScoreStatus.MISSING,
        reasons=[message],
    )


def _score_temperature(
    crop: CropProfile,
    climate_summary: ClimateSummary,
    config: SuitabilityScoringConfig,
) -> _ClimateFactorScore:
    if crop.optimal_temp_min_c is None or crop.optimal_temp_max_c is None:
        return _missing_factor("Crop temperature requirement is not configured.", config)

    value = climate_summary.avg_temp
    ideal_min = crop.optimal_temp_min_c
    ideal_max = crop.optimal_temp_max_c
    acceptable_min = ideal_min - config.thresholds.temperature_buffer_c
    acceptable_max = ideal_max + config.thresholds.temperature_buffer_c

    if ideal_min <= value <= ideal_max:
        return _ClimateFactorScore(1.0, ScoreStatus.IDEAL, ["Temperature within optimal range."])

    if acceptable_min <= value <= acceptable_max:
        if value < ideal_min:
            span = ideal_min - acceptable_min
            ratio = (value - acceptable_min) / span if span > 0 else 1.0
        else:
            span = acceptable_max - ideal_max
            ratio = (acceptable_max - value) / span if span > 0 else 1.0
        return _ClimateFactorScore(
            _clamp_ratio(ratio),
            ScoreStatus.ACCEPTABLE,
            ["Temperature is outside the optimal range but still acceptable."],
        )

    return _ClimateFactorScore(0.0, ScoreStatus.LIMITED, ["Temperature is outside the acceptable range."])


def _score_rainfall(
    crop: CropProfile,
    climate_summary: ClimateSummary,
    config: SuitabilityScoringConfig,
) -> _ClimateFactorScore:
    requirement = crop.rainfall_requirement_mm
    if requirement is None or requirement <= 0:
        return _missing_factor("Crop rainfall requirement is not configured.", config)

    actual = climate_summary.total_rainfall
    ideal_min = requirement * config.thresholds.rainfall_ideal_lower_ratio
    ideal_max = requirement * config.thresholds.rainfall_ideal_upper_ratio
    acceptable_min = requirement * config.thresholds.rainfall_acceptable_lower_ratio
    acceptable_max = requirement * config.thresholds.rainfall_acceptable_upper_ratio

    if ideal_min <= actual <= ideal_max:
        return _ClimateFactorScore(1.0, ScoreStatus.IDEAL, ["Rainfall is within the target range."])

    if acceptable_min <= actual <= acceptable_max:
        if actual < ideal_min:
            span = ideal_min - acceptable_min
            ratio = (actual - acceptable_min) / span if span > 0 else 1.0
            reason = "Rainfall insufficient."
        else:
            span = acceptable_max - ideal_max
            ratio = (acceptable_max - actual) / span if span > 0 else 1.0
            reason = "Rainfall exceeds the ideal target but remains tolerable."
        return _ClimateFactorScore(_clamp_ratio(ratio), ScoreStatus.ACCEPTABLE, [reason])

    if actual < acceptable_min:
        return _ClimateFactorScore(0.0, ScoreStatus.LIMITED, ["Rainfall insufficient."])
    return _ClimateFactorScore(0.0, ScoreStatus.LIMITED, ["Rainfall exceeds the acceptable range."])


def _score_frost(
    crop: CropProfile,
    climate_summary: ClimateSummary,
    config: SuitabilityScoringConfig,
) -> _ClimateFactorScore:
    tolerance = crop.frost_tolerance_days
    if tolerance is None:
        return _missing_factor("Crop frost tolerance is not configured.", config)

    actual = climate_summary.frost_days
    if actual <= tolerance:
        return _ClimateFactorScore(1.0, ScoreStatus.IDEAL, ["Frost exposure is within crop tolerance."])

    if tolerance <= 0:
        return _ClimateFactorScore(0.0, ScoreStatus.LIMITED, ["High frost risk detected."])

    zero_threshold = tolerance * config.thresholds.frost_tolerance_partial_multiplier
    if actual >= zero_threshold:
        return _ClimateFactorScore(0.0, ScoreStatus.LIMITED, ["High frost risk detected."])

    ratio = (zero_threshold - actual) / (zero_threshold - tolerance)
    return _ClimateFactorScore(_clamp_ratio(ratio), ScoreStatus.ACCEPTABLE, ["High frost risk detected."])


def _score_heat(
    crop: CropProfile,
    climate_summary: ClimateSummary,
    config: SuitabilityScoringConfig,
) -> _ClimateFactorScore:
    tolerance = crop.heat_tolerance_days
    if tolerance is None:
        return _missing_factor("Crop heat tolerance is not configured.", config)

    actual = climate_summary.heat_days
    if actual <= tolerance:
        return _ClimateFactorScore(1.0, ScoreStatus.IDEAL, ["Heat exposure is within crop tolerance."])

    if tolerance <= 0:
        return _ClimateFactorScore(0.0, ScoreStatus.LIMITED, ["High heat risk detected."])

    zero_threshold = tolerance * config.thresholds.heat_tolerance_partial_multiplier
    if actual >= zero_threshold:
        return _ClimateFactorScore(0.0, ScoreStatus.LIMITED, ["High heat risk detected."])

    ratio = (zero_threshold - actual) / (zero_threshold - tolerance)
    return _ClimateFactorScore(_clamp_ratio(ratio), ScoreStatus.ACCEPTABLE, ["High heat risk detected."])


def _component_status(factors: list[_ClimateFactorScore], weighted_ratio: float) -> ScoreStatus:
    if any(factor.status is ScoreStatus.LIMITED for factor in factors):
        return _status_from_ratio(weighted_ratio)
    if any(factor.status is ScoreStatus.MISSING for factor in factors):
        return ScoreStatus.MISSING
    return _status_from_ratio(weighted_ratio)


def score_climate_compatibility(
    crop: CropProfile,
    climate_summary: ClimateSummary | None,
    config: SuitabilityScoringConfig,
) -> ScoreComponent:
    """Score climate compatibility from the aggregated field climate summary."""

    key = "climate_compatibility"
    label = "Climate compatibility"
    weight = config.climate_compatibility

    if climate_summary is None:
        return ScoreComponent(
            key=key,
            label=label,
            weight=weight,
            awarded_points=_round_points(weight * config.thresholds.missing_climate_ratio),
            max_points=weight,
            status=ScoreStatus.MISSING,
            reasons=["Climate summary is unavailable; awarded a conservative partial climate score."],
        )

    temperature = _score_temperature(crop, climate_summary, config)
    rainfall = _score_rainfall(crop, climate_summary, config)
    frost = _score_frost(crop, climate_summary, config)
    heat = _score_heat(crop, climate_summary, config)
    factors = [temperature, rainfall, frost, heat]

    weighted_ratio = (
        temperature.ratio * config.climate_subweights.temperature
        + rainfall.ratio * config.climate_subweights.rainfall
        + frost.ratio * config.climate_subweights.frost
        + heat.ratio * config.climate_subweights.heat
    )

    return ScoreComponent(
        key=key,
        label=label,
        weight=weight,
        awarded_points=_round_points(weight * weighted_ratio),
        max_points=weight,
        status=_component_status(factors, weighted_ratio),
        reasons=_dedupe_messages(
            [
                *temperature.reasons,
                *rainfall.reasons,
                *frost.reasons,
                *heat.reasons,
            ]
        ),
    )
