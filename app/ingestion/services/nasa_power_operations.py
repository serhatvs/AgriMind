"""Operational helpers for resetting and verifying NASA POWER ingestion state."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
import logging
import math
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.reflection import reflect_tables
from app.ingestion.errors import IngestionVerificationError
from app.ingestion.services.repository import IngestionRepository
from app.ingestion.types import IngestionExecutionResult
from app.models.enums import IngestionRunStatus, IngestionRunType
from app.models.ingestion import DataSource, IngestionRun, RawIngestionPayload
from app.services.errors import ServiceValidationError


logger = logging.getLogger(__name__)
MISSING_SENTINELS = {None, "", -999, -999.0, -99, -99.0, "-999", "-99"}
WEATHER_PARAMETER_PRIORITY = {
    "min_temp": ("T2M_MIN",),
    "max_temp": ("T2M_MAX",),
    "avg_temp": ("T2M",),
    "rainfall_mm": ("PRECTOTCORR", "PRECTOT"),
    "humidity": ("RH2M",),
    "wind_speed": ("WS2M",),
    "solar_radiation": ("ALLSKY_SFC_SW_DWN",),
}


@dataclass(frozen=True, slots=True)
class NASAPowerResetResult:
    """Summary of a source-scoped NASA POWER reset operation."""

    source_name: str
    data_source_id: UUID | None
    stale_runs_marked: int
    weather_rows_deleted: int
    raw_payloads_deleted: int
    ingestion_runs_deleted: int


@dataclass(frozen=True, slots=True)
class NASAPowerVerificationResult:
    """Summary of NASA POWER ingestion verification checks."""

    source_name: str
    data_source_id: UUID
    succeeded_run_count: int
    raw_payload_count: int
    weather_history_count: int
    structured_weather_row_count: int
    duplicate_group_count: int
    running_run_count: int
    stale_running_count: int
    rerun_ingestion_run_id: int | None
    rerun_status: str | None
    weather_history_count_before_rerun: int
    weather_history_count_after_rerun: int
    raw_payload_count_before_rerun: int
    raw_payload_count_after_rerun: int
    ingestion_run_count_before_rerun: int
    ingestion_run_count_after_rerun: int


def reset_nasa_power_ingestion_data(
    db: Session,
    *,
    repository: IngestionRepository | None = None,
) -> NASAPowerResetResult:
    """Remove NASA POWER ingestion audit data and the weather rows it created."""

    repository = repository or IngestionRepository(db)
    repository.ensure_ingestion_tables_ready()

    data_source = repository.get_data_source_by_name(settings.NASA_POWER_SOURCE_NAME)
    if data_source is None:
        logger.info("NASA POWER reset found no configured data source row")
        return NASAPowerResetResult(
            source_name=settings.NASA_POWER_SOURCE_NAME,
            data_source_id=None,
            stale_runs_marked=0,
            weather_rows_deleted=0,
            raw_payloads_deleted=0,
            ingestion_runs_deleted=0,
        )

    stale_runs = repository.mark_stale_running_runs(
        data_source_id=data_source.id,
        error_message="Marked stale before NASA POWER reset.",
    )

    nasa_runs = (
        db.query(IngestionRun)
        .filter(IngestionRun.data_source_id == data_source.id)
        .order_by(IngestionRun.id.asc())
        .all()
    )
    run_ids = [run.id for run in nasa_runs]
    raw_payloads = _load_raw_payloads_for_runs(db, run_ids)
    weather_keys = _collect_weather_history_keys(
        raw_payloads=raw_payloads,
        data_source=data_source,
        fallback_run_type=IngestionRunType.INCREMENTAL,
    )
    weather_rows_deleted = _delete_weather_rows(db, weather_keys)

    raw_payloads_deleted = 0
    if run_ids:
        raw_payloads_deleted = (
            db.query(RawIngestionPayload)
            .filter(RawIngestionPayload.ingestion_run_id.in_(run_ids))
            .delete(synchronize_session=False)
        )
        db.commit()

    ingestion_runs_deleted = 0
    if run_ids:
        ingestion_runs_deleted = (
            db.query(IngestionRun)
            .filter(IngestionRun.id.in_(run_ids))
            .delete(synchronize_session=False)
        )
        db.commit()

    logger.info(
        "NASA POWER reset completed with stale_runs_marked=%s weather_rows_deleted=%s raw_payloads_deleted=%s ingestion_runs_deleted=%s",
        len(stale_runs),
        weather_rows_deleted,
        raw_payloads_deleted,
        ingestion_runs_deleted,
    )
    return NASAPowerResetResult(
        source_name=data_source.source_name,
        data_source_id=data_source.id,
        stale_runs_marked=len(stale_runs),
        weather_rows_deleted=weather_rows_deleted,
        raw_payloads_deleted=raw_payloads_deleted,
        ingestion_runs_deleted=ingestion_runs_deleted,
    )


def verify_nasa_power_ingestion(
    db: Session,
    *,
    repository: IngestionRepository | None = None,
    run_duplicate_safe_rerun: bool = True,
    rerun_type: IngestionRunType = IngestionRunType.INCREMENTAL,
    rerun_executor: Callable[..., IngestionExecutionResult] | None = None,
    rerun_kwargs: Mapping[str, Any] | None = None,
) -> NASAPowerVerificationResult:
    """Validate NASA POWER ingestion health and duplicate-safe rerun behavior."""

    repository = repository or IngestionRepository(db)
    repository.ensure_ingestion_tables_ready()

    data_source = repository.get_data_source_by_name(settings.NASA_POWER_SOURCE_NAME)
    if data_source is None:
        raise IngestionVerificationError("NASA POWER data source is not configured.")

    stale_running_count = repository.count_stale_running_ingestion_runs(data_source_id=data_source.id)
    running_run_count = repository.count_running_ingestion_runs(data_source_id=data_source.id)
    succeeded_run_count = _count_runs_by_status(db, data_source.id, IngestionRunStatus.SUCCEEDED)
    raw_payload_count = _count_raw_payloads(db, data_source.id)
    weather_history_count = _count_weather_history_rows(db)
    structured_weather_row_count = _count_structured_weather_rows(db)
    duplicate_group_count = _count_weather_history_duplicates(db)

    _require(succeeded_run_count > 0, "NASA POWER verification failed: no succeeded ingestion run exists.")
    _require(stale_running_count == 0, "NASA POWER verification failed: stale running ingestion rows remain.")
    _require(running_run_count == 0, "NASA POWER verification failed: running ingestion rows remain.")
    _require(raw_payload_count > 0, "NASA POWER verification failed: no raw payload audit rows exist.")
    _require(weather_history_count > 0, "NASA POWER verification failed: weather_history has no rows.")
    _require(
        structured_weather_row_count > 0,
        "NASA POWER verification failed: weather_history rows do not contain usable metrics.",
    )
    _require(
        duplicate_group_count == 0,
        "NASA POWER verification failed: duplicate weather_history field/date rows were detected.",
    )

    pre_run_count = _count_source_runs(db, data_source.id)
    pre_raw_payload_count = raw_payload_count
    pre_weather_count = weather_history_count
    rerun_result = None
    if run_duplicate_safe_rerun:
        if rerun_executor is None:
            from app.ingestion.runners.run_nasa_power import execute_nasa_power_ingestion

            rerun_executor = execute_nasa_power_ingestion

        rerun_result = rerun_executor(
            db,
            run_type=rerun_type,
            repository=repository,
            data_source=data_source,
            **dict(rerun_kwargs or {}),
        )
        _require(
            rerun_result.status == IngestionRunStatus.SUCCEEDED,
            f"NASA POWER verification failed: rerun finished with status '{rerun_result.status.value}'.",
        )

    post_run_count = _count_source_runs(db, data_source.id)
    post_raw_payload_count = _count_raw_payloads(db, data_source.id)
    post_weather_count = _count_weather_history_rows(db)
    post_duplicate_group_count = _count_weather_history_duplicates(db)
    post_running_run_count = repository.count_running_ingestion_runs(data_source_id=data_source.id)
    post_stale_running_count = repository.count_stale_running_ingestion_runs(data_source_id=data_source.id)

    if run_duplicate_safe_rerun:
        _require(
            post_run_count == pre_run_count + 1,
            "NASA POWER verification failed: rerun did not create a new ingestion_run row.",
        )
        _require(
            post_raw_payload_count > pre_raw_payload_count,
            "NASA POWER verification failed: rerun did not create additional raw payload rows.",
        )
        _require(
            post_weather_count == pre_weather_count,
            "NASA POWER verification failed: rerun duplicated weather_history rows.",
        )

    _require(
        post_duplicate_group_count == 0,
        "NASA POWER verification failed: duplicate weather_history rows were detected after rerun.",
    )
    _require(
        post_running_run_count == 0,
        "NASA POWER verification failed: running ingestion rows remain after verification.",
    )
    _require(
        post_stale_running_count == 0,
        "NASA POWER verification failed: stale running ingestion rows remain after verification.",
    )

    logger.info(
        "NASA POWER verification completed with succeeded_runs=%s raw_payloads=%s weather_rows=%s duplicate_groups=%s",
        succeeded_run_count,
        post_raw_payload_count,
        post_weather_count,
        post_duplicate_group_count,
    )
    return NASAPowerVerificationResult(
        source_name=data_source.source_name,
        data_source_id=data_source.id,
        succeeded_run_count=succeeded_run_count,
        raw_payload_count=post_raw_payload_count,
        weather_history_count=post_weather_count,
        structured_weather_row_count=structured_weather_row_count,
        duplicate_group_count=post_duplicate_group_count,
        running_run_count=post_running_run_count,
        stale_running_count=post_stale_running_count,
        rerun_ingestion_run_id=rerun_result.ingestion_run_id if rerun_result is not None else None,
        rerun_status=rerun_result.status.value if rerun_result is not None else None,
        weather_history_count_before_rerun=pre_weather_count,
        weather_history_count_after_rerun=post_weather_count,
        raw_payload_count_before_rerun=pre_raw_payload_count,
        raw_payload_count_after_rerun=post_raw_payload_count,
        ingestion_run_count_before_rerun=pre_run_count,
        ingestion_run_count_after_rerun=post_run_count,
    )


def _load_raw_payloads_for_runs(db: Session, run_ids: Sequence[int]) -> list[RawIngestionPayload]:
    if not run_ids:
        return []
    return (
        db.query(RawIngestionPayload)
        .filter(RawIngestionPayload.ingestion_run_id.in_(run_ids))
        .order_by(RawIngestionPayload.id.asc())
        .all()
    )


def _collect_weather_history_keys(
    *,
    raw_payloads: Iterable[RawIngestionPayload],
    data_source: DataSource,
    fallback_run_type: IngestionRunType,
) -> set[tuple[Any, date]]:
    _ = (data_source, fallback_run_type)
    weather_keys: set[tuple[Any, date]] = set()
    for raw_payload in raw_payloads:
        raw_json = raw_payload.raw_json if isinstance(raw_payload.raw_json, Mapping) else {}
        field_metadata = raw_json.get("field")
        response = raw_json.get("response")
        if not isinstance(field_metadata, Mapping) or not isinstance(response, Mapping):
            continue
        field_id = field_metadata.get("id")
        if field_id is None:
            continue
        try:
            date_keys = _extract_supported_weather_dates(response)
        except Exception:
            logger.debug(
                "Skipping weather row reconstruction for payload '%s' during reset",
                raw_payload.source_identifier,
                exc_info=True,
            )
            continue
        for weather_date in date_keys:
            weather_keys.add((field_id, weather_date))
    return weather_keys


def _delete_weather_rows(db: Session, weather_keys: Sequence[tuple[Any, date]]) -> int:
    if not weather_keys:
        return 0

    weather_history_table = reflect_tables(db, "weather_history")["weather_history"]
    date_column_name = "date" if "date" in weather_history_table.c else "weather_date"
    date_column = getattr(weather_history_table.c, date_column_name)
    normalized_keys = {
        (
            _normalize_identifier_for_column(weather_history_table.c.field_id, field_id),
            weather_date,
        )
        for field_id, weather_date in weather_keys
    }

    deleted_rows = 0
    for chunk in _chunked(tuple(normalized_keys), 200):
        conditions = [
            and_(weather_history_table.c.field_id == field_id, date_column == weather_date)
            for field_id, weather_date in chunk
        ]
        if not conditions:
            continue
        result = db.execute(delete(weather_history_table).where(or_(*conditions)))
        deleted_rows += int(result.rowcount or 0)
        db.commit()
    return deleted_rows


def _count_runs_by_status(db: Session, data_source_id: UUID, status: IngestionRunStatus) -> int:
    return (
        db.query(IngestionRun)
        .filter(IngestionRun.data_source_id == data_source_id, IngestionRun.status == status)
        .count()
    )


def _count_source_runs(db: Session, data_source_id: UUID) -> int:
    return db.query(IngestionRun).filter(IngestionRun.data_source_id == data_source_id).count()


def _count_raw_payloads(db: Session, data_source_id: UUID) -> int:
    return (
        db.query(RawIngestionPayload)
        .join(IngestionRun, RawIngestionPayload.ingestion_run_id == IngestionRun.id)
        .filter(IngestionRun.data_source_id == data_source_id)
        .count()
    )


def _count_weather_history_rows(db: Session) -> int:
    weather_history_table = reflect_tables(db, "weather_history")["weather_history"]
    return int(db.execute(select(func.count()).select_from(weather_history_table)).scalar_one())


def _count_structured_weather_rows(db: Session) -> int:
    weather_history_table = reflect_tables(db, "weather_history")["weather_history"]
    metric_conditions = _metric_not_null_conditions(weather_history_table)
    statement = select(func.count()).select_from(weather_history_table)
    if metric_conditions:
        statement = statement.where(or_(*metric_conditions))
    return int(db.execute(statement).scalar_one())


def _count_weather_history_duplicates(db: Session) -> int:
    weather_history_table = reflect_tables(db, "weather_history")["weather_history"]
    date_column_name = "date" if "date" in weather_history_table.c else "weather_date"
    duplicate_rows = db.execute(
        select(func.count())
        .select_from(
            select(
                weather_history_table.c.field_id,
                getattr(weather_history_table.c, date_column_name).label(date_column_name),
            )
            .group_by(weather_history_table.c.field_id, getattr(weather_history_table.c, date_column_name))
            .having(func.count() > 1)
            .subquery()
        )
    ).scalar_one()
    return int(duplicate_rows)


def _extract_supported_weather_dates(response_payload: Mapping[str, Any]) -> set[date]:
    properties = response_payload.get("properties")
    if not isinstance(properties, Mapping):
        return set()
    parameter_payload = properties.get("parameter")
    if not isinstance(parameter_payload, Mapping):
        return set()

    date_keys = sorted(
        {
            date_key
            for parameter_names in WEATHER_PARAMETER_PRIORITY.values()
            for parameter_name in parameter_names
            for date_key in _parameter_series(parameter_payload, parameter_name).keys()
        }
    )
    weather_dates: set[date] = set()
    for date_key in date_keys:
        weather_date = _parse_weather_date(date_key)
        if weather_date is None:
            continue
        if _date_has_observation(parameter_payload, date_key):
            weather_dates.add(weather_date)
    return weather_dates


def _metric_not_null_conditions(weather_history_table) -> list[Any]:
    metric_columns = (
        "min_temp",
        "max_temp",
        "avg_temp",
        "rainfall_mm",
        "humidity",
        "wind_speed",
        "solar_radiation",
    )
    return [
        getattr(weather_history_table.c, column_name).is_not(None)
        for column_name in metric_columns
        if column_name in weather_history_table.c
    ]


def _parameter_series(parameter_payload: Mapping[str, Any], parameter_name: str) -> Mapping[str, Any]:
    series = parameter_payload.get(parameter_name)
    if not isinstance(series, Mapping):
        return {}
    return series


def _date_has_observation(parameter_payload: Mapping[str, Any], date_key: str) -> bool:
    for parameter_names in WEATHER_PARAMETER_PRIORITY.values():
        for parameter_name in parameter_names:
            value = _normalize_parameter_value(_parameter_series(parameter_payload, parameter_name).get(date_key))
            if value is not None:
                return True
    return False


def _normalize_parameter_value(value: Any) -> float | None:
    if value in MISSING_SENTINELS:
        return None
    numeric_value = float(value)
    if math.isnan(numeric_value):
        return None
    return numeric_value


def _parse_weather_date(date_key: str) -> date | None:
    try:
        return date.fromisoformat(f"{date_key[0:4]}-{date_key[4:6]}-{date_key[6:8]}")
    except ValueError:
        return None


def _normalize_identifier_for_column(column, identifier: Any) -> Any:
    if identifier is None:
        raise ServiceValidationError("weather_history delete key is missing field_id")
    if not isinstance(identifier, str):
        return identifier
    try:
        python_type = column.type.python_type
    except (AttributeError, NotImplementedError):
        return identifier
    try:
        if python_type is int:
            return int(identifier)
        if python_type is UUID:
            return UUID(identifier)
    except (TypeError, ValueError) as exc:
        raise ServiceValidationError(
            f"Cannot coerce weather_history field_id '{identifier}' for reset operations."
        ) from exc
    return identifier


def _chunked(values: Sequence[tuple[Any, date]], size: int) -> Iterable[Sequence[tuple[Any, date]]]:
    for start_index in range(0, len(values), size):
        yield values[start_index : start_index + size]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IngestionVerificationError(message)
