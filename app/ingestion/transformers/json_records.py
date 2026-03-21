"""Reusable JSON payload transformer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.ingestion.types import NormalizedRecord, RawPayloadEnvelope
from app.models.ingestion import DataSource, IngestionRun
from app.services.errors import ServiceValidationError


class JSONRecordTransformer:
    """Transform a JSON object or array payload into normalized record objects."""

    def __init__(
        self,
        *,
        record_type: str,
        payload_items_key: str | None = None,
        source_identifier_field: str | None = None,
    ) -> None:
        self.record_type = record_type
        self.payload_items_key = payload_items_key
        self.source_identifier_field = source_identifier_field

    def transform(
        self,
        payload: RawPayloadEnvelope,
        *,
        data_source: DataSource,
        ingestion_run: IngestionRun,
    ) -> Sequence[NormalizedRecord]:
        """Expand a JSON payload into one or more normalized mapping records."""

        _ = (data_source, ingestion_run)
        items = self._extract_items(payload.raw_json)
        records: list[NormalizedRecord] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise ServiceValidationError(
                    f"Transformer expected mapping items for payload '{payload.source_identifier}'"
                )
            identifier = payload.source_identifier
            if self.source_identifier_field is not None and item.get(self.source_identifier_field) is not None:
                identifier = str(item[self.source_identifier_field])
            records.append(
                NormalizedRecord(
                    record_type=self.record_type,
                    source_identifier=identifier,
                    values=dict(item),
                    payload_type=payload.payload_type,
                )
            )
        return records

    def _extract_items(self, raw_json: Any) -> list[Any]:
        if self.payload_items_key is None:
            if isinstance(raw_json, list):
                return list(raw_json)
            return [raw_json]

        if not isinstance(raw_json, Mapping):
            raise ServiceValidationError(
                f"Expected payload object with '{self.payload_items_key}' items collection"
            )

        items = raw_json.get(self.payload_items_key)
        if not isinstance(items, list):
            raise ServiceValidationError(
                f"Expected payload key '{self.payload_items_key}' to contain a list"
            )
        return list(items)
