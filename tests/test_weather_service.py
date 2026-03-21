from datetime import date

from app.models.enums import WaterSourceType
from app.models.field import Field
from app.models.weather_history import WeatherHistory
from app.services.weather_service import WeatherService


def _create_field(db, **overrides) -> Field:
    values = {
        "name": "Weather Field",
        "location_name": "Climate Valley",
        "latitude": 39.1,
        "longitude": -94.5,
        "area_hectares": 10.0,
        "elevation_meters": 220.0,
        "slope_percent": 3.0,
        "irrigation_available": True,
        "water_source_type": WaterSourceType.WELL,
        "infrastructure_score": 70,
        "drainage_quality": "good",
    }
    values.update(overrides)
    field = Field(**values)
    db.add(field)
    db.flush()
    return field


def _add_weather_record(db, field_id: int, **overrides) -> WeatherHistory:
    values = {
        "field_id": field_id,
        "date": date(2024, 1, 1),
        "min_temp": 5.0,
        "max_temp": 14.0,
        "avg_temp": 9.0,
        "rainfall_mm": 2.0,
        "humidity": 60.0,
        "wind_speed": 10.0,
        "solar_radiation": 16.0,
        "et0": 3.0,
    }
    values.update(overrides)
    record = WeatherHistory(**values)
    db.add(record)
    return record


def test_get_recent_weather_returns_newest_first_with_latest_date_anchor(db):
    field = _create_field(db)
    _add_weather_record(db, field.id, date=date(2024, 1, 1), min_temp=0.0, max_temp=4.0, avg_temp=2.0)
    _add_weather_record(db, field.id, date=date(2024, 1, 20), min_temp=4.0, max_temp=10.0, avg_temp=7.0)
    _add_weather_record(db, field.id, date=date(2024, 2, 15), min_temp=8.0, max_temp=14.0, avg_temp=11.0)
    db.commit()

    service = WeatherService(db)
    recent_weather = service.get_recent_weather(field.id, days=30)

    assert [record.date for record in recent_weather] == [date(2024, 2, 15), date(2024, 1, 20)]


def test_get_recent_weather_returns_empty_list_when_no_data_exists(db):
    field = _create_field(db)

    service = WeatherService(db)

    assert service.get_recent_weather(field.id, days=30) == []


def test_get_climate_summary_computes_expected_metrics(db):
    field = _create_field(db)
    _add_weather_record(
        db,
        field.id,
        date=date(2024, 1, 2),
        min_temp=-2.0,
        max_temp=5.0,
        avg_temp=1.0,
        rainfall_mm=10.0,
    )
    _add_weather_record(
        db,
        field.id,
        date=date(2024, 6, 15),
        min_temp=18.0,
        max_temp=37.0,
        avg_temp=27.0,
        rainfall_mm=2.0,
    )
    _add_weather_record(
        db,
        field.id,
        date=date(2024, 12, 31),
        min_temp=5.0,
        max_temp=34.0,
        avg_temp=20.0,
        rainfall_mm=0.5,
    )
    db.commit()

    service = WeatherService(db)
    summary = service.get_climate_summary(field.id, days=365)

    assert summary is not None
    assert summary.avg_temp == 16.0
    assert summary.total_rainfall == 12.5
    assert summary.frost_days == 1
    assert summary.heat_days == 1


def test_get_climate_summary_honors_heat_threshold_override(db):
    field = _create_field(db)
    _add_weather_record(
        db,
        field.id,
        date=date(2024, 6, 15),
        min_temp=18.0,
        max_temp=37.0,
        avg_temp=27.0,
    )
    _add_weather_record(
        db,
        field.id,
        date=date(2024, 6, 16),
        min_temp=17.0,
        max_temp=34.0,
        avg_temp=25.0,
    )
    db.commit()

    service = WeatherService(db)
    summary = service.get_climate_summary(field.id, heat_threshold_c=33.0)

    assert summary is not None
    assert summary.heat_days == 2


def test_get_climate_summary_returns_none_when_no_data_exists(db):
    field = _create_field(db)

    service = WeatherService(db)

    assert service.get_climate_summary(field.id) is None
