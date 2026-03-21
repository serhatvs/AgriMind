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
        "T2M_MIN": "min_temp",
        "T2M_MAX": "max_temp",
        "T2M": "avg_temp",
        "PRECTOT": "rainfall_mm",
        "RH2M": "humidity",
        "WS2M": "wind_speed",
        "ALLSKY_SFC_SW_DWN": "solar_radiation",
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
                for parameter_name in self.PARAMETER_TO_FIELD_MAP
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
            for parameter_name, field_name in self.PARAMETER_TO_FIELD_MAP.items():
                values[field_name] = self._normalize_parameter_value(
                    self._parameter_series(parameter_payload, parameter_name).get(date_key)
                )
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

    def _normalize_parameter_value(self, value: Any) -> float | None:
        if value in self.MISSING_SENTINELS:
            return None
        numeric_value = float(value)
        if math.isnan(numeric_value):
            return None
        return numeric_value

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
