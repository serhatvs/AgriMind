"""Transformer for FAOSTAT crop statistics batches."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
import math
from typing import Any

from app.ingestion.transformers.base import PayloadTransformer
from app.ingestion.types import NormalizedRecord, RawPayloadEnvelope
from app.models.enums import ExternalCropStatisticType
from app.models.ingestion import DataSource, IngestionRun
from app.services.errors import ServiceValidationError


logger = logging.getLogger(__name__)


class FAOSTATStatisticsTransformer(PayloadTransformer):
    """Map FAOSTAT crop statistics batches into normalized internal rows."""

    ELEMENT_TO_STATISTIC_TYPE = {
        "Production": ExternalCropStatisticType.PRODUCTION.value,
        "Yield": ExternalCropStatisticType.YIELD.value,
        "Area harvested": ExternalCropStatisticType.HARVESTED_AREA.value,
    }

    def transform(
        self,
        payload: RawPayloadEnvelope,
        *,
        data_source: DataSource,
        ingestion_run: IngestionRun,
    ) -> Sequence[NormalizedRecord]:
        """Transform a FAOSTAT batch payload into normalized crop statistic rows."""

        _ = ingestion_run
        raw_json = self._require_mapping(payload.raw_json, "payload.raw_json")
        rows = raw_json.get("rows")
        if not isinstance(rows, list):
            raise ServiceValidationError("payload.raw_json.rows must be a list")

        records: list[NormalizedRecord] = []
        for row in rows:
            row_mapping = self._require_mapping(row, "payload.raw_json.rows[]")
            country = self._clean_string(self._first_value(row_mapping, "Area", "area", "country"))
            crop_name = self._clean_string(self._first_value(row_mapping, "Item", "item", "crop_name", "crop"))
            statistic_type = self.ELEMENT_TO_STATISTIC_TYPE.get(
                self._clean_string(self._first_value(row_mapping, "Element", "element"))
            )
            year = self._parse_int(self._first_value(row_mapping, "Year", "year"))
            statistic_value = self._parse_float(self._first_value(row_mapping, "Value", "value"))
            unit = self._clean_string(self._first_value(row_mapping, "Unit", "unit"))

            source_identifier = ":".join(
                part
                for part in (
                    country or "unknown-country",
                    crop_name or "unknown-crop",
                    str(year) if year is not None else "unknown-year",
                    statistic_type or "unknown-stat",
                )
            )
            records.append(
                NormalizedRecord(
                    record_type="external_crop_statistics",
                    source_identifier=source_identifier,
                    values={
                        "source_name": data_source.source_name,
                        "country": country,
                        "year": year,
                        "crop_name": crop_name,
                        "statistic_type": statistic_type,
                        "statistic_value": statistic_value,
                        "unit": unit,
                    },
                    payload_type=payload.payload_type,
                )
            )

        logger.info(
            "Transformed FAOSTAT payload '%s' into %s normalized statistics rows",
            payload.source_identifier,
            len(records),
        )
        return records

    @staticmethod
    def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ServiceValidationError(f"{field_name} must be an object")
        return value

    @staticmethod
    def _clean_string(value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _first_value(row: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row:
                return row[key]
        return None

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).strip())
        except ValueError:
            return None

    @staticmethod
    def _parse_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            numeric_value = float(str(value).strip())
        except ValueError:
            return None
        if math.isnan(numeric_value):
            return None
        return numeric_value
