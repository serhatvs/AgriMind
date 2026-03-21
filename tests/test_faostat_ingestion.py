from __future__ import annotations

import io
import zipfile

import httpx

from app.config import settings
from app.ingestion.clients.faostat import FAOSTATBulkDownloadClient
from app.ingestion.runners.run_faostat import execute_faostat_ingestion
from app.ingestion.services.external_crop_statistics_writer import ExternalCropStatisticsWriter
from app.ingestion.transformers.faostat_statistics import FAOSTATStatisticsTransformer
from app.ingestion.types import NormalizedRecord, RawPayloadEnvelope
from app.models.enums import (
    DataSourceType,
    IngestionPayloadType,
    IngestionRunStatus,
    IngestionRunType,
)
from app.models.external_crop_statistics import ExternalCropStatistic
from app.models.ingestion import DataSource, IngestionRun, RawIngestionPayload


class _StaticFAOSTATClient:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, object]] = []

    def iter_crop_statistics(
        self,
        *,
        start_year: int,
        end_year: int,
        countries=None,
        crops=None,
        elements=None,
        base_url: str | None = None,
    ):
        self.calls.append(
            {
                "start_year": start_year,
                "end_year": end_year,
                "countries": tuple(countries or ()),
                "crops": tuple(crops or ()),
                "elements": tuple(elements or ()),
                "base_url": base_url,
            }
        )
        yield from list(self.rows)


def _build_faostat_rows() -> list[dict[str, str]]:
    return [
        {
            "Area Code": "231",
            "Area Code (M49)": "'840",
            "Area": "United States of America",
            "Item Code": "56",
            "Item Code (CPC)": "'01313",
            "Item": "Maize",
            "Element Code": "5510",
            "Element": "Production",
            "Year Code": "2023",
            "Year": "2023",
            "Unit": "t",
            "Value": "389694720.000000",
            "Flag": "A",
            "Note": "",
        },
        {
            "Area Code": "231",
            "Area Code (M49)": "'840",
            "Area": "United States of America",
            "Item Code": "56",
            "Item Code (CPC)": "'01313",
            "Item": "Maize",
            "Element Code": "5412",
            "Element": "Yield",
            "Year Code": "2023",
            "Year": "2023",
            "Unit": "kg/ha",
            "Value": "11123.200000",
            "Flag": "A",
            "Note": "",
        },
        {
            "Area Code": "231",
            "Area Code (M49)": "'840",
            "Area": "United States of America",
            "Item Code": "56",
            "Item Code (CPC)": "'01313",
            "Item": "Maize",
            "Element Code": "5312",
            "Element": "Area harvested",
            "Year Code": "2023",
            "Year": "2023",
            "Unit": "ha",
            "Value": "35034000.000000",
            "Flag": "A",
            "Note": "",
        },
    ]


def _build_faostat_zip() -> bytes:
    csv_content = io.StringIO()
    csv_content.write(
        "Area Code,Area Code (M49),Area,Item Code,Item Code (CPC),Item,"
        "Element Code,Element,Year Code,Year,Unit,Value,Flag,Note\r\n"
    )
    for row in _build_faostat_rows():
        csv_content.write(
            (
                f"\"{row['Area Code']}\",\"{row['Area Code (M49)']}\",\"{row['Area']}\","
                f"\"{row['Item Code']}\",\"{row['Item Code (CPC)']}\",\"{row['Item']}\","
                f"\"{row['Element Code']}\",\"{row['Element']}\",\"{row['Year Code']}\","
                f"\"{row['Year']}\",\"{row['Unit']}\",\"{row['Value']}\",\"{row['Flag']}\",\"{row['Note']}\"\r\n"
            )
        )

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "Production_Crops_Livestock_E_All_Data_(Normalized).csv",
            csv_content.getvalue(),
        )
    return archive_buffer.getvalue()


def _build_runtime_records() -> tuple[DataSource, IngestionRun]:
    data_source = DataSource(
        source_name="FAOSTAT",
        source_type=DataSourceType.FILE,
        base_url="https://faostat.example.test/qcl.zip",
        is_active=True,
    )
    ingestion_run = IngestionRun(
        data_source_id=1,
        run_type=IngestionRunType.INCREMENTAL,
    )
    return data_source, ingestion_run


def test_faostat_bulk_download_client_fetches_filtered_rows():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, content=_build_faostat_zip())

    client = FAOSTATBulkDownloadClient(transport=httpx.MockTransport(handler))
    rows = list(
        client.iter_crop_statistics(
            start_year=2023,
            end_year=2023,
            countries=["United States of America"],
            crops=["Maize"],
        )
    )

    assert len(rows) == 3
    assert rows[0]["Area"] == "United States of America"
    assert rows[0]["Item"] == "Maize"
    assert captured["url"] == settings.FAOSTAT_BULK_DOWNLOAD_URL


