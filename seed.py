"""Deterministic MVP seed script for AgriMind.

Run:
    python seed.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import random

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models.crop_price import CropPrice
from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    FieldAspect,
    ManagementNeedLevel,
    WaterRequirementLevel,
    WaterSourceType,
)
from app.models.field import Field
from app.models.field_crop_cycle import FieldCropCycle
from app.models.input_cost import InputCost
from app.models.soil_test import SoilTest
from app.models.weather_history import WeatherHistory


SEED_TAG = "[agrimind-mvp-seed:v2]"
SEED_RANDOM_SEED = 20260319
LEGACY_FIELD_NAMES = (
    "North Valley Farm",
    "South Meadow",
    "East Ridge Plot",
    "West Flatlands",
    "Central Basin",
)


@dataclass(frozen=True, slots=True)
class CropSeedSpec:
    slug: str
    crop_name: str
    scientific_name: str
    ideal_ph_min: float
    ideal_ph_max: float
    tolerable_ph_min: float
    tolerable_ph_max: float
    water_requirement_level: WaterRequirementLevel
    drainage_requirement: CropDrainageRequirement
    frost_sensitivity: CropSensitivityLevel
    heat_sensitivity: CropSensitivityLevel
    salinity_tolerance: CropPreferenceLevel
    rooting_depth_cm: float
    slope_tolerance: float
    optimal_temp_min_c: float
    optimal_temp_max_c: float
    rainfall_requirement_mm: float
    frost_tolerance_days: int
    heat_tolerance_days: int
    target_nitrogen_ppm: float
    target_phosphorus_ppm: float
    target_potassium_ppm: float
    organic_matter_preference: CropPreferenceLevel
    growth_stages: list[dict[str, object]]
    price_per_ton: float
    fertilizer_cost: float
    water_cost: float
    labor_cost: float
    description: str


@dataclass(frozen=True, slots=True)
class FieldArchetype:
    key: str
    label: str
    location_prefix: str
    base_latitude: float
    base_longitude: float
    area_range: tuple[float, float]
    slope_range: tuple[float, float]
    elevation_range: tuple[float, float]
    infrastructure_range: tuple[int, int]
    drainage_options: tuple[str, ...]
    soil_drainage_options: tuple[str, ...]
    aspect_options: tuple[FieldAspect, ...]
    irrigation_count: int
    irrigation_sources: tuple[WaterSourceType, ...]
    soil_textures: tuple[str, ...]
    ph_range: tuple[float, float]
    ec_range: tuple[float, float]
    organic_matter_range: tuple[float, float]
    depth_range: tuple[float, float]
    water_holding_range: tuple[float, float]
    description: str


@dataclass(frozen=True, slots=True)
class FieldSeedSpec:
    slug: str
    archetype_key: str
    name: str
    location_name: str
    latitude: float
    longitude: float
    area_hectares: float
    elevation_meters: float
    slope_percent: float
    aspect: FieldAspect
    irrigation_available: bool
    water_source_type: WaterSourceType
    infrastructure_score: int
    drainage_quality: str
    description: str


@dataclass(frozen=True, slots=True)
class SoilSeedSpec:
    field_slug: str
    sample_date: datetime
    ph: float
    ec: float
    organic_matter_percent: float
    nitrogen_ppm: float
    phosphorus_ppm: float
    potassium_ppm: float
    calcium_ppm: float
    magnesium_ppm: float
    texture_class: str
    drainage_class: str
    depth_cm: float
    water_holding_capacity: float
    description: str


@dataclass(frozen=True, slots=True)
class CropCycleSeedSpec:
    field_slug: str
    crop_slug: str
    sowing_date: date
    current_stage: str


FIELD_ARCHETYPES = (
    FieldArchetype(
        key="river-valley",
        label="River Valley",
        location_prefix="Sacramento River Valley",
        base_latitude=38.58,
        base_longitude=-121.50,
        area_range=(8.0, 32.0),
        slope_range=(0.3, 3.0),
        elevation_range=(12.0, 58.0),
        infrastructure_range=(75, 94),
        drainage_options=("good", "excellent"),
        soil_drainage_options=("good", "excellent"),
        aspect_options=(FieldAspect.FLAT, FieldAspect.EAST, FieldAspect.SOUTH),
        irrigation_count=8,
        irrigation_sources=(
            WaterSourceType.CANAL,
            WaterSourceType.RIVER,
            WaterSourceType.WELL,
            WaterSourceType.RESERVOIR,
        ),
        soil_textures=("loam", "silt loam", "clay loam"),
        ph_range=(5.8, 6.8),
        ec_range=(0.4, 1.4),
        organic_matter_range=(3.0, 6.2),
        depth_range=(110.0, 180.0),
        water_holding_range=(20.0, 32.0),
        description="Irrigated alluvial parcels suited to water-demanding crops.",
    ),
    FieldArchetype(
        key="grain-belt",
        label="Grain Belt",
        location_prefix="Central Kansas Grain Belt",
        base_latitude=39.20,
        base_longitude=-96.60,
        area_range=(12.0, 48.0),
        slope_range=(2.0, 8.5),
        elevation_range=(350.0, 520.0),
        infrastructure_range=(55, 82),
        drainage_options=("moderate", "good"),
        soil_drainage_options=("moderate", "good"),
        aspect_options=(FieldAspect.NORTH, FieldAspect.SOUTH, FieldAspect.EAST, FieldAspect.WEST),
        irrigation_count=4,
        irrigation_sources=(WaterSourceType.WELL, WaterSourceType.CANAL),
        soil_textures=("silt loam", "loam", "clay loam"),
        ph_range=(6.0, 7.2),
        ec_range=(0.6, 1.8),
        organic_matter_range=(2.2, 4.5),
        depth_range=(100.0, 170.0),
        water_holding_range=(18.0, 30.0),
        description="Rolling cereal acreage with moderate slopes and mixed irrigation.",
    ),
    FieldArchetype(
        key="upland-terrace",
        label="Upland Terrace",
        location_prefix="Texas High Plains Terrace",
        base_latitude=34.90,
        base_longitude=-101.80,
        area_range=(18.0, 60.0),
        slope_range=(4.0, 12.0),
        elevation_range=(820.0, 1150.0),
        infrastructure_range=(35, 70),
        drainage_options=("moderate", "good"),
        soil_drainage_options=("moderate", "good"),
        aspect_options=(FieldAspect.SOUTH, FieldAspect.SOUTHEAST, FieldAspect.WEST, FieldAspect.SOUTHWEST),
        irrigation_count=2,
        irrigation_sources=(WaterSourceType.WELL, WaterSourceType.BOREHOLE),
        soil_textures=("sandy loam", "loam", "gravelly loam"),
        ph_range=(7.0, 8.1),
        ec_range=(1.4, 3.4),
        organic_matter_range=(0.8, 2.6),
        depth_range=(70.0, 125.0),
        water_holding_range=(10.0, 22.0),
        description="Semi-arid upland fields with alkaline soils and limited water.",
    ),
    FieldArchetype(
        key="foothill-orchard",
        label="Foothill Orchard",
        location_prefix="Sierra Foothill Orchard Belt",
        base_latitude=39.00,
        base_longitude=-120.80,
        area_range=(4.0, 18.0),
        slope_range=(5.0, 16.0),
        elevation_range=(200.0, 820.0),
        infrastructure_range=(60, 90),
        drainage_options=("good", "excellent"),
        soil_drainage_options=("good", "excellent"),
        aspect_options=(FieldAspect.EAST, FieldAspect.SOUTHEAST, FieldAspect.SOUTH, FieldAspect.SOUTHWEST),
        irrigation_count=8,
        irrigation_sources=(WaterSourceType.WELL, WaterSourceType.RESERVOIR, WaterSourceType.RAINWATER_HARVEST),
        soil_textures=("loam", "clay loam", "gravelly loam"),
        ph_range=(5.4, 6.6),
        ec_range=(0.3, 1.2),
        organic_matter_range=(3.2, 6.8),
        depth_range=(90.0, 160.0),
        water_holding_range=(16.0, 28.0),
        description="Higher-elevation berry and orchard parcels with strong drainage.",
    ),
    FieldArchetype(
        key="alluvial-plain",
        label="Alluvial Plain",
        location_prefix="Mississippi Alluvial Plain",
        base_latitude=33.50,
        base_longitude=-91.20,
        area_range=(14.0, 50.0),
        slope_range=(0.2, 4.0),
        elevation_range=(20.0, 110.0),
        infrastructure_range=(58, 88),
        drainage_options=("poor", "moderate", "good"),
        soil_drainage_options=("poor", "moderate", "good"),
        aspect_options=(FieldAspect.FLAT, FieldAspect.NORTH, FieldAspect.EAST, FieldAspect.SOUTH),
        irrigation_count=6,
        irrigation_sources=(WaterSourceType.RIVER, WaterSourceType.CANAL, WaterSourceType.RESERVOIR, WaterSourceType.WELL),
        soil_textures=("silt loam", "silty clay loam", "clay loam"),
        ph_range=(5.8, 7.0),
        ec_range=(0.6, 2.2),
        organic_matter_range=(2.5, 5.5),
        depth_range=(100.0, 190.0),
        water_holding_range=(24.0, 38.0),
        description="Low-slope floodplain ground with heavier soils and mixed drainage.",
    ),
)


def _seed_note(entity: str, slug: str, description: str) -> str:
    return f"{SEED_TAG} {entity}_slug={slug} | {description}"


def _extract_seed_slug(notes: str | None, entity: str) -> str | None:
    prefix = f"{SEED_TAG} {entity}_slug="
    if not notes or not notes.startswith(prefix):
        return None
    return notes[len(prefix) :].split(" | ", maxsplit=1)[0]


def _round(value: float, digits: int = 1) -> float:
    return round(value, digits)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _cycle(options: tuple, index: int):
    return options[(index - 1) % len(options)]


def build_crop_specs() -> list[CropSeedSpec]:
    """Return the canonical MVP crop profiles used for demo ranking."""

    return [
        CropSeedSpec(
            slug="blackberry",
            crop_name="Blackberry",
            scientific_name="Rubus fruticosus",
            ideal_ph_min=5.5,
            ideal_ph_max=6.5,
            tolerable_ph_min=5.2,
            tolerable_ph_max=6.8,
            water_requirement_level=WaterRequirementLevel.HIGH,
            drainage_requirement=CropDrainageRequirement.GOOD,
            frost_sensitivity=CropSensitivityLevel.MEDIUM,
            heat_sensitivity=CropSensitivityLevel.MEDIUM,
            salinity_tolerance=CropPreferenceLevel.LOW,
            rooting_depth_cm=90.0,
            slope_tolerance=14.0,
            optimal_temp_min_c=16.0,
            optimal_temp_max_c=24.0,
            rainfall_requirement_mm=900.0,
            frost_tolerance_days=15,
            heat_tolerance_days=20,
            target_nitrogen_ppm=42.0,
            target_phosphorus_ppm=24.0,
            target_potassium_ppm=210.0,
            organic_matter_preference=CropPreferenceLevel.HIGH,
            growth_stages=[
                {
                    "name": "budbreak",
                    "duration_days": 14,
                    "irrigation_need": ManagementNeedLevel.MEDIUM.value,
                    "fertilizer_need": ManagementNeedLevel.MEDIUM.value,
                },
                {
                    "name": "flowering",
                    "duration_days": 21,
                    "irrigation_need": ManagementNeedLevel.HIGH.value,
                    "fertilizer_need": ManagementNeedLevel.HIGH.value,
                },
                {
                    "name": "fruit_fill",
                    "duration_days": 28,
                    "irrigation_need": ManagementNeedLevel.HIGH.value,
                    "fertilizer_need": ManagementNeedLevel.MEDIUM.value,
                },
            ],
            price_per_ton=1850.0,
            fertilizer_cost=320.0,
            water_cost=240.0,
            labor_cost=410.0,
            description="Bramble crop profile tuned to acidic, well-drained foothill sites.",
        ),
        CropSeedSpec(
            slug="corn",
            crop_name="Corn",
            scientific_name="Zea mays",
            ideal_ph_min=6.0,
            ideal_ph_max=6.8,
            tolerable_ph_min=5.8,
            tolerable_ph_max=7.2,
            water_requirement_level=WaterRequirementLevel.HIGH,
            drainage_requirement=CropDrainageRequirement.MODERATE,
            frost_sensitivity=CropSensitivityLevel.HIGH,
            heat_sensitivity=CropSensitivityLevel.MEDIUM,
            salinity_tolerance=CropPreferenceLevel.MODERATE,
            rooting_depth_cm=150.0,
            slope_tolerance=6.0,
            optimal_temp_min_c=18.0,
            optimal_temp_max_c=30.0,
            rainfall_requirement_mm=650.0,
            frost_tolerance_days=2,
            heat_tolerance_days=25,
            target_nitrogen_ppm=60.0,
            target_phosphorus_ppm=28.0,
            target_potassium_ppm=220.0,
            organic_matter_preference=CropPreferenceLevel.MODERATE,
            growth_stages=[
                {
                    "name": "germination",
                    "duration_days": 7,
                    "irrigation_need": ManagementNeedLevel.MEDIUM.value,
                    "fertilizer_need": ManagementNeedLevel.LOW.value,
                },
                {
                    "name": "vegetative",
                    "duration_days": 21,
                    "irrigation_need": ManagementNeedLevel.HIGH.value,
                    "fertilizer_need": ManagementNeedLevel.HIGH.value,
                },
                {
                    "name": "reproductive",
                    "duration_days": 18,
                    "irrigation_need": ManagementNeedLevel.HIGH.value,
                    "fertilizer_need": ManagementNeedLevel.MEDIUM.value,
                },
            ],
            price_per_ton=210.0,
            fertilizer_cost=240.0,
            water_cost=165.0,
            labor_cost=130.0,
            description="High-water grain crop profile for deeper irrigated fields.",
        ),
        CropSeedSpec(
            slug="wheat",
            crop_name="Wheat",
            scientific_name="Triticum aestivum",
            ideal_ph_min=6.0,
            ideal_ph_max=7.0,
            tolerable_ph_min=5.5,
            tolerable_ph_max=7.5,
            water_requirement_level=WaterRequirementLevel.MEDIUM,
            drainage_requirement=CropDrainageRequirement.GOOD,
            frost_sensitivity=CropSensitivityLevel.MEDIUM,
            heat_sensitivity=CropSensitivityLevel.MEDIUM,
            salinity_tolerance=CropPreferenceLevel.LOW,
            rooting_depth_cm=120.0,
            slope_tolerance=12.0,
            optimal_temp_min_c=12.0,
            optimal_temp_max_c=22.0,
            rainfall_requirement_mm=450.0,
            frost_tolerance_days=25,
            heat_tolerance_days=18,
            target_nitrogen_ppm=45.0,
            target_phosphorus_ppm=20.0,
            target_potassium_ppm=180.0,
            organic_matter_preference=CropPreferenceLevel.MODERATE,
            growth_stages=[
                {
                    "name": "establishment",
                    "duration_days": 10,
                    "irrigation_need": ManagementNeedLevel.LOW.value,
                    "fertilizer_need": ManagementNeedLevel.LOW.value,
                },
                {
                    "name": "tillering",
                    "duration_days": 24,
                    "irrigation_need": ManagementNeedLevel.MEDIUM.value,
                    "fertilizer_need": ManagementNeedLevel.HIGH.value,
                },
                {
                    "name": "grain_fill",
                    "duration_days": 18,
                    "irrigation_need": ManagementNeedLevel.MEDIUM.value,
                    "fertilizer_need": ManagementNeedLevel.MEDIUM.value,
                },
            ],
            price_per_ton=255.0,
            fertilizer_cost=165.0,
            water_cost=60.0,
            labor_cost=95.0,
            description="Benchmark cereal profile for moderately drained grain-belt soils.",
        ),
        CropSeedSpec(
            slug="sunflower",
            crop_name="Sunflower",
            scientific_name="Helianthus annuus",
            ideal_ph_min=6.2,
            ideal_ph_max=7.2,
            tolerable_ph_min=5.8,
            tolerable_ph_max=7.8,
            water_requirement_level=WaterRequirementLevel.LOW,
            drainage_requirement=CropDrainageRequirement.MODERATE,
            frost_sensitivity=CropSensitivityLevel.MEDIUM,
            heat_sensitivity=CropSensitivityLevel.LOW,
            salinity_tolerance=CropPreferenceLevel.HIGH,
            rooting_depth_cm=170.0,
            slope_tolerance=14.0,
            optimal_temp_min_c=18.0,
            optimal_temp_max_c=30.0,
            rainfall_requirement_mm=400.0,
            frost_tolerance_days=3,
            heat_tolerance_days=35,
            target_nitrogen_ppm=36.0,
            target_phosphorus_ppm=18.0,
            target_potassium_ppm=190.0,
            organic_matter_preference=CropPreferenceLevel.LOW,
            growth_stages=[
                {
                    "name": "emergence",
                    "duration_days": 9,
                    "irrigation_need": ManagementNeedLevel.LOW.value,
                    "fertilizer_need": ManagementNeedLevel.LOW.value,
                },
                {
                    "name": "vegetative",
                    "duration_days": 20,
                    "irrigation_need": ManagementNeedLevel.MEDIUM.value,
                    "fertilizer_need": ManagementNeedLevel.MEDIUM.value,
                },
                {
                    "name": "flowering",
                    "duration_days": 16,
                    "irrigation_need": ManagementNeedLevel.MEDIUM.value,
                    "fertilizer_need": ManagementNeedLevel.HIGH.value,
                },
            ],
            price_per_ton=430.0,
            fertilizer_cost=145.0,
            water_cost=45.0,
            labor_cost=90.0,
            description="Drought-tolerant oilseed profile suited to lower-input parcels.",
        ),
        CropSeedSpec(
            slug="chickpea",
            crop_name="Chickpea",
            scientific_name="Cicer arietinum",
            ideal_ph_min=6.2,
            ideal_ph_max=7.4,
            tolerable_ph_min=5.8,
            tolerable_ph_max=8.0,
            water_requirement_level=WaterRequirementLevel.LOW,
            drainage_requirement=CropDrainageRequirement.GOOD,
            frost_sensitivity=CropSensitivityLevel.MEDIUM,
            heat_sensitivity=CropSensitivityLevel.MEDIUM,
            salinity_tolerance=CropPreferenceLevel.MODERATE,
            rooting_depth_cm=110.0,
            slope_tolerance=10.0,
            optimal_temp_min_c=16.0,
            optimal_temp_max_c=28.0,
            rainfall_requirement_mm=350.0,
            frost_tolerance_days=8,
            heat_tolerance_days=20,
            target_nitrogen_ppm=24.0,
            target_phosphorus_ppm=16.0,
            target_potassium_ppm=150.0,
            organic_matter_preference=CropPreferenceLevel.MODERATE,
            growth_stages=[
                {
                    "name": "emergence",
                    "duration_days": 8,
                    "irrigation_need": ManagementNeedLevel.LOW.value,
                    "fertilizer_need": ManagementNeedLevel.LOW.value,
                },
                {
                    "name": "branching",
                    "duration_days": 18,
                    "irrigation_need": ManagementNeedLevel.MEDIUM.value,
                    "fertilizer_need": ManagementNeedLevel.MEDIUM.value,
                },
                {
                    "name": "pod_fill",
                    "duration_days": 20,
                    "irrigation_need": ManagementNeedLevel.MEDIUM.value,
                    "fertilizer_need": ManagementNeedLevel.HIGH.value,
                },
            ],
            price_per_ton=610.0,
            fertilizer_cost=120.0,
            water_cost=35.0,
            labor_cost=105.0,
            description="Pulse crop profile for neutral to slightly alkaline, well-drained soils.",
        ),
    ]


def build_field_specs() -> list[FieldSeedSpec]:
    """Build 50 deterministic field payloads across five agronomic archetypes."""

    rng = random.Random(SEED_RANDOM_SEED)
    field_specs: list[FieldSeedSpec] = []

    for archetype in FIELD_ARCHETYPES:
        for index in range(1, 11):
            slug = f"{archetype.key}-{index:02d}"
            lat_offset = ((index - 5.5) * 0.035) + rng.uniform(-0.008, 0.008)
            lon_offset = ((5.5 - index) * 0.04) + rng.uniform(-0.008, 0.008)
            slope_percent = _round(rng.uniform(*archetype.slope_range), 1)
            irrigation_available = index <= archetype.irrigation_count
            water_source_type = (
                _cycle(archetype.irrigation_sources, index)
                if irrigation_available
                else WaterSourceType.NONE
            )
            aspect = FieldAspect.FLAT if slope_percent < 1.0 else _cycle(archetype.aspect_options, index)
            drainage_quality = _cycle(archetype.drainage_options, index)

            field_specs.append(
                FieldSeedSpec(
                    slug=slug,
                    archetype_key=archetype.key,
                    name=f"{archetype.label} Block {index:02d}",
                    location_name=f"{archetype.location_prefix} Sector {index:02d}",
                    latitude=_round(archetype.base_latitude + lat_offset, 4),
                    longitude=_round(archetype.base_longitude + lon_offset, 4),
                    area_hectares=_round(rng.uniform(*archetype.area_range), 1),
                    elevation_meters=_round(rng.uniform(*archetype.elevation_range), 1),
                    slope_percent=slope_percent,
                    aspect=aspect,
                    irrigation_available=irrigation_available,
                    water_source_type=water_source_type,
                    infrastructure_score=rng.randint(*archetype.infrastructure_range),
                    drainage_quality=drainage_quality,
                    description=archetype.description,
                )
            )

    return field_specs


def build_soil_specs(field_specs: list[FieldSeedSpec]) -> list[SoilSeedSpec]:
    """Build one deterministic latest soil test for each seeded field."""

    rng = random.Random(SEED_RANDOM_SEED + 1)
    archetypes = {archetype.key: archetype for archetype in FIELD_ARCHETYPES}
    base_date = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    soil_specs: list[SoilSeedSpec] = []

    for offset, field_spec in enumerate(field_specs):
        archetype = archetypes[field_spec.archetype_key]
        texture_class = _cycle(archetype.soil_textures, offset + 1)
        drainage_class = (
            field_spec.drainage_quality
            if field_spec.drainage_quality in archetype.soil_drainage_options
            else _cycle(archetype.soil_drainage_options, offset + 1)
        )
        organic_matter_percent = _round(rng.uniform(*archetype.organic_matter_range), 1)
        water_holding_capacity = _round(rng.uniform(*archetype.water_holding_range), 1)
        depth_cm = _round(rng.uniform(*archetype.depth_range), 1)
        ph = _round(rng.uniform(*archetype.ph_range), 1)
        ec = _round(rng.uniform(*archetype.ec_range), 2)

        if field_spec.irrigation_available:
            nitrogen_base = 12.0
            phosphorus_base = 8.0
        else:
            nitrogen_base = 8.0
            phosphorus_base = 5.0

        nitrogen_ppm = _round(
            _clamp(nitrogen_base + organic_matter_percent * 8.5 + rng.uniform(-4.0, 8.0), 10.0, 75.0),
            1,
        )
        phosphorus_ppm = _round(
            _clamp(phosphorus_base + organic_matter_percent * 4.2 + rng.uniform(-2.0, 7.0), 8.0, 45.0),
            1,
        )
        potassium_ppm = _round(
            _clamp(70.0 + water_holding_capacity * 5.2 + rng.uniform(-25.0, 35.0), 70.0, 320.0),
            1,
        )
        calcium_ppm = _round(
            _clamp(650.0 + ph * 180.0 + rng.uniform(-120.0, 240.0), 900.0, 2400.0),
            1,
        )
        magnesium_ppm = _round(
            _clamp(70.0 + organic_matter_percent * 24.0 + rng.uniform(-15.0, 45.0), 100.0, 380.0),
            1,
        )

        soil_specs.append(
            SoilSeedSpec(
                field_slug=field_spec.slug,
                sample_date=base_date + timedelta(days=offset),
                ph=ph,
                ec=ec,
                organic_matter_percent=organic_matter_percent,
                nitrogen_ppm=nitrogen_ppm,
                phosphorus_ppm=phosphorus_ppm,
                potassium_ppm=potassium_ppm,
                calcium_ppm=calcium_ppm,
                magnesium_ppm=magnesium_ppm,
                texture_class=texture_class,
                drainage_class=drainage_class,
                depth_cm=depth_cm,
                water_holding_capacity=water_holding_capacity,
                description=f"Latest lab panel for {field_spec.name}.",
            )
        )

    return soil_specs


def build_crop_cycle_specs() -> list[CropCycleSeedSpec]:
    """Return the deterministic active crop cycles used for management demos."""

    return [
        CropCycleSeedSpec(
            field_slug="river-valley-01",
            crop_slug="corn",
            sowing_date=date(2026, 3, 1),
            current_stage="planned",
        ),
        CropCycleSeedSpec(
            field_slug="grain-belt-01",
            crop_slug="wheat",
            sowing_date=date(2026, 2, 20),
            current_stage="planned",
        ),
        CropCycleSeedSpec(
            field_slug="upland-terrace-01",
            crop_slug="sunflower",
            sowing_date=date(2026, 3, 5),
            current_stage="planned",
        ),
        CropCycleSeedSpec(
            field_slug="foothill-orchard-01",
            crop_slug="blackberry",
            sowing_date=date(2026, 2, 10),
            current_stage="planned",
        ),
        CropCycleSeedSpec(
            field_slug="alluvial-plain-01",
            crop_slug="chickpea",
            sowing_date=date(2026, 2, 25),
            current_stage="planned",
        ),
    ]


def _find_existing_crop(db: Session, crop_name: str) -> CropProfile | None:
    candidates = (
        db.query(CropProfile)
        .filter(CropProfile.crop_name == crop_name)
        .order_by(CropProfile.id.asc())
        .all()
    )
    if not candidates:
        return None

    for candidate in candidates:
        if candidate.notes and candidate.notes.startswith(SEED_TAG):
            return candidate
    return candidates[0]


def _cleanup_legacy_seed_fields(db: Session) -> int:
    """Remove the old hardcoded demo fields and their soil tests."""

    legacy_fields = (
        db.query(Field)
        .filter(
            Field.name.in_(LEGACY_FIELD_NAMES),
            or_(Field.notes.is_(None), Field.notes == ""),
        )
        .all()
    )
    removed = 0
    for legacy_field in legacy_fields:
        db.query(SoilTest).filter(SoilTest.field_id == legacy_field.id).delete(synchronize_session=False)
        db.delete(legacy_field)
        removed += 1
    return removed


def _upsert_crops(db: Session, crop_specs: list[CropSeedSpec]) -> dict[str, int]:
    """Create or update the canonical demo crop profiles."""

    stats = {"created": 0, "updated": 0}
    for spec in crop_specs:
        crop = _find_existing_crop(db, spec.crop_name)
        created = crop is None
        if created:
            crop = CropProfile(crop_name=spec.crop_name)
            db.add(crop)
            stats["created"] += 1
        else:
            stats["updated"] += 1

        crop.crop_name = spec.crop_name
        crop.scientific_name = spec.scientific_name
        crop.ideal_ph_min = spec.ideal_ph_min
        crop.ideal_ph_max = spec.ideal_ph_max
        crop.tolerable_ph_min = spec.tolerable_ph_min
        crop.tolerable_ph_max = spec.tolerable_ph_max
        crop.water_requirement_level = spec.water_requirement_level
        crop.drainage_requirement = spec.drainage_requirement
        crop.frost_sensitivity = spec.frost_sensitivity
        crop.heat_sensitivity = spec.heat_sensitivity
        crop.salinity_tolerance = spec.salinity_tolerance
        crop.rooting_depth_cm = spec.rooting_depth_cm
        crop.slope_tolerance = spec.slope_tolerance
        crop.optimal_temp_min_c = spec.optimal_temp_min_c
        crop.optimal_temp_max_c = spec.optimal_temp_max_c
        crop.rainfall_requirement_mm = spec.rainfall_requirement_mm
        crop.frost_tolerance_days = spec.frost_tolerance_days
        crop.heat_tolerance_days = spec.heat_tolerance_days
        crop.target_nitrogen_ppm = spec.target_nitrogen_ppm
        crop.target_phosphorus_ppm = spec.target_phosphorus_ppm
        crop.target_potassium_ppm = spec.target_potassium_ppm
        crop.organic_matter_preference = spec.organic_matter_preference
        crop.growth_stages = spec.growth_stages
        crop.notes = _seed_note("crop", spec.slug, spec.description)

        if crop.crop_price is None:
            crop.crop_price = CropPrice(price_per_ton=spec.price_per_ton)
        else:
            crop.crop_price.price_per_ton = spec.price_per_ton

        if crop.input_cost is None:
            crop.input_cost = InputCost(
                fertilizer_cost=spec.fertilizer_cost,
                water_cost=spec.water_cost,
                labor_cost=spec.labor_cost,
            )
        else:
            crop.input_cost.fertilizer_cost = spec.fertilizer_cost
            crop.input_cost.water_cost = spec.water_cost
            crop.input_cost.labor_cost = spec.labor_cost

    return stats


def _load_seed_crops_by_slug(db: Session) -> dict[str, CropProfile]:
    seed_crops = (
        db.query(CropProfile)
        .filter(CropProfile.notes.is_not(None), CropProfile.notes.like(f"{SEED_TAG} crop_slug=%"))
        .all()
    )
    crop_map: dict[str, CropProfile] = {}
    for crop in seed_crops:
        slug = _extract_seed_slug(crop.notes, "crop")
        if slug:
            crop_map[slug] = crop
    return crop_map


def _load_seed_fields_by_slug(db: Session) -> dict[str, Field]:
    seed_fields = (
        db.query(Field)
        .filter(Field.notes.is_not(None), Field.notes.like(f"{SEED_TAG} field_slug=%"))
        .all()
    )
    field_map: dict[str, Field] = {}
    for field in seed_fields:
        slug = _extract_seed_slug(field.notes, "field")
        if slug:
            field_map[slug] = field
    return field_map


def _delete_managed_fields(db: Session, fields: list[Field]) -> int:
    removed = 0
    for field in fields:
        db.query(SoilTest).filter(SoilTest.field_id == field.id).delete(synchronize_session=False)
        db.delete(field)
        removed += 1
    return removed


def _sync_fields(db: Session, field_specs: list[FieldSeedSpec]) -> tuple[dict[str, Field], dict[str, int]]:
    """Create, update, and prune seed-managed field records."""

    existing = _load_seed_fields_by_slug(db)
    wanted_slugs = {spec.slug for spec in field_specs}
    obsolete_fields = [field for slug, field in existing.items() if slug not in wanted_slugs]
    removed = _delete_managed_fields(db, obsolete_fields)

    field_by_slug: dict[str, Field] = {}
    stats = {"created": 0, "updated": 0, "removed": removed}
    for spec in field_specs:
        field = existing.get(spec.slug)
        created = field is None
        if created:
            field = Field(name=spec.name, location_name=spec.location_name, area_hectares=spec.area_hectares)
            db.add(field)
            stats["created"] += 1
        else:
            stats["updated"] += 1

        field.name = spec.name
        field.location_name = spec.location_name
        field.latitude = spec.latitude
        field.longitude = spec.longitude
        field.area_hectares = spec.area_hectares
        field.elevation_meters = spec.elevation_meters
        field.slope_percent = spec.slope_percent
        field.aspect = spec.aspect
        field.irrigation_available = spec.irrigation_available
        field.water_source_type = spec.water_source_type
        field.infrastructure_score = spec.infrastructure_score
        field.drainage_quality = spec.drainage_quality
        field.notes = _seed_note("field", spec.slug, spec.description)
        field_by_slug[spec.slug] = field

    db.flush()
    return field_by_slug, stats


def _replace_seed_soil_tests(
    db: Session,
    field_by_slug: dict[str, Field],
    soil_specs: list[SoilSeedSpec],
) -> dict[str, int]:
    """Replace only the seed-managed soil tests for the managed seed fields."""

    field_ids = [field.id for field in field_by_slug.values()]
    if field_ids:
        db.query(SoilTest).filter(
            SoilTest.field_id.in_(field_ids),
            SoilTest.notes.is_not(None),
            SoilTest.notes.like(f"{SEED_TAG} soil_slug=%"),
        ).delete(synchronize_session=False)

    for spec in soil_specs:
        db.add(
            SoilTest(
                field_id=field_by_slug[spec.field_slug].id,
                sample_date=spec.sample_date,
                ph=spec.ph,
                ec=spec.ec,
                organic_matter_percent=spec.organic_matter_percent,
                nitrogen_ppm=spec.nitrogen_ppm,
                phosphorus_ppm=spec.phosphorus_ppm,
                potassium_ppm=spec.potassium_ppm,
                calcium_ppm=spec.calcium_ppm,
                magnesium_ppm=spec.magnesium_ppm,
                texture_class=spec.texture_class,
                drainage_class=spec.drainage_class,
                depth_cm=spec.depth_cm,
                water_holding_capacity=spec.water_holding_capacity,
                notes=_seed_note("soil", spec.field_slug, spec.description),
            )
        )

    return {"replaced": len(soil_specs)}


def _upsert_seed_crop_cycles(
    db: Session,
    *,
    field_by_slug: dict[str, Field],
    crop_by_slug: dict[str, CropProfile],
    cycle_specs: list[CropCycleSeedSpec],
) -> dict[str, int]:
    """Upsert active crop cycles for the demo-managed management fields."""

    stats = {"created": 0, "updated": 0}
    for spec in cycle_specs:
        field = field_by_slug[spec.field_slug]
        crop = crop_by_slug[spec.crop_slug]
        cycle = db.query(FieldCropCycle).filter(FieldCropCycle.field_id == field.id).first()
        created = cycle is None
        if created:
            cycle = FieldCropCycle(
                field_id=field.id,
                crop_id=crop.id,
                sowing_date=spec.sowing_date,
                current_stage=spec.current_stage,
            )
            db.add(cycle)
            stats["created"] += 1
        else:
            stats["updated"] += 1

        cycle.crop_id = crop.id
        cycle.sowing_date = spec.sowing_date
        cycle.current_stage = spec.current_stage

    return stats


def _upsert_seed_weather_history(
    db: Session,
    *,
    field_by_slug: dict[str, Field],
    cycle_specs: list[CropCycleSeedSpec],
) -> dict[str, int]:
    """Upsert a recent weather window for the demo-managed management fields."""

    stats = {"created": 0, "updated": 0}
    window_end = date(2026, 3, 19)
    window_start = window_end - timedelta(days=27)

    for index, spec in enumerate(cycle_specs):
        field = field_by_slug[spec.field_slug]
        existing_records = {
            record.date: record
            for record in (
                db.query(WeatherHistory)
                .filter(WeatherHistory.field_id == field.id)
                .filter(WeatherHistory.date >= window_start, WeatherHistory.date <= window_end)
                .all()
            )
        }
        rng = random.Random(SEED_RANDOM_SEED + 200 + index)
        rainfall_bias = 0.8 if field.irrigation_available else 1.4

        for day_offset in range(28):
            observation_date = window_start + timedelta(days=day_offset)
            seasonal_offset = (day_offset % 7) - 3
            avg_temp = _round(14.0 + index * 1.8 + seasonal_offset * 0.6 + rng.uniform(-1.5, 1.5), 1)
            min_temp = _round(avg_temp - rng.uniform(4.0, 7.0), 1)
            max_temp = _round(avg_temp + rng.uniform(5.0, 8.0), 1)
            rainfall_mm = _round(max(0.0, rainfall_bias + rng.uniform(-0.6, 4.2)), 1)
            humidity = _round(_clamp(58.0 + rng.uniform(-10.0, 18.0), 35.0, 92.0), 1)
            wind_speed = _round(max(1.5, 6.0 + rng.uniform(-2.0, 5.0)), 1)
            solar_radiation = _round(max(6.0, 14.0 + rng.uniform(-2.5, 5.5)), 1)
            et0 = _round(max(0.5, 2.6 + rng.uniform(-0.8, 1.4)), 1)

            record = existing_records.get(observation_date)
            if record is None:
                record = WeatherHistory(field_id=field.id, date=observation_date)
                db.add(record)
                stats["created"] += 1
            else:
                stats["updated"] += 1

            record.min_temp = min_temp
            record.max_temp = max_temp
            record.avg_temp = avg_temp
            record.rainfall_mm = rainfall_mm
            record.humidity = humidity
            record.wind_speed = wind_speed
            record.solar_radiation = solar_radiation
            record.et0 = et0

    return stats


def seed(db: Session | None = None) -> None:
    """Seed deterministic MVP demo data into the configured database."""

    created_session = db is None
    if created_session:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()

    assert db is not None

    try:
        crop_specs = build_crop_specs()
        field_specs = build_field_specs()
        soil_specs = build_soil_specs(field_specs)
        cycle_specs = build_crop_cycle_specs()

        removed_legacy_fields = _cleanup_legacy_seed_fields(db)
        crop_stats = _upsert_crops(db, crop_specs)
        field_by_slug, field_stats = _sync_fields(db, field_specs)
        soil_stats = _replace_seed_soil_tests(db, field_by_slug, soil_specs)
        crop_by_slug = _load_seed_crops_by_slug(db)
        cycle_stats = _upsert_seed_crop_cycles(
            db,
            field_by_slug=field_by_slug,
            crop_by_slug=crop_by_slug,
            cycle_specs=cycle_specs,
        )
        weather_stats = _upsert_seed_weather_history(
            db,
            field_by_slug=field_by_slug,
            cycle_specs=cycle_specs,
        )

        db.commit()

        print(
            "Seed refresh complete: "
            f"{len(field_specs)} seed fields "
            f"({field_stats['created']} created, {field_stats['updated']} updated, {field_stats['removed']} removed, "
            f"{removed_legacy_fields} legacy cleaned), "
            f"{soil_stats['replaced']} soil tests replaced, "
            f"{len(crop_specs)} crops ({crop_stats['created']} created, {crop_stats['updated']} updated), "
            f"{cycle_stats['created'] + cycle_stats['updated']} active crop cycles synced, "
            f"{weather_stats['created'] + weather_stats['updated']} weather rows synced."
        )
        print("Run `python seed.py` to refresh the demo dataset.")
    except Exception:
        db.rollback()
        raise
    finally:
        if created_session:
            db.close()


def main() -> None:
    seed()


if __name__ == "__main__":
    main()
