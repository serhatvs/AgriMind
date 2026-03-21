from __future__ import annotations

from datetime import date

from app.ingestion.deduplication import (
    ExternalCropStatisticsDuplicateStrategy,
    WeatherHistoryDuplicateStrategy,
    collect_existing_keys,
    deduplicate_prepared_rows,
)
from app.ingestion.types import NormalizedRecord, PreparedRow
from app.ingestion.validators import (
    AllowedValuesValidator,
    FieldTypeValidator,
    NumericRangeValidator,
    RequiredFieldsValidator,
    validate_records,
)


def test_validate_records_returns_valid_and_skipped_rows_with_traceable_reasons():
    records = (
        NormalizedRecord(
            record_type="weather_history",
            source_identifier="field-1:2025-01-01",
            values={
                "field_id": "field-1",
                "weather_date": date(2025, 1, 1),
                "humidity": 61.0,
            },
            payload_type="json",
        ),
        NormalizedRecord(
            record_type="weather_history",
            source_identifier="field-1:2025-01-02",
            values={
                "field_id": "field-1",
                "humidity": 125.0,
            },
            payload_type="json",
        ),
    )

    result = validate_records(
        records,
        validators=(
            RequiredFieldsValidator("field_id", "weather_date"),
            FieldTypeValidator("weather_date", date),
            NumericRangeValidator("humidity", min_value=0, max_value=100, allow_none=False),
        ),
    )

    assert len(result.valid_records) == 1
    assert len(result.skipped_records) == 1
    assert result.skipped_records[0].source_identifier == "field-1:2025-01-02"
    assert result.skipped_records[0].stage == "validation"
    assert {reason.code for reason in result.skipped_records[0].reasons} == {
        "missing_required_field",
        "value_above_maximum",
    }


def test_deduplicate_prepared_rows_skips_weather_duplicates_with_traceable_reason():
    prepared_rows = (
        PreparedRow(
            source_identifier="field-1:2025-01-01",
            record_type="weather_history",
            values={"field_id": "field-1", "weather_date": date(2025, 1, 1)},
        ),
        PreparedRow(
            source_identifier="field-1:2025-01-02",
            record_type="weather_history",
            values={"field_id": "field-1", "weather_date": date(2025, 1, 2)},
        ),
        PreparedRow(
            source_identifier="field-1:2025-01-02:dup",
            record_type="weather_history",
            values={"field_id": "field-1", "weather_date": date(2025, 1, 2)},
        ),
    )
    strategy = WeatherHistoryDuplicateStrategy(date_column_name="weather_date")

    result = deduplicate_prepared_rows(
        prepared_rows,
        existing_keys=collect_existing_keys(
            ({"field_id": "field-1", "weather_date": date(2025, 1, 1)},),
            strategy,
        ),
        strategy=strategy,
    )

    assert len(result.unique_rows) == 1
    assert len(result.skipped_records) == 2
    assert result.skipped_records[0].stage == "deduplication"
    assert result.skipped_records[0].reasons[0].code == "duplicate_record"


def test_external_statistics_duplicate_strategy_normalizes_statistic_types():
    prepared_rows = (
        PreparedRow(
            source_identifier="us:maize:2023:production",
            record_type="external_crop_statistics",
            values={
                "source_name": "Mirror Feed",
                "country": "United States of America",
                "year": 2023,
                "crop_name": "Maize",
                "statistic_type": "production",
            },
        ),
    )
    strategy = ExternalCropStatisticsDuplicateStrategy()

    result = deduplicate_prepared_rows(
        prepared_rows,
        existing_keys=collect_existing_keys(
            (
                {
                    "source_name": "FAOSTAT",
                    "country": "United States of America",
                    "year": 2023,
                    "crop_name": "Maize",
                    "statistic_type": "PRODUCTION",
                },
            ),
            strategy,
        ),
        strategy=strategy,
    )

    assert len(result.unique_rows) == 0
    assert len(result.skipped_records) == 1
    assert result.skipped_records[0].reasons[0].code == "duplicate_record"


def test_allowed_values_validator_supports_reusable_normalizers():
    validator = AllowedValuesValidator(
        "statistic_type",
        ("production", "yield"),
        normalizer=lambda value: str(value).lower(),
    )

    issues = validator.validate(
        NormalizedRecord(
            record_type="external_crop_statistics",
            source_identifier="stat-1",
            values={"statistic_type": "YIELD"},
            payload_type="json",
        )
    )

    assert issues == []
