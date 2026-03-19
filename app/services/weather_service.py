"""Weather-history service and climate summary helpers.

Example:
```python
from app.services.weather_service import WeatherService

service = WeatherService(db)

recent_weather = service.get_recent_weather(field_id=1, days=30)
climate_summary = service.get_climate_summary(field_id=1)

print(len(recent_weather))
print(climate_summary.avg_temp if climate_summary else None)
```
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Protocol, Sequence

from sqlalchemy.orm import Session

from app.models.field import Field
from app.models.weather_history import WeatherHistory
from app.schemas.weather_history import ClimateSummary, WeatherHistoryCreate


class WeatherProvider(Protocol):
    """Normalized provider interface for future weather API integrations."""

    def fetch_history_for_field(
        self,
        field_obj: Field,
        start_date: date,
        end_date: date,
    ) -> Sequence[WeatherHistoryCreate]:
        """Return normalized daily weather payloads for a field."""


class NoOpWeatherProvider:
    """Placeholder provider used until a real external integration is added."""

    def fetch_history_for_field(
        self,
        field_obj: Field,
        start_date: date,
        end_date: date,
    ) -> Sequence[WeatherHistoryCreate]:
        """Return no records until a concrete provider is configured."""

        _ = field_obj, start_date, end_date
        return []


class WeatherService:
    """Persistence and summary operations for field-scoped weather history."""

    def __init__(
        self,
        db: Session,
        provider: WeatherProvider | None = None,
    ) -> None:
        self.db = db
        self.provider = provider or NoOpWeatherProvider()

    def create_weather_history(self, weather_data: WeatherHistoryCreate) -> WeatherHistory:
        """Create and persist a weather-history record."""

        weather_record = WeatherHistory(**weather_data.model_dump())
        self.db.add(weather_record)
        self.db.commit()
        self.db.refresh(weather_record)
        return weather_record

    def get_recent_weather(self, field_id: int, days: int = 30) -> list[WeatherHistory]:
        """Return recent weather rows anchored to the latest stored field date."""

        if days <= 0:
            return []
        latest_date = self._get_latest_weather_date(field_id)
        if latest_date is None:
            return []

        start_date = self._window_start(latest_date, days)
        return (
            self.db.query(WeatherHistory)
            .filter(WeatherHistory.field_id == field_id)
            .filter(WeatherHistory.date >= start_date, WeatherHistory.date <= latest_date)
            .order_by(WeatherHistory.date.desc(), WeatherHistory.created_at.desc())
            .all()
        )

    def get_weather_window(
        self,
        field_id: int,
        *,
        start_date: date,
        end_date: date,
    ) -> list[WeatherHistory]:
        """Return weather records for a specific inclusive date window."""

        if start_date > end_date:
            return []
        return (
            self.db.query(WeatherHistory)
            .filter(WeatherHistory.field_id == field_id)
            .filter(WeatherHistory.date >= start_date, WeatherHistory.date <= end_date)
            .order_by(WeatherHistory.date.desc(), WeatherHistory.created_at.desc())
            .all()
        )

    def get_climate_summary(
        self,
        field_id: int,
        days: int = 365,
        heat_threshold_c: float = 35.0,
    ) -> ClimateSummary | None:
        """Return an aggregated climate summary anchored to the latest stored field date."""

        recent_weather = self.get_recent_weather(field_id, days=days)
        if not recent_weather:
            return None

        avg_temp = round(sum(record.avg_temp for record in recent_weather) / len(recent_weather), 2)
        total_rainfall = round(sum(record.rainfall_mm for record in recent_weather), 2)
        frost_days = sum(1 for record in recent_weather if record.min_temp < 0)
        heat_days = sum(1 for record in recent_weather if record.max_temp > heat_threshold_c)

        return ClimateSummary(
            avg_temp=avg_temp,
            total_rainfall=total_rainfall,
            frost_days=frost_days,
            heat_days=heat_days,
        )

    def _get_latest_weather_date(self, field_id: int) -> date | None:
        latest_record = (
            self.db.query(WeatherHistory)
            .filter(WeatherHistory.field_id == field_id)
            .order_by(WeatherHistory.date.desc(), WeatherHistory.created_at.desc())
            .first()
        )
        return latest_record.date if latest_record is not None else None

    @staticmethod
    def _window_start(latest_date: date, days: int) -> date:
        return latest_date - timedelta(days=days - 1)
