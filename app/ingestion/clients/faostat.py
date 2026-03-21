"""REST client for FAOSTAT crop statistics and ingestion batching helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date
import logging
from typing import Any

import httpx

from app.config import settings
from app.ingestion.clients.base import IngestionClient
from app.ingestion.errors import IngestionConfigurationError
from app.ingestion.types import RawPayloadEnvelope
from app.models.enums import ExternalCropStatisticType, IngestionPayloadType, IngestionRunType
from app.models.ingestion import DataSource


logger = logging.getLogger(__name__)


class FAOSTATAPIClient:
    """Fetch annual crop statistics from the FAOSTAT REST API."""

    DEFAULT_DATASET_NAME = "FAOSTAT REST API"
    SUPPORTED_ELEMENTS = (
        "Production",
        "Yield",
        "Area harvested",
    )
    ELEMENT_ALIASES = {
        ExternalCropStatisticType.PRODUCTION.value: {"production", "production quantity", "2510", "5510"},
        ExternalCropStatisticType.YIELD.value: {"yield", "5412", "5419"},
        ExternalCropStatisticType.HARVESTED_AREA.value: {"area harvested", "harvested area", "5312"},
    }

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_token: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url or settings.FAOSTAT_API_BASE_URL
        self.api_token = api_token or settings.FAOSTAT_API_TOKEN
        self.timeout_seconds = timeout_seconds or settings.FAOSTAT_TIMEOUT_SECONDS
        self.transport = transport

    def iter_crop_statistics(
        self,
        *,
        start_year: int,
        end_year: int,
        countries: Sequence[str] | None = None,
        crops: Sequence[str] | None = None,
        base_url: str | None = None,
    ) -> Iterable[dict[str, Any]]:
        """Yield FAOSTAT crop statistic rows from the REST API."""

        if start_year > end_year:
            raise IngestionConfigurationError("start_year must be less than or equal to end_year")

        allowed_countries = self._normalize_filter_values(countries)
        allowed_crops = self._normalize_filter_values(crops)

        for year in range(start_year, end_year + 1):
            logger.info("Fetching FAOSTAT crop statistics for year %s", year)
            for row in self._fetch_year_rows(year=year, base_url=base_url):
                if not self._matches_filters(
                    row,
                    year=year,
                    countries=allowed_countries,
                    crops=allowed_crops,
                ):
                    continue
                yield dict(row)

    def _fetch_year_rows(
        self,
        *,
        year: int,
        base_url: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {
            "year": year,
            "show_unit": 1,
            "show_flags": 0,
            "null_values": 0,
            "limit": -1,
            "output_type": "objects",
        }
        request_url = base_url or self.base_url
        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport, follow_redirects=True) as client:
            response = client.get(request_url, params=params, headers=self._build_headers())
            response.raise_for_status()
            payload = response.json()
        return self._extract_rows(payload, year=year)

    def _extract_rows(self, payload: Any, *, year: int) -> list[dict[str, Any]]:
        rows = payload.get("data") if isinstance(payload, Mapping) else payload
        if not isinstance(rows, list):
            raise IngestionConfigurationError("FAOSTAT API response is missing a list 'data' payload")

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                logger.warning("Skipping non-object FAOSTAT row for year %s", year)
                continue
            normalized_rows.append({str(key).strip(): value for key, value in row.items()})
        return normalized_rows

    def _matches_filters(
        self,
        row: Mapping[str, Any],
        *,
        year: int,
        countries: set[str],
        crops: set[str],
    ) -> bool:
        row_year = self._parse_int(self._first_value(row, "Year", "year"))
        if row_year is None or row_year != year:
            return False

        country = self._clean_string(self._first_value(row, "Area", "area", "country"))
        if countries and self._normalize_filter_value(country or "") not in countries:
            return False

        crop_name = self._clean_string(self._first_value(row, "Item", "item", "crop_name", "crop"))
        if crops and self._normalize_filter_value(crop_name or "") not in crops:
            return False

        statistic_type = self._normalize_statistic_type(row)
        return statistic_type is not None

    def _normalize_statistic_type(self, row: Mapping[str, Any]) -> str | None:
        element_name = self._clean_string(self._first_value(row, "Element", "element"))
        element_code = self._clean_string(self._first_value(row, "Element Code", "element_code", "elementCode"))
        normalized_candidates = {
            self._normalize_filter_value(candidate)
            for candidate in (element_name, element_code)
            if candidate
        }
        for statistic_type, aliases in self.ELEMENT_ALIASES.items():
            if normalized_candidates.intersection(alias.casefold() for alias in aliases):
                return statistic_type
        return None

    @staticmethod
    def _first_value(row: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row:
                return row[key]
        return None

    def _build_headers(self) -> dict[str, str]:
        if not self.api_token:
            return {}
        return {"Authorization": f"Bearer {self.api_token}"}

    @staticmethod
    def _clean_string(value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _normalize_filter_values(values: Sequence[str] | None) -> set[str]:
        if not values:
            return set()
        normalized_values: set[str] = set()
        for value in values:
            stripped_value = value.strip()
            if stripped_value:
                normalized_values.add(stripped_value.casefold())
        return normalized_values

    @staticmethod
    def _normalize_filter_value(value: str) -> str:
        return value.strip().casefold()

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).strip())
        except ValueError:
            return None


class FAOSTATIngestionClient(IngestionClient):
    """Fetch filtered FAOSTAT REST rows and package them into raw payload batches."""

    def __init__(
        self,
        api_client: FAOSTATAPIClient,
        *,
        start_year: int | None = None,
        end_year: int | None = None,
        countries: Sequence[str] | None = None,
        crops: Sequence[str] | None = None,
        batch_size: int | None = None,
        default_lookback_years: int | None = None,
    ) -> None:
        self.api_client = api_client
        self.start_year = start_year
        self.end_year = end_year
        self.countries = tuple(countries or ())
        self.crops = tuple(crops or ())
        self.batch_size = batch_size if batch_size is not None else settings.FAOSTAT_BATCH_SIZE
        self.default_lookback_years = (
            default_lookback_years
            if default_lookback_years is not None
            else settings.FAOSTAT_DEFAULT_LOOKBACK_YEARS
        )

    def resolve_year_range(self) -> tuple[int, int]:
        """Return the effective inclusive year window for the current ingestion run."""

        current_year = date.today().year
        end_year = self.end_year if self.end_year is not None else current_year - 1
        lookback_years = self.default_lookback_years
        if lookback_years <= 0:
            raise IngestionConfigurationError("default_lookback_years must be greater than 0")

        if self.start_year is not None:
            start_year = self.start_year
        else:
            start_year = end_year - lookback_years + 1

        if start_year > end_year:
            raise IngestionConfigurationError("start_year must be less than or equal to end_year")
        return start_year, end_year

    def fetch(
        self,
        data_source: DataSource,
        *,
        run_type: IngestionRunType,
    ) -> Sequence[RawPayloadEnvelope]:
        """Fetch FAOSTAT REST rows and store them as batched raw payload envelopes."""

        _ = run_type
        if not data_source.base_url:
            raise IngestionConfigurationError(
                f"Data source '{data_source.source_name}' does not define a base_url"
            )
        if self.batch_size <= 0:
            raise IngestionConfigurationError("batch_size must be greater than 0")

        start_year, end_year = self.resolve_year_range()
        payloads: list[RawPayloadEnvelope] = []
        batch_rows: list[dict[str, Any]] = []
        batch_number = 0

        for row in self.api_client.iter_crop_statistics(
            start_year=start_year,
            end_year=end_year,
            countries=self.countries,
            crops=self.crops,
            base_url=data_source.base_url,
        ):
            batch_rows.append(row)
            if len(batch_rows) >= self.batch_size:
                batch_number += 1
                payloads.append(
                    self._build_payload(
                        batch_number=batch_number,
                        start_year=start_year,
                        end_year=end_year,
                        rows=batch_rows,
                    )
                )
                batch_rows = []

        if batch_rows:
            batch_number += 1
            payloads.append(
                self._build_payload(
                    batch_number=batch_number,
                    start_year=start_year,
                    end_year=end_year,
                    rows=batch_rows,
                )
            )

        if not payloads:
            logger.warning("No FAOSTAT rows matched the filters for %s-%s", start_year, end_year)
        return payloads

    def _build_payload(
        self,
        *,
        batch_number: int,
        start_year: int,
        end_year: int,
        rows: list[dict[str, Any]],
    ) -> RawPayloadEnvelope:
        return RawPayloadEnvelope(
            payload_type=IngestionPayloadType.BATCH,
            source_identifier=f"faostat:{start_year}:{end_year}:batch-{batch_number}",
            raw_json={
                "dataset_name": getattr(
                    self.api_client,
                    "DEFAULT_DATASET_NAME",
                    FAOSTATAPIClient.DEFAULT_DATASET_NAME,
                ),
                "start_year": start_year,
                "end_year": end_year,
                "countries": list(self.countries),
                "crops": list(self.crops),
                "batch_number": batch_number,
                "row_count": len(rows),
                "rows": rows,
            },
        )


# Backward-compatible alias for older imports that still reference the bulk client name.
FAOSTATBulkDownloadClient = FAOSTATAPIClient
