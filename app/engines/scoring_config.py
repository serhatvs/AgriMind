"""Typed loading for suitability scoring configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "scoring_weights.json"


@dataclass(frozen=True, slots=True)
class RangeBand:
    """Ideal and acceptable range thresholds for a qualitative preference."""

    ideal_min: float
    ideal_max: float
    acceptable_min: float
    acceptable_max: float


@dataclass(frozen=True, slots=True)
class SalinityBand:
    """Maximum electrical conductivity thresholds for a salinity tolerance band."""

    ideal_max: float
    acceptable_max: float


@dataclass(frozen=True, slots=True)
class SoilSubWeights:
    """Relative subweights within the soil compatibility dimension."""

    organic_matter: float
    rooting_depth: float
    salinity: float


@dataclass(frozen=True, slots=True)
class ThresholdConfig:
    """Thresholds and reference bands used by the scoring engine."""

    ph_blocker_delta: float
    rooting_depth_partial_ratio: float
    slope_zero_ratio: float
    organic_matter_bands: dict[str, RangeBand]
    ec_bands: dict[str, SalinityBand]


@dataclass(frozen=True, slots=True)
class SuitabilityScoringConfig:
    """Dimension weights and thresholds for the suitability engine."""

    soil_compatibility: float
    ph_compatibility: float
    drainage_compatibility: float
    water_availability_compatibility: float
    slope_compatibility: float
    soil_subweights: SoilSubWeights
    thresholds: ThresholdConfig

    @property
    def max_total_points(self) -> float:
        """Return the configured total points before normalization."""

        return (
            self.soil_compatibility
            + self.ph_compatibility
            + self.drainage_compatibility
            + self.water_availability_compatibility
            + self.slope_compatibility
        )


@lru_cache(maxsize=1)
def load_scoring_config(path: str | Path = CONFIG_PATH) -> SuitabilityScoringConfig:
    """Load and cache the suitability scoring config from disk."""

    config_path = Path(path)
    with config_path.open(encoding="utf-8") as file_handle:
        raw = json.load(file_handle)

    dimensions = raw["dimensions"]
    soil_config = raw["soil_compatibility"]
    thresholds = raw["thresholds"]

    soil_subweights = SoilSubWeights(**soil_config["subweights"])
    organic_matter_bands = {
        key: RangeBand(**band)
        for key, band in thresholds["organic_matter_bands"].items()
    }
    ec_bands = {
        key: SalinityBand(**band)
        for key, band in thresholds["ec_bands"].items()
    }

    threshold_config = ThresholdConfig(
        ph_blocker_delta=thresholds["ph_blocker_delta"],
        rooting_depth_partial_ratio=thresholds["rooting_depth_partial_ratio"],
        slope_zero_ratio=thresholds["slope_zero_ratio"],
        organic_matter_bands=organic_matter_bands,
        ec_bands=ec_bands,
    )

    return SuitabilityScoringConfig(
        soil_compatibility=dimensions["soil_compatibility"],
        ph_compatibility=dimensions["ph_compatibility"],
        drainage_compatibility=dimensions["drainage_compatibility"],
        water_availability_compatibility=dimensions["water_availability_compatibility"],
        slope_compatibility=dimensions["slope_compatibility"],
        soil_subweights=soil_subweights,
        thresholds=threshold_config,
    )
