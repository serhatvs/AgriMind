from __future__ import annotations

from datetime import date

import httpx

from app.config import settings
from app.ingestion.clients.nasa_power import NASAPowerAPIClient
from app.ingestion.runners.run_nasa_power import execute_nasa_power_ingestion
from app.ingestion.services.weather_history_writer import WeatherHistoryIngestionWriter
from app.ingestion.transformers.nasa_power_weather import NASAPowerWeatherTransformer
from app.ingestion.types import NormalizedRecord, RawPayloadEnvelope
from app.models.enums import (
    DataSourceType,
    IngestionPayloadType,
    IngestionRunStatus,
    IngestionRunType,
)
from app.models.field import Field
from app.models.ingestion import DataSource, IngestionRun, RawIngestionPayload
from app.models.weather_history import WeatherHistory


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


def _build_nasa_payload() -> dict[str, object]:
    return {
        "properties": {
            "parameter": {
                "T2M_MIN": {"20250101": 10.0, "20250102": 11.0},
                "T2M_MAX": {"20250101": 20.0, "20250102": 21.0},
                "T2M": {"20250101": 15.0, "20250102": 16.0},
                "PRECTOTCORR": {"20250101": 3.2, "20250102": 0.0},
                "RH2M": {"20250101": 71.0, "20250102": 69.0},
                "WS2M": {"20250101": 4.6, "20250102": 5.1},
                "ALLSKY_SFC_SW_DWN": {"20250101": 12.3, "20250102": -999.0},
                "EVPTRNS": {"20250101": 2.3, "20250102": 2.5},
            }
        }
    }


def _build_field(name: str = "North Block") -> Field:
    return Field(
        name=name,
        location_name="Springfield",
        latitude=39.7817,
        longitude=-89.6501,
        area_hectares=12.5,
        elevation_meters=182.0,
        slope_percent=2.4,
        irrigation_available=True,
        infrastructure_score=80,
        drainage_quality="good",
        notes="NASA ingestion test field",
    )


def _build_runtime_records() -> tuple[DataSource, IngestionRun]:
    data_source = DataSource(
        source_name="NASA POWER",
        source_type=DataSourceType.API,
        base_url="https://power.example.test",
        is_active=True,
    )
    ingestion_run = IngestionRun(
        data_source_id=1,
        run_type=IngestionRunType.INCREMENTAL,
    )
    return data_source, ingestion_run


def test_nasa_power_api_client_fetches_daily_weather_with_expected_query():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_build_nasa_payload())

    client = NASAPowerAPIClient(transport=httpx.MockTransport(handler))

    payload = client.fetch_daily_weather(
        latitude=39.7817,
        longitude=-89.6501,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )

    assert payload["properties"]["parameter"]["T2M"]["20250101"] == 15.0
    assert captured["params"]["start"] == "20250101"
    assert captured["params"]["end"] == "20250102"
    assert captured["params"]["community"] == settings.NASA_POWER_COMMUNITY
    assert captured["params"]["time-standard"] == settings.NASA_POWER_TIME_STANDARD
    assert "T2M_MIN" in captured["params"]["parameters"]


def test_nasa_power_weather_transformer_maps_daily_rows():
    transformer = NASAPowerWeatherTransformer()
    data_source, ingestion_run = _build_runtime_records()

    records = transformer.transform(
        RawPayloadEnvelope(
            payload_type=IngestionPayloadType.JSON,
            source_identifier="field-1:2025-01-01:2025-01-02",
            raw_json={
                "field": {
                    "id": "field-1",
                    "name": "North Block",
                    "latitude": 39.7817,
                    "longitude": -89.6501,
                },
                "response": _build_nasa_payload(),
            },
        ),
        data_source=data_source,
        ingestion_run=ingestion_run,
    )

    assert len(records) == 2
    assert records[0].values["field_id"] == "field-1"
    assert records[0].values["weather_date"] == date(2025, 1, 1)
    assert records[0].values["rainfall_mm"] == 3.2
    assert records[1].values["solar_radiation"] is None
    assert records[1].values["et0"] == 2.5


def test_weather_history_writer_skips_existing_and_in_batch_duplicates(db):
    field = _build_field()
    db.add(field)
    db.commit()
    db.refresh(field)

    db.add(
        WeatherHistory(
            field_id=field.id,
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

    data_source, ingestion_run = _build_runtime_records()
    writer = WeatherHistoryIngestionWriter()
    result = writer.write(
        db,
        [
            NormalizedRecord(
                record_type="weather_history",
                source_identifier=f"{field.id}:2025-01-01",
                values={
                    "field_id": str(field.id),
                    "weather_date": date(2025, 1, 1),
                    "min_temp": 9.0,
                    "max_temp": 19.0,
                    "avg_temp": 14.0,
                    "rainfall_mm": 0.0,
                    "humidity": 60.0,
                    "wind_speed": 4.0,
                    "solar_radiation": 11.0,
                    "et0": 2.1,
                },
                payload_type=IngestionPayloadType.JSON,
            ),
            NormalizedRecord(
                record_type="weather_history",
                source_identifier=f"{field.id}:2025-01-02",
                values={
                    "field_id": str(field.id),
                    "weather_date": date(2025, 1, 2),
                    "min_temp": 10.0,
                    "max_temp": 20.0,
                    "avg_temp": 15.0,
                    "rainfall_mm": 2.0,
                    "humidity": 61.0,
                    "wind_speed": 4.1,
                    "solar_radiation": 12.0,
                    "et0": 2.4,
                },
                payload_type=IngestionPayloadType.JSON,
            ),
            NormalizedRecord(
                record_type="weather_history",
                source_identifier=f"{field.id}:2025-01-02:dup",
                values={
                    "field_id": str(field.id),
                    "weather_date": date(2025, 1, 2),
                    "min_temp": 10.0,
                    "max_temp": 20.0,
                    "avg_temp": 15.0,
                    "rainfall_mm": 2.0,
                    "humidity": 61.0,
                    "wind_speed": 4.1,
                    "solar_radiation": 12.0,
                    "et0": 2.4,
                },
                payload_type=IngestionPayloadType.JSON,
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
    assert result.metadata_json["date_column"] == "date"
    assert db.query(WeatherHistory).count() == 2


def test_execute_nasa_power_ingestion_persists_run_payloads_and_weather_rows(db):
    field = _build_field()
    db.add(field)
    db.commit()
    db.refresh(field)

    api_client = _StaticNASAAPIClient(_build_nasa_payload())

    first_result = execute_nasa_power_ingestion(
        db,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        run_type=IngestionRunType.BACKFILL,
        api_client=api_client,
    )

    assert first_result.status == IngestionRunStatus.SUCCEEDED
    assert first_result.records_fetched == 1
    assert first_result.records_inserted == 2
    assert first_result.records_skipped == 0
    assert first_result.metadata_json["field_target_count"] == 1
    assert db.query(DataSource).count() == 1
    assert db.query(IngestionRun).count() == 1
    assert db.query(RawIngestionPayload).count() == 1
    assert db.query(WeatherHistory).count() == 2
    assert api_client.calls[0]["base_url"] == settings.NASA_POWER_BASE_URL

    second_result = execute_nasa_power_ingestion(
        db,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        run_type=IngestionRunType.BACKFILL,
        api_client=api_client,
    )

    assert second_result.status == IngestionRunStatus.SUCCEEDED
    assert second_result.records_inserted == 0
    assert second_result.records_skipped == 2
    assert db.query(DataSource).count() == 1
    assert db.query(IngestionRun).count() == 2
    assert db.query(RawIngestionPayload).count() == 2
    assert db.query(WeatherHistory).count() == 2
