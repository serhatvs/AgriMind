"""Services for loading field targets used by weather ingestion runners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.reflection import reflect_tables


@dataclass(frozen=True, slots=True)
class FieldCoordinateTarget:
    """Field identifier plus coordinates needed for external weather fetches."""

    field_id: int | str
    field_name: str
    latitude: float
    longitude: float


class FieldCoordinateService:
    """Load fields that have coordinates and can be queried against weather APIs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_fields_with_coordinates(self) -> list[FieldCoordinateTarget]:
        """Return all fields that have both latitude and longitude values."""

        fields_table = reflect_tables(self.db, "fields")["fields"]
        rows = self.db.execute(
            select(fields_table)
            .where(fields_table.c.latitude.is_not(None))
            .where(fields_table.c.longitude.is_not(None))
            .order_by(fields_table.c.name.asc())
        ).mappings().all()
        return [
            FieldCoordinateTarget(
                field_id=self._normalize_identifier(row.get("id")),
                field_name=str(row.get("name") or ""),
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
            )
            for row in rows
        ]

    @staticmethod
    def _normalize_identifier(value: Any) -> int | str:
        if isinstance(value, (int, str)):
            return value
        return str(value)
