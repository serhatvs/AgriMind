from datetime import date

from app.services.climate_feature_builder import ClimateFeatureBuilder, ClimateObservation


def test_build_summary_computes_recent_climate_aggregates():
    builder = ClimateFeatureBuilder()

    summary = builder.build_summary(
        [
            ClimateObservation(
                observation_date=date(2026, 3, 1),
                min_temp=-1.0,
                max_temp=16.0,
                avg_temp=8.0,
                rainfall_mm=12.0,
                humidity=64.0,
                wind_speed=4.0,
                solar_radiation=14.0,
            ),
            ClimateObservation(
                observation_date=date(2026, 3, 2),
                min_temp=7.0,
                max_temp=36.0,
                avg_temp=21.0,
                rainfall_mm=4.5,
                humidity=58.0,
                wind_speed=6.0,
                solar_radiation=19.0,
            ),
        ],
        lookback_days=30,
        heat_day_threshold=35.0,
    )

    assert summary is not None
    assert summary.avg_temp == 14.5
    assert summary.min_observed_temp == -1.0
    assert summary.max_observed_temp == 36.0
    assert summary.total_rainfall == 16.5
    assert summary.avg_humidity == 61.0
    assert summary.avg_wind_speed == 5.0
    assert summary.avg_solar_radiation == 16.5
    assert summary.frost_days == 1
    assert summary.heat_days == 1
    assert summary.weather_record_count == 2
    assert summary.coverage_ratio == 0.0667


def test_observation_from_mapping_supports_weather_date_column():
    observation = ClimateFeatureBuilder.observation_from_mapping(
        {
            "weather_date": date(2026, 3, 20),
            "min_temp": 5,
            "max_temp": 15,
            "avg_temp": 10,
            "rainfall_mm": 2.5,
            "humidity": 70,
            "wind_speed": 3.5,
            "solar_radiation": 12.5,
        },
        date_column_name="weather_date",
    )

    assert observation is not None
    assert observation.observation_date == date(2026, 3, 20)
    assert observation.avg_temp == 10.0
