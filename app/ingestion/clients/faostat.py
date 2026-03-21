"""Client for FAOSTAT bulk crop statistics downloads and ingestion batching."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import csv
import io
from datetime import date
import logging
from zipfile import ZipFile

import httpx

from app.config import settings
from app.ingestion.clients.base import IngestionClient
from app.ingestion.errors import IngestionConfigurationError
from app.ingestion.types import RawPayloadEnvelope
from app.models.enums import IngestionPayloadType, IngestionRunType
from app.models.ingestion import DataSource


logger = logging.getLogger(__name__)


class FAOSTATBulkDownloadClient:
    """Download and filter the official FAOSTAT bulk crops and livestock export."""

    DEFAULT_DATASET_FILENAME = "Production_Crops_Livestock_E_All_Data_(Normalized).csv"
    SUPPORTED_ELEMENTS = ("Production", "Yield", "Area harvested")

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url or settings.FAOSTAT_BULK_DOWNLOAD_URL
        self.timeout_seconds = timeout_seconds or settings.FAOSTAT_TIMEOUT_SECONDS
        self.transport = transport

    def iter_crop_statistics(
        self,
        *,
        start_year: int,
        end_year: int,
        countries: Sequence[str] | None = None,
        crops: Sequence[str] | None = None,
        elements: Sequence[str] | None = None,
        base_url: str | None = None,
    ) -> Iterable[dict[str, str]]:
        """Yield filtered FAOSTAT rows from the bulk crops and livestock archive."""

        if start_year > end_year:
            raise IngestionConfigurationError("start_year must be less than or equal to end_year")

        allowed_countries = self._normalize_filter_values(countries)
        allowed_crops = self._normalize_filter_values(crops)
        allowed_elements = self._normalize_filter_values(elements or self.SUPPORTED_ELEMENTS)

        archive_bytes = self._download_archive(base_url=base_url)
        with ZipFile(io.BytesIO(archive_bytes)) as archive:
            csv_member_name = self._select_csv_member_name(archive)
            with archive.open(csv_member_name) as csv_file:
                reader = csv.DictReader(io.TextIOWrapper(csv_file, encoding="utf-8-sig", newline=""))
                for raw_row in reader:
                    row = {
                        (key or "").strip(): (value.strip() if isinstance(value, str) else "")
                        for key, value in raw_row.items()
                    }
                    if not self._matches_filters(
                        row,
                        start_year=start_year,
                        end_year=end_year,
                        countries=allowed_countries,
                        crops=allowed_crops,
                        elements=allowed_elements,
                    ):
                        continue
                    yield row

    def _download_archive(self, *, base_url: str | None = None) -> bytes:
        request_url = base_url or self.base_url
        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport, follow_redirects=True) as client:
            response = client.get(request_url)
            response.raise_for_status()
            return response.content

    def _select_csv_member_name(self, archive: ZipFile) -> str:
        try:
            return next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        except StopIteration as exc:
            raise IngestionConfigurationError("FAOSTAT archive does not contain a CSV member") from exc

    def _matches_filters(
        self,
        row: dict[str, str],
        *,
        start_year: int,
        end_year: int,
        countries: set[str],
        crops: set[str],
        elements: set[str],
    ) -> bool:
        year_value = self._parse_int(row.get("Year"))
        if year_value is None or year_value < start_year or year_value > end_year:
            return False

        area_name = row.get("Area", "")
        if countries and self._normalize_filter_value(area_name) not in countries:
            return False

        item_name = row.get("Item", "")
        if crops and self._normalize_filter_value(item_name) not in crops:
            return False

        element_name = row.get("Element", "")
        return self._normalize_filter_value(element_name) in elements

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
    def _parse_int(value: str | None) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError:
            return None


class FAOSTATIngestionClient(IngestionClient):
    """Fetch filtered FAOSTAT rows and package them into raw payload batches."""

    def __init__(
        self,
        bulk_client: FAOSTATBulkDownloadClient,
        *,
        start_year: int | None = None,
        end_year: int | None = None,
        countries: Sequence[str] | None = None,
        crops: Sequence[str] | None = None,
        batch_size: int | None = None,
        default_lookback_years: int | None = None,
    ) -> None:
        self.bulk_client = bulk_client
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
        """Download, filter, and chunk FAOSTAT rows into raw ingestion payloads."""

        _ = run_type
        if not data_source.base_url:
            raise IngestionConfigurationError(
                f"Data source '{data_source.source_name}' does not define a base_url"
            )
        if self.batch_size <= 0:
            raise IngestionConfigurationError("batch_size must be greater than 0")

        start_year, end_year = self.resolve_year_range()
        payloads: list[RawPayloadEnvelope] = []
        batch_rows: list[dict[str, str]] = []
        batch_number = 0

        for row in self.bulk_client.iter_crop_statistics(
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
            logger.warning(
                "No FAOSTAT rows matched the filters for %s-%s",
                start_year,
                end_year,
            )
        return payloads

    def _build_payload(
        self,
        *,
        batch_number: int,
        start_year: int,
        end_year: int,
        rows: list[dict[str, str]],
    ) -> RawPayloadEnvelope:
        return RawPayloadEnvelope(
            payload_type=IngestionPayloadType.BATCH,
            source_identifier=f"faostat:{start_year}:{end_year}:batch-{batch_number}",
            raw_json={
                "dataset_name": getattr(
                    self.bulk_client,
                    "DEFAULT_DATASET_FILENAME",
                    FAOSTATBulkDownloadClient.DEFAULT_DATASET_FILENAME,
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
