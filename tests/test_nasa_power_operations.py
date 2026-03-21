from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.config import settings
from app.ingestion.clients.nasa_power import NASAPowerFetchResult
from app.ingestion.errors import IngestionVerificationError
from app.ingestion.runners.reset_nasa_power_data import main as reset_nasa_power_data_main
from app.ingestion.runners.run_nasa_power import execute_nasa_power_ingestion
from app.ingestion.runners.verify_nasa_power_ingestion import main as verify_nasa_power_ingestion_main
from app.ingestion.services.nasa_power_operations import (
    reset_nasa_power_ingestion_data,
    verify_nasa_power_ingestion,
)
from app.models.enums import DataSourceType, IngestionPayloadType, IngestionRunStatus, IngestionRunType
from app.models.field import Field
from app.models.ingestion import DataSource, IngestionRun, RawIngestionPayload
from app.models.mixins import utc_now
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
    ) -> NASAPowerFetchResult:
        self.calls.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "end_date": end_date,
                "base_url": base_url,
            }
        )
        parameter_names = tuple(self.payload["properties"]["parameter"].keys())
        return NASAPowerFetchResult(
            payload=self.payload,
            parameter_names=parameter_names,
            attempted_parameter_sets=(parameter_names,),
        )


def _build_field(name: str = "Operations Test Block") -> Field:
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
        notes="NASA operations test field",
    )


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
                "ALLSKY_SFC_SW_DWN": {"20250101": 12.3, "20250102": 11.1},
            }
        }
    }


def test_execute_nasa_power_ingestion_marks_stale_running_rows_before_new_run(db):
    field = _build_field()
    db.add(field)
    db.commit()
    db.refresh(field)

    data_source = DataSource(
        source_name=settings.NASA_POWER_SOURCE_NAME,
        source_type=DataSourceType.API,
        base_url=settings.NASA_POWER_BASE_URL,
        is_active=True,
    )
    db.add(data_source)
    db.commit()
    db.refresh(data_source)

    stale_run = IngestionRun(
        data_source_id=data_source.id,
        run_type=IngestionRunType.INCREMENTAL,
        status=IngestionRunStatus.RUNNING,
        started_at=utc_now() - timedelta(minutes=settings.INGESTION_STALE_RUN_MINUTES + 5),
        records_fetched=0,
        records_inserted=0,
        records_skipped=0,
        metadata_json={},
    )
    db.add(stale_run)
    db.commit()

    result = execute_nasa_power_ingestion(
        db,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        api_client=_StaticNASAAPIClient(_build_nasa_payload()),
        data_source=data_source,
    )

    db.refresh(stale_run)
    latest_run = db.get(IngestionRun, result.ingestion_run_id)

    assert stale_run.status == IngestionRunStatus.FAILED
    assert stale_run.finished_at is not None
    assert stale_run.error_message == "Marked stale before fresh ingestion run."
    assert latest_run is not None
    assert latest_run.status == IngestionRunStatus.SUCCEEDED
    assert latest_run.metadata_json["stale_runs_marked_before_start"] == 1


def test_reset_nasa_power_ingestion_data_deletes_only_nasa_records(db):
    field = _build_field()
    db.add(field)
    db.commit()
    db.refresh(field)

    nasa_result = execute_nasa_power_ingestion(
        db,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        api_client=_StaticNASAAPIClient(_build_nasa_payload()),
    )
    assert nasa_result.records_inserted == 2

    db.add(
        WeatherHistory(
            field_id=field.id,
            date=date(2025, 1, 3),
            min_temp=9.0,
            max_temp=19.0,
            avg_temp=14.0,
            rainfall_mm=2.0,
            humidity=70.0,
            wind_speed=4.4,
            solar_radiation=10.5,
            et0=2.3,
        )
    )
    other_source = DataSource(
        source_name="Other Feed",
        source_type=DataSourceType.API,
        base_url="https://example.test/other",
        is_active=True,
    )
    db.add(other_source)
    db.commit()
    db.refresh(other_source)

    other_run = IngestionRun(
        data_source_id=other_source.id,
        run_type=IngestionRunType.INCREMENTAL,
        status=IngestionRunStatus.SUCCEEDED,
        started_at=utc_now(),
        finished_at=utc_now(),
        records_fetched=1,
        records_inserted=0,
        records_skipped=0,
        metadata_json={"source_name": other_source.source_name},
    )
    db.add(other_run)
    db.commit()
    db.refresh(other_run)

    db.add(
        RawIngestionPayload(
            ingestion_run_id=other_run.id,
            payload_type=IngestionPayloadType.JSON,
            source_identifier="other-1",
            raw_json={"payload": "other"},
        )
    )
    db.commit()

    reset_result = reset_nasa_power_ingestion_data(db)

    assert reset_result.stale_runs_marked == 0
    assert reset_result.weather_rows_deleted == 2
    assert reset_result.raw_payloads_deleted == 1
    assert reset_result.ingestion_runs_deleted == 1
    assert db.query(WeatherHistory).count() == 1
    assert db.query(IngestionRun).count() == 1
    assert db.query(RawIngestionPayload).count() == 1
    assert db.query(DataSource).count() == 2


