"""Smoke tests for the ingestion infrastructure and automated runners."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.db.reflection import reflect_tables
from app.ingestion.runners.run_faostat import execute_faostat_ingestion
from app.ingestion.runners.run_nasa_power import execute_nasa_power_ingestion
from app.ingestion.services.pipeline import IngestionPipelineService
from app.ingestion.services.repository import IngestionRepository
from app.ingestion.services.weather_history_writer import WeatherHistoryIngestionWriter
from app.ingestion.transformers.json_records import JSONRecordTransformer
from app.ingestion.transformers.nasa_power_weather import NASAPowerWeatherTransformer
from app.ingestion.types import PersistResult, RawPayloadEnvelope
from app.ingestion.validators.base import validate_records
from app.ingestion.validators.required_fields import RequiredFieldsValidator
from app.ingestion.validators.weather_history import WeatherHistoryRecordValidator
from app.models.enums import DataSourceType, IngestionPayloadType, IngestionRunStatus, IngestionRunType
from app.models.field import Field
from app.models.ingestion import DataSource, IngestionRun, RawIngestionPayload
from app.models.weather_history import WeatherHistory


class _StaticClient:
    def __init__(self, payloads: list[RawPayloadEnvelope]) -> None:
        self.payloads = payloads

    def fetch(self, data_source: DataSource, *, run_type: IngestionRunType) -> list[RawPayloadEnvelope]:
        _ = (data_source, run_type)
        return list(self.payloads)


class _FailingWriter:
    def write(self, db, records, *, data_source: DataSource, ingestion_run: IngestionRun) -> PersistResult:
        _ = (db, records, data_source, ingestion_run)
        raise RuntimeError("sink unavailable")


class _StaticNASAAPIClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def fetch_daily_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        base_url: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "end_date": end_date,
                "base_url": base_url,
            }
        )
        return self.payload


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


@pytest.fixture
def field_with_coordinates(db) -> Field:
    field = Field(
        name="Smoke Test Block",
        location_name="Springfield",
        latitude=39.7817,
        longitude=-89.6501,
        area_hectares=12.5,
        elevation_meters=182.0,
        slope_percent=2.4,
        irrigation_available=True,
        infrastructure_score=80,
        drainage_quality="good",
        notes="Ingestion smoke test field",
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


def _build_nasa_payload(
    *,
    humidity_by_day: dict[str, float] | None = None,
) -> dict[str, object]:
    humidity_series = humidity_by_day or {
        "20250101": 71.0,
        "20250102": 69.0,
        "20250103": 68.0,
    }
    date_keys = tuple(humidity_series.keys())

    def select_dates(values: dict[str, float]) -> dict[str, float]:
        return {date_key: values[date_key] for date_key in date_keys}

    return {
        "properties": {
            "parameter": {
                "T2M_MIN": select_dates({"20250101": 10.0, "20250102": 11.0, "20250103": 12.0}),
                "T2M_MAX": select_dates({"20250101": 20.0, "20250102": 21.0, "20250103": 22.0}),
                "T2M": select_dates({"20250101": 15.0, "20250102": 16.0, "20250103": 17.0}),
                "PRECTOTCORR": select_dates({"20250101": 3.2, "20250102": 0.0, "20250103": 1.4}),
                "RH2M": humidity_series,
                "WS2M": select_dates({"20250101": 4.6, "20250102": 5.1, "20250103": 4.9}),
                "ALLSKY_SFC_SW_DWN": select_dates({"20250101": 12.3, "20250102": 11.1, "20250103": 12.8}),
                "EVPTRNS": select_dates({"20250101": 2.3, "20250102": 2.5, "20250103": 2.4}),
            }
        }
    }


def _build_faostat_rows() -> list[dict[str, str]]:
    return [
        {
            "Area": "United States of America",
            "Item": "Maize",
            "Element": "Production",
            "Year": "2023",
            "Unit": "t",
            "Value": "389694720.000000",
        },
        {
            "Area": "United States of America",
            "Item": "Maize",
            "Element": "Yield",
            "Year": "2023",
            "Unit": "kg/ha",
            "Value": "11123.200000",
        },
        {
            "Area": "United States of America",
            "Item": "Maize",
            "Element": "Area harvested",
            "Year": "2023",
            "Unit": "ha",
            "Value": "35034000.000000",
        },
    ]


def test_ingestion_repository_smoke_creates_run_stores_raw_payloads_and_marks_success(db):
    repository = IngestionRepository(db)
    repository.ensure_ingestion_tables_ready()

    data_source = repository.get_or_create_data_source(
        source_name="Smoke Feed",
        source_type=DataSourceType.API,
        base_url="https://example.test/smoke",
        is_active=True,
    )

    ingestion_run = repository.create_ingestion_run(
        data_source,
        run_type=IngestionRunType.INCREMENTAL,
        metadata_json={"trigger": "smoke"},
    )
    assert ingestion_run.status == IngestionRunStatus.RUNNING

    repository.store_raw_payloads(
        ingestion_run,
        [
            RawPayloadEnvelope(
                payload_type=IngestionPayloadType.BATCH,
                source_identifier="smoke-batch-1",
                raw_json={"rows": [{"external_id": "wx-1", "rainfall_mm": 12.4}]},
            )
        ],
    )

    finalized_run = repository.finalize_ingestion_run(
        ingestion_run,
        status=IngestionRunStatus.SUCCEEDED,
        records_fetched=1,
        records_inserted=1,
        records_skipped=0,
        metadata_json={"result": "ok"},
    )

    raw_payloads = (
        db.query(RawIngestionPayload)
        .filter(RawIngestionPayload.ingestion_run_id == finalized_run.id)
        .order_by(RawIngestionPayload.id.asc())
        .all()
    )

    assert finalized_run.status == IngestionRunStatus.SUCCEEDED
    assert finalized_run.finished_at is not None
    assert finalized_run.metadata_json["trigger"] == "smoke"
    assert finalized_run.metadata_json["result"] == "ok"
    assert len(raw_payloads) == 1
    assert raw_payloads[0].source_identifier == "smoke-batch-1"
    assert raw_payloads[0].raw_json["rows"][0]["external_id"] == "wx-1"


def test_weather_ingestion_smoke_transforms_validates_deduplicates_and_inserts_rows(db, field_with_coordinates):
    db.add(
        WeatherHistory(
            field_id=field_with_coordinates.id,
            date=date(2025, 1, 1),
            min_temp=8.0,
            max_temp=18.0,
            avg_temp=13.0,
            rainfall_mm=1.1,
            humidity=65.0,
            wind_speed=3.2,
            solar_radiation=10.0,
            et0=2.0,
        )
    )
    db.commit()

    transformer = NASAPowerWeatherTransformer()
    payload = RawPayloadEnvelope(
        payload_type=IngestionPayloadType.JSON,
        source_identifier=f"{field_with_coordinates.id}:2025-01-01:2025-01-03",
        raw_json={
            "field": {
                "id": str(field_with_coordinates.id),
                "name": field_with_coordinates.name,
                "latitude": field_with_coordinates.latitude,
                "longitude": field_with_coordinates.longitude,
            },
            "response": _build_nasa_payload(
                humidity_by_day={
                    "20250101": 71.0,
                    "20250102": 140.0,
                    "20250103": 68.0,
                }
            ),
        },
    )
    data_source = DataSource(
        source_name="NASA POWER",
        source_type=DataSourceType.API,
        base_url="https://power.example.test",
        is_active=True,
    )
    ingestion_run = IngestionRun(data_source_id=1, run_type=IngestionRunType.INCREMENTAL)

    transformed_records = transformer.transform(
        payload,
        data_source=data_source,
        ingestion_run=ingestion_run,
    )
    validation_result = validate_records(transformed_records, [WeatherHistoryRecordValidator()])
    persist_result = WeatherHistoryIngestionWriter().write(
        db,
        validation_result.valid_records,
        data_source=data_source,
        ingestion_run=ingestion_run,
    )

    weather_rows = (
        db.query(WeatherHistory)
        .filter(WeatherHistory.field_id == field_with_coordinates.id)
        .order_by(WeatherHistory.date.asc())
        .all()
    )

    assert len(transformed_records) == 3
    assert len(validation_result.valid_records) == 2
    assert len(validation_result.skipped_records) == 1
    assert validation_result.skipped_records[0].stage == "validation"
    assert validation_result.skipped_records[0].reasons[0].code == "value_above_maximum"
    assert persist_result.records_inserted == 1
    assert persist_result.records_skipped == 1
    assert persist_result.skipped_records[0].stage == "deduplication"
    assert persist_result.skipped_records[0].reasons[0].code == "duplicate_record"
    assert [row.date for row in weather_rows] == [date(2025, 1, 1), date(2025, 1, 3)]
    assert weather_rows[1].avg_temp == 17.0


def test_nasa_power_runner_smoke_executes_end_to_end_with_mocked_client(db, field_with_coordinates):
    api_client = _StaticNASAAPIClient(
        _build_nasa_payload(
            humidity_by_day={
                "20250101": 71.0,
                "20250102": 69.0,
            }
        )
    )

    result = execute_nasa_power_ingestion(
        db,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        run_type=IngestionRunType.BACKFILL,
        api_client=api_client,
    )

    ingestion_run = db.get(IngestionRun, result.ingestion_run_id)
    raw_payloads = (
        db.query(RawIngestionPayload)
        .filter(RawIngestionPayload.ingestion_run_id == result.ingestion_run_id)
        .all()
    )
    weather_rows = db.query(WeatherHistory).order_by(WeatherHistory.date.asc()).all()

    assert result.status == IngestionRunStatus.SUCCEEDED
    assert result.records_fetched == 1
    assert result.records_inserted == 2
    assert result.records_skipped == 0
    assert ingestion_run is not None
    assert ingestion_run.status == IngestionRunStatus.SUCCEEDED
    assert len(raw_payloads) == 1
    assert len(weather_rows) == 2
    assert [row.date for row in weather_rows] == [date(2025, 1, 1), date(2025, 1, 2)]
    assert api_client.calls[0]["latitude"] == field_with_coordinates.latitude


def test_faostat_runner_smoke_executes_end_to_end_with_mocked_client(db):
    bulk_client = _StaticFAOSTATClient(_build_faostat_rows())

    result = execute_faostat_ingestion(
        db,
        start_year=2023,
        end_year=2023,
        countries=["United States of America"],
        crops=["Maize"],
        batch_size=2,
        run_type=IngestionRunType.BACKFILL,
        bulk_client=bulk_client,
    )

    ingestion_run = db.get(IngestionRun, result.ingestion_run_id)
    raw_payloads = (
        db.query(RawIngestionPayload)
        .filter(RawIngestionPayload.ingestion_run_id == result.ingestion_run_id)
        .order_by(RawIngestionPayload.id.asc())
        .all()
    )
    statistics_table = reflect_tables(db, "external_crop_statistics")["external_crop_statistics"]
    statistics_rows = db.execute(
        select(statistics_table)
        .order_by(
            statistics_table.c.country.asc(),
            statistics_table.c.crop_name.asc(),
            statistics_table.c.statistic_type.asc(),
        )
    ).mappings().all()

    assert result.status == IngestionRunStatus.SUCCEEDED
    assert result.records_fetched == 2
    assert result.records_inserted == 3
    assert result.records_skipped == 0
    assert ingestion_run is not None
    assert ingestion_run.status == IngestionRunStatus.SUCCEEDED
    assert len(raw_payloads) == 2
    assert len(statistics_rows) == 3
    assert statistics_rows[0].country == "United States of America"
    assert statistics_rows[0].crop_name == "Maize"
    assert bulk_client.calls[0]["countries"] == ("United States of America",)


def test_ingestion_pipeline_smoke_marks_run_failed_when_persistence_raises(db):
    data_source = DataSource(
        source_name="Broken Feed",
        source_type=DataSourceType.API,
        base_url="https://example.test/broken",
        is_active=True,
    )
    db.add(data_source)
    db.commit()
    db.refresh(data_source)

    pipeline = IngestionPipelineService(
        db,
        client=_StaticClient(
            [
                RawPayloadEnvelope(
                    payload_type=IngestionPayloadType.RECORD,
                    source_identifier="record-1",
                    raw_json={"external_id": "record-1", "field_name": "Parcel A"},
                )
            ]
        ),
        transformer=JSONRecordTransformer(record_type="generic_record"),
        writer=_FailingWriter(),
        validators=[RequiredFieldsValidator("external_id", "field_name")],
    )

    with pytest.raises(RuntimeError, match="sink unavailable"):
        pipeline.run(data_source.id, run_type=IngestionRunType.INCREMENTAL)

    failed_run = db.query(IngestionRun).order_by(IngestionRun.id.desc()).first()
    raw_payloads = (
        db.query(RawIngestionPayload)
        .filter(RawIngestionPayload.ingestion_run_id == failed_run.id)
        .all()
    )

    assert failed_run is not None
    assert failed_run.status == IngestionRunStatus.FAILED
    assert failed_run.finished_at is not None
    assert failed_run.error_message == "sink unavailable"
    assert failed_run.records_fetched == 1
    assert failed_run.records_inserted == 0
    assert failed_run.records_skipped == 0
    assert len(raw_payloads) == 1