def test_faostat_transformer_maps_statistics_rows():
    transformer = FAOSTATStatisticsTransformer()
    data_source, ingestion_run = _build_runtime_records()

    records = transformer.transform(
        RawPayloadEnvelope(
            payload_type=IngestionPayloadType.BATCH,
            source_identifier="faostat:2023:2023:batch-1",
            raw_json={
                "rows": _build_faostat_rows(),
            },
        ),
        data_source=data_source,
        ingestion_run=ingestion_run,
    )

    assert len(records) == 3
    assert records[0].values["source_name"] == "FAOSTAT"
    assert records[0].values["country"] == "United States of America"
    assert records[0].values["crop_name"] == "Maize"
    assert records[0].values["statistic_type"] == "production"
    assert records[1].values["statistic_type"] == "yield"
    assert records[2].values["statistic_type"] == "harvested_area"


def test_external_crop_statistics_writer_skips_existing_and_in_batch_duplicates(db):
    db.add(
        ExternalCropStatistic(
            source_name="FAOSTAT",
            country="United States of America",
            year=2023,
            crop_name="Maize",
            statistic_type="production",
            statistic_value=389694720.0,
            unit="t",
        )
    )
    db.commit()

    data_source, ingestion_run = _build_runtime_records()
    writer = ExternalCropStatisticsWriter()
    result = writer.write(
        db,
        [
            NormalizedRecord(
                record_type="external_crop_statistics",
                source_identifier="us-maize-2023-production",
                values={
                    "source_name": "FAOSTAT",
                    "country": "United States of America",
                    "year": 2023,
                    "crop_name": "Maize",
                    "statistic_type": "production",
                    "statistic_value": 389694720.0,
                    "unit": "t",
                },
                payload_type=IngestionPayloadType.BATCH,
            ),
            NormalizedRecord(
                record_type="external_crop_statistics",
                source_identifier="us-maize-2023-yield",
                values={
                    "source_name": "FAOSTAT",
                    "country": "United States of America",
                    "year": 2023,
                    "crop_name": "Maize",
                    "statistic_type": "yield",
                    "statistic_value": 11123.2,
                    "unit": "kg/ha",
                },
                payload_type=IngestionPayloadType.BATCH,
            ),
            NormalizedRecord(
                record_type="external_crop_statistics",
                source_identifier="us-maize-2023-yield-dup",
                values={
                    "source_name": "FAOSTAT",
                    "country": "United States of America",
                    "year": 2023,
                    "crop_name": "Maize",
                    "statistic_type": "yield",
                    "statistic_value": 11123.2,
                    "unit": "kg/ha",
                },
                payload_type=IngestionPayloadType.BATCH,
            ),
        ],
        data_source=data_source,
        ingestion_run=ingestion_run,
    )

    assert result.records_inserted == 1
    assert result.records_skipped == 2
    assert result.skipped_is_successful is True
    assert len(result.skipped_records) == 2
    assert result.skipped_records[0].stage == "deduplication"
    assert db.query(ExternalCropStatistic).count() == 2


def test_execute_faostat_ingestion_persists_run_payloads_and_statistics(db):
    bulk_client = _StaticFAOSTATClient(_build_faostat_rows())

    first_result = execute_faostat_ingestion(
        db,
        start_year=2023,
        end_year=2023,
        countries=["United States of America"],
        crops=["Maize"],
        batch_size=2,
        run_type=IngestionRunType.BACKFILL,
        bulk_client=bulk_client,
    )

    assert first_result.status == IngestionRunStatus.SUCCEEDED
    assert first_result.records_fetched == 2
    assert first_result.records_inserted == 3
    assert first_result.records_skipped == 0
    assert first_result.metadata_json["start_year"] == 2023
    assert first_result.metadata_json["country_filters"] == ["United States of America"]
    assert db.query(DataSource).count() == 1
    assert db.query(IngestionRun).count() == 1
    assert db.query(RawIngestionPayload).count() == 2
    assert db.query(ExternalCropStatistic).count() == 3
    assert bulk_client.calls[0]["base_url"] == settings.FAOSTAT_BULK_DOWNLOAD_URL

    second_result = execute_faostat_ingestion(
        db,
        start_year=2023,
        end_year=2023,
        countries=["United States of America"],
        crops=["Maize"],
        batch_size=2,
        run_type=IngestionRunType.BACKFILL,
        bulk_client=bulk_client,
    )

    assert second_result.status == IngestionRunStatus.SUCCEEDED
    assert second_result.records_inserted == 0
    assert second_result.records_skipped == 3
    assert db.query(DataSource).count() == 1
    assert db.query(IngestionRun).count() == 2
    assert db.query(RawIngestionPayload).count() == 4
    assert db.query(ExternalCropStatistic).count() == 3
