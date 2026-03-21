"""Build reusable climate summaries from normalized weather observations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.schemas.weather_history import ClimateSummary


@dataclass(frozen=True, slots=True)
class ClimateObservation:
    """Normalized daily weather observation used by the climate summary builder."""

    observation_date: date
    min_temp: float | None = None
    max_temp: float | None = None
    avg_temp: float | None = None
    rainfall_mm: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    solar_radiation: float | None = None


class ClimateFeatureBuilder:
    """Build climate summaries from normalized weather observations."""

    def build_summary(
        self,
        observations: Sequence[ClimateObservation],
        *,
        lookback_days: int,
        heat_day_threshold: float,
    ) -> ClimateSummary | None:
        """Return a climate summary for the supplied weather observations."""

        if not observations:
            return None

        sorted_observations = sorted(observations, key=lambda item: item.observation_date)
        avg_temp_values = [
            observation.avg_temp
            if observation.avg_temp is not None
            else _average_from_min_max(observation.min_temp, observation.max_temp)
            for observation in sorted_observations
        ]
        avg_temp_values = [value for value in avg_temp_values if value is not None]
        rainfall_values = [
            float(observation.rainfall_mm or 0.0)
            for observation in sorted_observations
            if observation.rainfall_mm is not None
        ]
        humidity_values = [observation.humidity for observation in sorted_observations if observation.humidity is not None]
        wind_speed_values = [observation.wind_speed for observation in sorted_observations if observation.wind_speed is not None]
        solar_values = [
            observation.solar_radiation
            for observation in sorted_observations
            if observation.solar_radiation is not None
        ]
        min_temp_values = [observation.min_temp for observation in sorted_observations if observation.min_temp is not None]
        max_temp_values = [observation.max_temp for observation in sorted_observations if observation.max_temp is not None]

        weather_record_count = len(sorted_observations)
        coverage_ratio = (
            round(min(weather_record_count / lookback_days, 1.0), 4)
            if lookback_days > 0
            else None
        )

        return ClimateSummary(
            avg_temp=_round_optional(_average(avg_temp_values)),
            min_observed_temp=_round_optional(min(min_temp_values) if min_temp_values else None),
            max_observed_temp=_round_optional(max(max_temp_values) if max_temp_values else None),
            total_rainfall=_round_optional(sum(rainfall_values) if rainfall_values else 0.0),
            avg_humidity=_round_optional(_average(humidity_values)),
            avg_wind_speed=_round_optional(_average(wind_speed_values)),
            avg_solar_radiation=_round_optional(_average(solar_values)),
            frost_days=sum(1 for observation in sorted_observations if (observation.min_temp is not None and observation.min_temp < 0)),
            heat_days=sum(1 for observation in sorted_observations if (observation.max_temp is not None and observation.max_temp > heat_day_threshold)),
            weather_record_count=weather_record_count,
            lookback_days=lookback_days,
            observation_start_date=sorted_observations[0].observation_date,
            observation_end_date=sorted_observations[-1].observation_date,
            coverage_ratio=coverage_ratio,
        )

    @staticmethod
    def observation_from_mapping(
        row: Mapping[str, Any],
        *,
        date_column_name: str = "date",
    ) -> ClimateObservation | None:
        """Normalize a reflected weather row into a climate observation."""

        observation_date = row.get(date_column_name)
        if not isinstance(observation_date, date):
            return None
        return ClimateObservation(
            observation_date=observation_date,
            min_temp=_coerce_optional_float(row.get("min_temp")),
            max_temp=_coerce_optional_float(row.get("max_temp")),
            avg_temp=_coerce_optional_float(row.get("avg_temp")),
            rainfall_mm=_coerce_optional_float(row.get("rainfall_mm")),
            humidity=_coerce_optional_float(row.get("humidity")),
            wind_speed=_coerce_optional_float(row.get("wind_speed")),
            solar_radiation=_coerce_optional_float(row.get("solar_radiation")),
        )


def _average(values: Sequence[float | None]) -> float | None:
    numeric_values = [float(value) for value in values if value is not None]
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _average_from_min_max(min_temp: float | None, max_temp: float | None) -> float | None:
    if min_temp is None or max_temp is None:
        return None
    return (float(min_temp) + float(max_temp)) / 2.0


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_optional(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)
