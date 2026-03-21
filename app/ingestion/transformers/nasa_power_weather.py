"""Transformer that maps NASA POWER daily responses into weather_history records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
import logging
import math
from typing import Any

from app.ingestion.transformers.base import PayloadTransformer
from app.ingestion.types import NormalizedRecord, RawPayloadEnvelope
from app.models.ingestion import DataSource, IngestionRun
from app.services.errors import ServiceValidationError


logger = logging.getLogger(__name__)


class NASAPowerWeatherTransformer(PayloadTransformer):
    """Transform a NASA POWER response into daily weather_history-style rows."""

    PARAMETER_TO_FIELD_MAP = {
        "T2M_MIN": ("min_temp",),
        "T2M_MAX": ("max_temp",),
        "T2M": ("avg_temp",),
        "PRECTOTCORR": ("rainfall_mm",),
        "PRECTOT": ("rainfall_mm",),
        "RH2M": ("humidity",),
        "WS2M": ("wind_speed",),
        "ALLSKY_SFC_SW_DWN": ("solar_radiation",),
    }
    FIELD_PARAMETER_PRIORITY = {
        "min_temp": ("T2M_MIN",),
        "max_temp": ("T2M_MAX",),
        "avg_temp": ("T2M",),
        "rainfall_mm": ("PRECTOTCORR", "PRECTOT"),
        "humidity": ("RH2M",),
        "wind_speed": ("WS2M",),
        "solar_radiation": ("ALLSKY_SFC_SW_DWN",),
    }
    MISSING_SENTINELS = {None, "", -999, -999.0, -99, -99.0, "-999", "-99"}

    def transform(
        self,
        payload: RawPayloadEnvelope,
        *,
        data_source: DataSource,
        ingestion_run: IngestionRun,
    ) -> Sequence[NormalizedRecord]:
        """Return one normalized weather row per daily timestamp in the response."""

        _ = (data_source, ingestion_run)
        raw_json = self._require_mapping(payload.raw_json, "payload.raw_json")
        fetch_error = raw_json.get("fetch_error")
        if isinstance(fetch_error, Mapping):
            error_message = str(fetch_error.get("message") or "NASA POWER fetch failed")
            raise ServiceValidationError(error_message)
        field_metadata = self._require_mapping(raw_json.get("field"), "payload.raw_json.field")
        response_payload = self._require_mapping(raw_json.get("response"), "payload.raw_json.response")
        parameter_payload = self._require_mapping(
            response_payload.get("properties", {}).get("parameter"),
            "payload.raw_json.response.properties.parameter",
        )

        field_id = field_metadata.get("id")
        if field_id is None:
            raise ServiceValidationError("NASA POWER payload is missing field.id")

        date_keys = sorted(
            {
                date_key
                for parameter_names in self.FIELD_PARAMETER_PRIORITY.values()
                for parameter_name in parameter_names
                for date_key in self._parameter_series(parameter_payload, parameter_name).keys()
            }
        )

        records: list[NormalizedRecord] = []
        for date_key in date_keys:
            weather_date = self._parse_weather_date(date_key, payload.source_identifier)
            if weather_date is None:
                continue
            values: dict[str, Any] = {
                "field_id": str(field_id),
                "weather_date": weather_date,
            }
            for field_name, parameter_names in self.FIELD_PARAMETER_PRIORITY.items():
                values[field_name] = self._resolve_field_value(
                    parameter_payload=parameter_payload,
                    parameter_names=parameter_names,
                    date_key=date_key,
                )
            if not self._has_any_observation_metric(values):
                logger.info(
                    "Skipping NASA POWER date '%s' from payload '%s' because every mapped metric is missing",
                    weather_date.isoformat(),
                    payload.source_identifier,
                )
                continue
            records.append(
                NormalizedRecord(
                    record_type="weather_history",
                    source_identifier=f"{field_id}:{weather_date.isoformat()}",
                    values=values,
                    payload_type=payload.payload_type,
                )
            )

        logger.info(
            "Transformed NASA POWER payload '%s' into %s daily weather rows",
            payload.source_identifier,
            len(records),
        )
        return records

    def _parameter_series(
        self,
        parameter_payload: Mapping[str, Any],
        parameter_name: str,
    ) -> Mapping[str, Any]:
        series = parameter_payload.get(parameter_name)
        if not isinstance(series, Mapping):
            return {}
        return series

    def _resolve_field_value(
        self,
        *,
        parameter_payload: Mapping[str, Any],
        parameter_names: Sequence[str],
        date_key: str,
    ) -> float | None:
        for parameter_name in parameter_names:
            value = self._normalize_parameter_value(
                self._parameter_series(parameter_payload, parameter_name).get(date_key)
            )
            if value is not None:
                return value
        return None

    def _normalize_parameter_value(self, value: Any) -> float | None:
        if value in self.MISSING_SENTINELS:
            return None
        numeric_value = float(value)
        if math.isnan(numeric_value):
            return None
        return numeric_value

    @staticmethod
    def _has_any_observation_metric(values: Mapping[str, Any]) -> bool:
        metric_names = (
            "min_temp",
            "max_temp",
            "avg_temp",
            "rainfall_mm",
            "humidity",
            "wind_speed",
            "solar_radiation",
        )
        return any(values.get(metric_name) is not None for metric_name in metric_names)

    @staticmethod
    def _parse_weather_date(date_key: str, source_identifier: str) -> date | None:
        try:
            return date.fromisoformat(f"{date_key[0:4]}-{date_key[4:6]}-{date_key[6:8]}")
        except ValueError:
            logger.warning(
                "Skipping NASA POWER series entry with invalid date key '%s' from payload '%s'",
                date_key,
                source_identifier,
            )
            return None

    @staticmethod
    def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ServiceValidationError(f"{field_name} must be an object")
        return value
