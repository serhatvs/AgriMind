"""Contracts for suitability-scoring providers."""

from __future__ import annotations

from typing import Protocol

from app.engines.scoring_types import SuitabilityResult
from app.models.crop_profile import CropProfile
from app.models.field import Field
from app.models.soil_test import SoilTest
from app.schemas.weather_history import ClimateSummary


class SuitabilityProvider(Protocol):
    """Provider contract for field/crop suitability scoring."""

    def calculate_suitability(
        self,
        field_obj: Field,
        crop: CropProfile,
        soil_test: SoilTest | None,
        climate_summary: ClimateSummary | None = None,
    ) -> SuitabilityResult:
        """Return a structured suitability result for the supplied inputs."""
