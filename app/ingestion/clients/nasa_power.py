"""NASA POWER client and ingestion adapter for field-scoped daily weather pulls."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
import logging
from typing import Any

import httpx

from app.config import settings
from app.ingestion.clients.base import IngestionClient
from app.ingestion.errors import IngestionConfigurationError
from app.ingestion.services.field_targets import FieldCoordinateTarget
from app.ingestion.types import RawPayloadEnvelope
from app.models.enums import IngestionPayloadType, IngestionRunType
from app.models.ingestion import DataSource


logger = logging.getLogger(__name__)


class NASAPowerAPIClient:
    """Thin client for the NASA POWER daily point API."""

    PARAMETERS = (
        "T2M_MIN",
        "T2M_MAX",
        "T2M",
        "PRECTOTCORR",
        "RH2M",
        "WS2M",
        "ALLSKY_SFC_SW_DWN",
        "EVPTRNS",
    )

    def __init__(
        self,
        *,
        base_url: str | None = None,
        community: str | None = None,
        timeout_seconds: float | None = None,
        time_standard: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url or settings.NASA_POWER_BASE_URL
        self.community = community or settings.NASA_POWER_COMMUNITY
        self.timeout_seconds = timeout_seconds or settings.NASA_POWER_TIMEOUT_SECONDS
        self.time_standard = time_standard or settings.NASA_POWER_TIME_STANDARD
        self.transport = transport

    def fetch_daily_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a daily NASA POWER response for a coordinate window."""

        if start_date > end_date:
            raise IngestionConfigurationError("start_date must be on or before end_date")

        params = {
            "parameters": ",".join(self.PARAMETERS),
            "community": self.community,
            "longitude": longitude,
            "latitude": latitude,
            "start": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "format": "JSON",
            "time-standard": self.time_standard,
        }
        request_url = base_url or self.base_url
        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
            response = client.get(request_url, params=params)
            response.raise_for_status()
            payload = response.json()

        parameter_payload = payload.get("properties", {}).get("parameter")
        if not isinstance(parameter_payload, dict):
            raise IngestionConfigurationError("NASA POWER response is missing properties.parameter")
        return payload


class NASAPowerIngestionClient(IngestionClient):
    """Fetch NASA POWER weather payloads for a prepared list of field targets."""

    def __init__(
        self,
        api_client: NASAPowerAPIClient,
        *,
        field_targets: Sequence[FieldCoordinateTarget],
        start_date: date | None = None,
        end_date: date | None = None,
        default_lookback_days: int | None = None,
    ) -> None:
        self.api_client = api_client
        self.field_targets = tuple(field_targets)
        self.start_date = start_date
        self.end_date = end_date
        self.default_lookback_days = default_lookback_days or settings.NASA_POWER_DEFAULT_LOOKBACK_DAYS

    def resolve_date_range(self) -> tuple[date, date]:
        """Return the effective date range for the current ingestion run."""

        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise IngestionConfigurationError("start_date must be on or before end_date")
            return self.start_date, self.end_date

        end_date = self.end_date or date.today()
        lookback_days = self.default_lookback_days
        if lookback_days <= 0:
            raise IngestionConfigurationError("default_lookback_days must be greater than 0")
        start_date = self.start_date or (end_date - timedelta(days=lookback_days - 1))
        if start_date > end_date:
            raise IngestionConfigurationError("start_date must be on or before end_date")
        return start_date, end_date

    def fetch(
        self,
        data_source: DataSource,
        *,
        run_type: IngestionRunType,
    ) -> Sequence[RawPayloadEnvelope]:
        """Fetch one NASA POWER raw payload per field target."""

        _ = run_type
        if not data_source.base_url:
            raise IngestionConfigurationError(
                f"Data source '{data_source.source_name}' does not define a base_url"
            )

        start_date, end_date = self.resolve_date_range()
        if not self.field_targets:
            logger.warning("No fields with coordinates are available for NASA POWER ingestion")
            return []

        payloads: list[RawPayloadEnvelope] = []
        for field_target in self.field_targets:
            logger.info(
                "Fetching NASA POWER weather for field '%s' (%s) from %s to %s",
                field_target.field_name,
                field_target.field_id,
                start_date.isoformat(),
                end_date.isoformat(),
            )
            response_payload = self.api_client.fetch_daily_weather(
                latitude=field_target.latitude,
                longitude=field_target.longitude,
                start_date=start_date,
                end_date=end_date,
                base_url=data_source.base_url,
            )
            payloads.append(
                RawPayloadEnvelope(
                    payload_type=IngestionPayloadType.JSON,
                    source_identifier=f"{field_target.field_id}:{start_date.isoformat()}:{end_date.isoformat()}",
                    raw_json={
                        "field": {
                            "id": str(field_target.field_id),
                            "name": field_target.field_name,
                            "latitude": field_target.latitude,
                            "longitude": field_target.longitude,
                        },
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "response": response_payload,
                    },
                )
            )
        return payloads