def test_verify_nasa_power_ingestion_checks_duplicate_safe_rerun(db):
    field = _build_field()
    db.add(field)
    db.commit()
    db.refresh(field)

    api_client = _StaticNASAAPIClient(_build_nasa_payload())
    execute_nasa_power_ingestion(
        db,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        api_client=api_client,
    )

    verification = verify_nasa_power_ingestion(
        db,
        rerun_kwargs={
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 2),
            "api_client": api_client,
        },
    )

    assert verification.succeeded_run_count == 1
    assert verification.weather_history_count_before_rerun == 2
    assert verification.weather_history_count_after_rerun == 2
    assert verification.raw_payload_count_after_rerun > verification.raw_payload_count_before_rerun
    assert verification.ingestion_run_count_after_rerun == verification.ingestion_run_count_before_rerun + 1
    assert verification.duplicate_group_count == 0
    assert verification.running_run_count == 0
    assert verification.stale_running_count == 0
    assert verification.rerun_status == IngestionRunStatus.SUCCEEDED.value


def test_verify_nasa_power_ingestion_raises_for_stale_running_rows(db):
    field = _build_field()
    db.add(field)
    db.commit()
    db.refresh(field)

    execute_nasa_power_ingestion(
        db,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        api_client=_StaticNASAAPIClient(_build_nasa_payload()),
    )
    data_source = db.query(DataSource).filter(DataSource.source_name == settings.NASA_POWER_SOURCE_NAME).one()

    db.add(
        IngestionRun(
            data_source_id=data_source.id,
            run_type=IngestionRunType.INCREMENTAL,
            status=IngestionRunStatus.RUNNING,
            started_at=utc_now() - timedelta(minutes=settings.INGESTION_STALE_RUN_MINUTES + 5),
            records_fetched=0,
            records_inserted=0,
            records_skipped=0,
            metadata_json={},
        )
    )
    db.commit()

    with pytest.raises(IngestionVerificationError, match="stale running ingestion rows remain"):
        verify_nasa_power_ingestion(db, run_duplicate_safe_rerun=False)


def test_reset_nasa_power_data_runner_returns_success(monkeypatch):
    class _FakeSession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "app.ingestion.runners.reset_nasa_power_data.SessionLocal",
        lambda: _FakeSession(),
    )
    monkeypatch.setattr(
        "app.ingestion.runners.reset_nasa_power_data.reset_nasa_power_ingestion_data",
        lambda db: type(
            "_Result",
            (),
            {
                "source_name": settings.NASA_POWER_SOURCE_NAME,
                "data_source_id": uuid4(),
                "stale_runs_marked": 1,
                "weather_rows_deleted": 2,
                "raw_payloads_deleted": 3,
                "ingestion_runs_deleted": 4,
            },
        )(),
    )

    exit_code = reset_nasa_power_data_main(["--log-level", "ERROR"])

    assert exit_code == 0


def test_verify_nasa_power_ingestion_runner_returns_failure_for_failed_verification(monkeypatch):
    class _FakeSession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "app.ingestion.runners.verify_nasa_power_ingestion.SessionLocal",
        lambda: _FakeSession(),
    )
    monkeypatch.setattr(
        "app.ingestion.runners.verify_nasa_power_ingestion.verify_nasa_power_ingestion",
        lambda db, run_duplicate_safe_rerun: (_ for _ in ()).throw(
            IngestionVerificationError("verification failed")
        ),
    )

    exit_code = verify_nasa_power_ingestion_main(["--log-level", "ERROR"])

    assert exit_code == 1
