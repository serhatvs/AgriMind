"""Reusable HTTP JSON ingestion client."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import httpx

from app.ingestion.errors import IngestionConfigurationError
from app.ingestion.types import RawPayloadEnvelope
from app.models.enums import IngestionPayloadType, IngestionRunType
from app.models.ingestion import DataSource


class HTTPJSONClient:
    """Fetch a JSON document from an HTTP endpoint and wrap it as a raw payload."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        payload_type: IngestionPayloadType | str = IngestionPayloadType.JSON,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.headers = dict(headers or {})
        self.params = dict(params or {})
        self.payload_type = payload_type

    def fetch(
        self,
        data_source: DataSource,
        *,
        run_type: IngestionRunType,
    ) -> Sequence[RawPayloadEnvelope]:
        """Fetch a JSON response from the source base URL."""

        if not data_source.base_url:
            raise IngestionConfigurationError(
                f"Data source '{data_source.source_name}' does not define a base_url"
            )

        params = dict(self.params)
        params.setdefault("run_type", run_type.value)

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(
                data_source.base_url,
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            payload = response.json()

        return [
            RawPayloadEnvelope(
                payload_type=self.payload_type,
                source_identifier=data_source.source_name,
                raw_json=payload,
            )
        ]
