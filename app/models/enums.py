"""Shared domain enums for SQLAlchemy models and schemas."""

from enum import Enum


class FieldAspect(str, Enum):
    """Compass aspect values for a field's predominant orientation."""

    FLAT = "flat"
    NORTH = "north"
    NORTHEAST = "northeast"
    EAST = "east"
    SOUTHEAST = "southeast"
    SOUTH = "south"
    SOUTHWEST = "southwest"
    WEST = "west"
    NORTHWEST = "northwest"


class WaterSourceType(str, Enum):
    """Supported irrigation water source categories."""

    NONE = "none"
    CANAL = "canal"
    RIVER = "river"
    RESERVOIR = "reservoir"
    WELL = "well"
    BOREHOLE = "borehole"
    RAINWATER_HARVEST = "rainwater_harvest"
    MUNICIPAL = "municipal"
    MIXED = "mixed"


class WaterRequirementLevel(str, Enum):
    """Relative crop water demand levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CropDrainageRequirement(str, Enum):
    """Supported crop drainage requirement classes."""

    POOR = "poor"
    MODERATE = "moderate"
    GOOD = "good"
    EXCELLENT = "excellent"


class CropSensitivityLevel(str, Enum):
    """Relative crop sensitivity levels used for abiotic stress traits."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CropPreferenceLevel(str, Enum):
    """Relative preference or tolerance levels for qualitative crop traits."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
