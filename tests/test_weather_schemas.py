from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.weather_history import WeatherHistoryCreate


def test_weather_history_create_accepts_valid_payload():
    weather = WeatherHistoryCreate(
        field_id=1,
        date=date(2026, 3, 19),
        min_temp=8.0,
        max_temp=20.0,
        avg_temp=14.0,
        rainfall_mm=5.2,
        humidity=62.0,
        wind_speed=12.5,
        solar_radiation=18.4,
        et0=3.7,
    )

    assert weather.field_id == 1
    assert weather.avg_temp == 14.0


def test_weather_history_create_rejects_invalid_temperature_order():
    with pytest.raises(ValidationError):
        WeatherHistoryCreate(
            field_id=1,
            date=date(2026, 3, 19),
            min_temp=18.0,
            max_temp=20.0,
            avg_temp=14.0,
            rainfall_mm=5.2,
            humidity=62.0,
            wind_speed=12.5,
        )


def test_weather_history_create_rejects_invalid_humidity():
    with pytest.raises(ValidationError):
        WeatherHistoryCreate(
            field_id=1,
            date=date(2026, 3, 19),
            min_temp=8.0,
            max_temp=20.0,
            avg_temp=14.0,
            rainfall_mm=5.2,
            humidity=120.0,
            wind_speed=12.5,
        )


def test_weather_history_create_rejects_negative_optional_metrics():
    with pytest.raises(ValidationError):
        WeatherHistoryCreate(
            field_id=1,
            date=date(2026, 3, 19),
            min_temp=8.0,
            max_temp=20.0,
            avg_temp=14.0,
            rainfall_mm=5.2,
            humidity=62.0,
            wind_speed=12.5,
            solar_radiation=-1.0,
        )
