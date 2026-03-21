"""NASA POWER client and ingestion adapter for field-scoped daily weather pulls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
import logging
import time
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


@dataclass(frozen=True, slots=True)
class NASAPowerFetchResult:
    """Successful NASA POWER response plus request metadata."""

    payload: dict[str, Any]
    parameter_names: tuple[str, ...]
    attempted_parameter_sets: tuple[tuple[str, ...], ...]

    def has_observations(self) -> bool:
        """Return whether the response contains any non-missing daily value."""

        parameter_payload = self.payload.get("properties", {}).get("parameter", {})
        if not isinstance(parameter_payload, Mapping):
            return False

        for parameter_name in self.parameter_names:
            series = parameter_payload.get(parameter_name)
            if not isinstance(series, Mapping):
                continue
            for value in series.values():
                if value not in NASAPowerAPIClient.MISSING_SENTINELS:
                    return True
        return False


class NASAPowerAPIClient:
    """Thin client for the NASA POWER daily point API."""

    PRIMARY_PARAMETER_SET = (
        "T2M",
        "T2M_MIN",
        "T2M_MAX",
        "PRECTOTCORR",
        "RH2M",
        "WS2M",
        "ALLSKY_SFC_SW_DWN",
    )
    FALLBACK_PARAMETER_SETS = (
        PRIMARY_PARAMETER_SET,
        (
            "T2M",
            "T2M_MIN",
            "T2M_MAX",
            "PRECTOT",
            "RH2M",
            "WS2M",
            "ALLSKY_SFC_SW_DWN",
        ),
        (
            "T2M",
            "T2M_MIN",
            "T2M_MAX",
            "PRECTOTCORR",
            "RH2M",
            "ALLSKY_SFC_SW_DWN",
        ),
        (
            "T2M",
            "T2M_MIN",
            "T2M_MAX",
            "PRECTOT",
            "RH2M",
            "ALLSKY_SFC_SW_DWN",
        ),
        (
            "T2M",
            "T2M_MIN",
            "T2M_MAX",
            "PRECTOTCORR",
        ),
        (
            "T2M",
            "T2M_MIN",
            "T2M_MAX",
            "PRECTOT",
        ),
    )
    MISSING_SENTINELS = {None, "", -999, -999.0, -99, -99.0, "-999", "-99"}

    def __init__(
        self,
        *,
        base_url: str | None = None,
        community: str | None = None,
        timeout_seconds: float | None = None,
        time_standard: str | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url or settings.NASA_POWER_BASE_URL
        self.community = community or settings.NASA_POWER_COMMUNITY
        self.timeout_seconds = timeout_seconds or settings.NASA_POWER_TIMEOUT_SECONDS
        self.time_standard = time_standard or settings.NASA_POWER_TIME_STANDARD
        self.max_retries = settings.NASA_POWER_MAX_RETRIES if max_retries is None else max_retries
        self.retry_backoff_seconds = (
            settings.NASA_POWER_RETRY_BACKOFF_SECONDS
            if retry_backoff_seconds is None
            else retry_backoff_seconds
        )
        self.transport = transport

    def fetch_daily_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        base_url: str | None = None,
    ) -> NASAPowerFetchResult:
        """Fetch a daily NASA POWER response for a coordinate window."""

        if start_date > end_date:
            raise IngestionConfigurationError("start_date must be on or before end_date")

        request_url = base_url or self.base_url
        attempted_parameter_sets: list[tuple[str, ...]] = []
        fallback_errors: list[str] = []

        for parameter_names in self.FALLBACK_PARAMETER_SETS:
            attempted_parameter_sets.append(tuple(parameter_names))
            try:
                payload = self._request_with_retries(
                    request_url=request_url,
                    latitude=latitude,
                    longitude=longitude,
                    start_date=start_date,
                    end_date=end_date,
                    parameter_names=parameter_names,
                )
                return NASAPowerFetchResult(
                    payload=payload,
                    parameter_names=tuple(parameter_names),
                    attempted_parameter_sets=tuple(attempted_parameter_sets),
                )
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                response_text = exc.response.text[:500]
                fallback_errors.append(
                    f"status={status_code} params={','.join(parameter_names)} body={response_text}"
                )
                if status_code in {400, 404, 422}:
                    logger.warning(
                        "NASA POWER request rejected for parameter set %s with status %s; trying fallback set",
                        ",".join(parameter_names),
                        status_code,
                    )
                    continue
                raise

        fallback_summary = "; ".join(fallback_errors) or "no successful parameter set"
        raise IngestionConfigurationError(
            f"NASA POWER request failed for all parameter sets: {fallback_summary}"
        )

    def _request_with_retries(
        self,
        *,
        request_url: str,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        parameter_names: Sequence[str],
    ) -> dict[str, Any]:
        params = self._build_query_params(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            parameter_names=parameter_names,
        )

        attempts = self.max_retries + 1
        for attempt_number in range(1, attempts + 1):
            try:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    transport=self.transport,
                    follow_redirects=True,
                ) as client:
                    response = client.get(request_url, params=params)
                    response.raise_for_status()
                    payload = response.json()
                self._validate_response(payload)
                return payload
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt_number >= attempts:
                    raise IngestionConfigurationError(
                        f"NASA POWER request failed after {attempt_number} attempt(s): {exc}"
                    ) from exc
                logger.warning(
                    "NASA POWER request attempt %s/%s failed for parameters %s: %s",
                    attempt_number,
                    attempts,
                    ",".join(parameter_names),
                    exc,
                )
                if self.retry_backoff_seconds > 0:
                    time.sleep(self.retry_backoff_seconds * attempt_number)

    def _build_query_params(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        parameter_names: Sequence[str],
    ) -> dict[str, object]:
        return {
            "parameters": ",".join(parameter_names),
            "community": self.community,
            "longitude": longitude,
            "latitude": latitude,
            "start": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "format": "JSON",
            "time-standard": self.time_standard,
        }

    @staticmethod
    def _validate_response(payload: dict[str, Any]) -> None:
        parameter_payload = payload.get("properties", {}).get("parameter")
        if not isinstance(parameter_payload, dict):
            raise IngestionConfigurationError("NASA POWER response is missing properties.parameter")


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
        max_window_shifts: int | None = None,
    ) -> None:
        self.api_client = api_client
        self.field_targets = tuple(field_targets)
        self.start_date = start_date
        self.end_date = end_date
        self.default_lookback_days = default_lookback_days or settings.NASA_POWER_DEFAULT_LOOKBACK_DAYS
        self.max_window_shifts = (
            settings.NASA_POWER_MAX_WINDOW_SHIFTS
            if max_window_shifts is None
            else max_window_shifts
        )
        self._resolved_date_range: tuple[date, date] | None = None
        self._probe_result: NASAPowerFetchResult | None = None

    def resolve_date_range(self) -> tuple[date, date]:
        """Return the effective date range for the current ingestion run."""

        if self._resolved_date_range is not None:
            return self._resolved_date_range

        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise IngestionConfigurationError("start_date must be on or before end_date")
            self._resolved_date_range = (self.start_date, self.end_date)
            return self._resolved_date_range

        end_date = self.end_date or date.today()
        lookback_days = self.default_lookback_days
        if lookback_days <= 0:
            raise IngestionConfigurationError("default_lookback_days must be greater than 0")
        start_date = self.start_date or (end_date - timedelta(days=lookback_days - 1))
        if start_date > end_date:
            raise IngestionConfigurationError("start_date must be on or before end_date")

        if self.start_date is not None or not self.field_targets:
            self._resolved_date_range = (start_date, end_date)
            return self._resolved_date_range

        self._resolved_date_range = self._resolve_available_window(start_date=start_date, end_date=end_date)
        return self._resolved_date_range

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
        for index, field_target in enumerate(self.field_targets):
            logger.info(
                "Fetching NASA POWER weather for field '%s' (%s) from %s to %s",
                field_target.field_name,
                field_target.field_id,
                start_date.isoformat(),
                end_date.isoformat(),
            )
            try:
                if index == 0 and self._probe_result is not None:
                    fetch_result = self._probe_result
                else:
                    fetch_result = self.api_client.fetch_daily_weather(
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
                            "resolved_parameters": list(fetch_result.parameter_names),
                            "attempted_parameter_sets": [
                                list(parameter_set)
                                for parameter_set in fetch_result.attempted_parameter_sets
                            ],
                            "response": fetch_result.payload,
                        },
                    )
                )
            except Exception as exc:
                logger.exception(
                    "NASA POWER fetch failed for field '%s' (%s)",
                    field_target.field_name,
                    field_target.field_id,
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
                            "fetch_error": {
                                "type": exc.__class__.__name__,
                                "message": str(exc),
                            },
                        },
                        is_error=True,
                        error_message=str(exc),
                    )
                )
        return payloads

    def _resolve_available_window(self, *, start_date: date, end_date: date) -> tuple[date, date]:
        """Shift the default window backwards until NASA returns real observations."""

        probe_field = self.field_targets[0]
        window_size_days = (end_date - start_date).days + 1

        for shift_index in range(self.max_window_shifts + 1):
            shifted_end_date = end_date - timedelta(days=window_size_days * shift_index)
            shifted_start_date = shifted_end_date - timedelta(days=window_size_days - 1)
            probe_result = self.api_client.fetch_daily_weather(
                latitude=probe_field.latitude,
                longitude=probe_field.longitude,
                start_date=shifted_start_date,
                end_date=shifted_end_date,
            )
            if probe_result.has_observations():
                if shift_index > 0:
                    logger.warning(
                        "NASA POWER returned empty recent windows; shifted default window to %s..%s",
                        shifted_start_date.isoformat(),
                        shifted_end_date.isoformat(),
                    )
                self._probe_result = probe_result
                return shifted_start_date, shifted_end_date

        logger.warning(
            "NASA POWER returned empty data across %s window shift attempts; using requested range %s..%s",
            self.max_window_shifts + 1,
            start_date.isoformat(),
            end_date.isoformat(),
        )
        return start_date, end_date
