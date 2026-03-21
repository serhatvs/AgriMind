"""Deterministic demo seed definitions for the live PostgreSQL schema."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from random import Random

from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    FieldAspect,
    WaterRequirementLevel,
    WaterSourceType,
)

SEED_TAG = "[agrimind-demo-seed:v1]"
SEED_RANDOM_SEED = 20260321
DEMO_WEATHER_END_DATE = date(2026, 3, 20)
DEMO_WEATHER_DAYS = 28


@dataclass(frozen=True, slots=True)
class CropSeedSpec:
    """Canonical crop profile payload used for demo ranking and scoring."""

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
    organic_matter_preference: CropPreferenceLevel
    description: str


@dataclass(frozen=True, slots=True)
class CropEconomicProfileSeedSpec:
    """Economic assumptions used to exercise profitability-aware ranking."""

    crop_slug: str
    crop_name: str
    average_market_price_per_unit: float
    price_unit: str
    base_cost_per_hectare: float
    irrigation_cost_factor: float
    fertilizer_cost_factor: float
    labor_cost_factor: float
    risk_cost_factor: float
    region: str | None
    description: str


@dataclass(frozen=True, slots=True)
class FieldSeedSpec:
    """Field payload tuned to exercise different ranking outcomes."""

    slug: str
    name: str
    location_name: str
    latitude: float
    longitude: float
    area_hectares: float
    slope_percent: float
    elevation_meters: float
    aspect: FieldAspect
    irrigation_available: bool
    water_source_type: WaterSourceType
    infrastructure_score: float
    weather_profile: str
    description: str


@dataclass(frozen=True, slots=True)
class SoilSeedSpec:
    """Latest soil test payload for a single demo field."""

    field_slug: str
    sample_date: date
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
class WeatherPattern:
    """Profile used to generate realistic recent weather for a region."""

    key: str
    base_avg_temp: float
    warming_trend_per_day: float
    diurnal_range: tuple[float, float]
    rainfall_cycle: tuple[float, ...]
    humidity_range: tuple[float, float]
    wind_range: tuple[float, float]
    solar_range: tuple[float, float]
    et0_range: tuple[float, float]


@dataclass(frozen=True, slots=True)
class WeatherSeedSpec:
    """Daily weather observation for a seeded field."""

    field_slug: str
    weather_date: date
    min_temp: float
    max_temp: float
    avg_temp: float
    rainfall_mm: float
    humidity: float
    wind_speed: float
    solar_radiation: float
    et0: float


@dataclass(frozen=True, slots=True)
class SeedDataset:
    """Bundle of all deterministic demo seed definitions."""

    crops: tuple[CropSeedSpec, ...]
    economic_profiles: tuple[CropEconomicProfileSeedSpec, ...]
    fields: tuple[FieldSeedSpec, ...]
    soils: tuple[SoilSeedSpec, ...]
    weather: tuple[WeatherSeedSpec, ...]


def build_crop_specs() -> tuple[CropSeedSpec, ...]:
    """Return the five demo crops requested for the AgriMind seed."""

    return (
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
            organic_matter_preference=CropPreferenceLevel.HIGH,
            description="Berry crop suited to acidic, well-drained foothill parcels with strong organic matter.",
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
            organic_matter_preference=CropPreferenceLevel.MODERATE,
            description="High-yield grain crop tuned for deep irrigated alluvial soils.",
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
            organic_matter_preference=CropPreferenceLevel.MODERATE,
            description="Benchmark cereal profile for rolling grain-belt fields with moderate fertility.",
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
            organic_matter_preference=CropPreferenceLevel.LOW,
            description="Drought-tolerant oilseed profile for lighter, warmer, lower-input ground.",
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
            organic_matter_preference=CropPreferenceLevel.MODERATE,
            description="Pulse crop profile for neutral to slightly alkaline, well-drained soils.",
        ),
    )


def build_field_specs() -> tuple[FieldSeedSpec, ...]:
    """Return ten realistic fields with strong variation for ranking demos."""

    return (
        FieldSeedSpec(
            slug="foothill-blackberry-01",
            name="Berry Ridge Block 01",
            location_name="Placerville, CA",
            latitude=38.7428,
            longitude=-120.7853,
            area_hectares=6.4,
            slope_percent=11.8,
            elevation_meters=540.0,
            aspect=FieldAspect.SOUTHEAST,
            irrigation_available=True,
            water_source_type=WaterSourceType.WELL,
            infrastructure_score=82.0,
            weather_profile="foothill",
            description="Cooler foothill berry block with reliable well water and strong drainage.",
        ),
        FieldSeedSpec(
            slug="foothill-blackberry-02",
            name="Canyon Berry Terrace",
            location_name="Auburn, CA",
            latitude=38.8929,
            longitude=-121.0780,
            area_hectares=4.9,
            slope_percent=14.1,
            elevation_meters=610.0,
            aspect=FieldAspect.SOUTH,
            irrigation_available=True,
            water_source_type=WaterSourceType.RESERVOIR,
            infrastructure_score=76.0,
            weather_profile="foothill",
            description="Steeper berry terrace with strong sunlight and managed reservoir irrigation.",
        ),
        FieldSeedSpec(
            slug="valley-corn-01",
            name="River Bend Corn North",
            location_name="Woodland, CA",
            latitude=38.6785,
            longitude=-121.7733,
            area_hectares=28.6,
            slope_percent=0.8,
            elevation_meters=24.0,
            aspect=FieldAspect.FLAT,
            irrigation_available=True,
            water_source_type=WaterSourceType.CANAL,
            infrastructure_score=91.0,
            weather_profile="valley",
            description="Deep alluvial valley field built for irrigated row-crop production.",
        ),
        FieldSeedSpec(
            slug="valley-corn-02",
            name="Delta Corn South",
            location_name="Dixon, CA",
            latitude=38.4455,
            longitude=-121.8233,
            area_hectares=31.2,
            slope_percent=1.2,
            elevation_meters=18.0,
            aspect=FieldAspect.EAST,
            irrigation_available=True,
            water_source_type=WaterSourceType.RIVER,
            infrastructure_score=88.0,
            weather_profile="valley",
            description="Low-slope delta parcel with strong access and high water security.",
        ),
        FieldSeedSpec(
            slug="prairie-wheat-01",
            name="Prairie Wheat West",
            location_name="Salina, KS",
            latitude=38.8403,
            longitude=-97.6114,
            area_hectares=44.0,
            slope_percent=4.6,
            elevation_meters=412.0,
            aspect=FieldAspect.SOUTH,
            irrigation_available=False,
            water_source_type=WaterSourceType.NONE,
            infrastructure_score=68.0,
            weather_profile="plains",
            description="Dryland grain parcel with broad area, moderate slope, and dependable access roads.",
        ),
        FieldSeedSpec(
            slug="prairie-wheat-02",
            name="Prairie Wheat East",
            location_name="Manhattan, KS",
            latitude=39.1836,
            longitude=-96.5717,
            area_hectares=37.5,
            slope_percent=3.4,
            elevation_meters=389.0,
            aspect=FieldAspect.EAST,
            irrigation_available=True,
            water_source_type=WaterSourceType.WELL,
            infrastructure_score=72.0,
            weather_profile="plains",
            description="Mixed-irrigation grain block with enough fertility to compete across cereals and pulses.",
        ),
        FieldSeedSpec(
            slug="highplains-sunflower-01",
            name="High Plains Sun Block 01",
            location_name="Amarillo, TX",
            latitude=35.2219,
            longitude=-101.8313,
            area_hectares=52.4,
            slope_percent=7.3,
            elevation_meters=1012.0,
            aspect=FieldAspect.SOUTHWEST,
            irrigation_available=False,
            water_source_type=WaterSourceType.NONE,
            infrastructure_score=58.0,
            weather_profile="high_plains",
            description="Windy semi-arid block suited to drought-tolerant oilseed crops.",
        ),
        FieldSeedSpec(
            slug="highplains-chickpea-01",
            name="Mesa Pulse Block 02",
            location_name="Hereford, TX",
            latitude=34.8151,
            longitude=-102.3977,
            area_hectares=46.7,
            slope_percent=6.1,
            elevation_meters=1048.0,
            aspect=FieldAspect.SOUTH,
            irrigation_available=True,
            water_source_type=WaterSourceType.BOREHOLE,
            infrastructure_score=63.0,
            weather_profile="high_plains",
            description="Alkaline high-plains parcel with modest irrigation support and pulse-friendly drainage.",
        ),
        FieldSeedSpec(
            slug="delta-mixed-01",
            name="Alluvial Flat 09",
            location_name="Greenville, MS",
            latitude=33.4089,
            longitude=-91.0612,
            area_hectares=25.8,
            slope_percent=0.6,
            elevation_meters=35.0,
            aspect=FieldAspect.FLAT,
            irrigation_available=True,
            water_source_type=WaterSourceType.RIVER,
            infrastructure_score=79.0,
            weather_profile="delta",
            description="Heavier alluvial field with strong water access and higher humidity exposure.",
        ),
        FieldSeedSpec(
            slug="bench-mixed-01",
            name="Palouse Bench 03",
            location_name="Moscow, ID",
            latitude=46.7300,
            longitude=-117.0002,
            area_hectares=19.6,
            slope_percent=6.8,
            elevation_meters=780.0,
            aspect=FieldAspect.NORTHEAST,
            irrigation_available=False,
            water_source_type=WaterSourceType.NONE,
            infrastructure_score=65.0,
            weather_profile="intermountain",
            description="Rolling inland bench that creates a balanced mid-suitability reference parcel.",
        ),
    )


def build_crop_economic_profile_specs() -> tuple[CropEconomicProfileSeedSpec, ...]:
    """Return demo crop economics for profitability-aware ranking."""

    return (
        CropEconomicProfileSeedSpec(
            crop_slug="blackberry",
            crop_name="Blackberry",
            average_market_price_per_unit=1850.0,
            price_unit="ton",
            base_cost_per_hectare=5200.0,
            irrigation_cost_factor=0.14,
            fertilizer_cost_factor=0.12,
            labor_cost_factor=0.28,
            risk_cost_factor=0.08,
            region=None,
            description="High-value berry economics with elevated labor intensity.",
        ),
        CropEconomicProfileSeedSpec(
            crop_slug="corn",
            crop_name="Corn",
            average_market_price_per_unit=210.0,
            price_unit="ton",
            base_cost_per_hectare=360.0,
            irrigation_cost_factor=0.18,
            fertilizer_cost_factor=0.22,
            labor_cost_factor=0.11,
            risk_cost_factor=0.06,
            region=None,
            description="Irrigated row-crop economics for high-yield grain production.",
        ),
        CropEconomicProfileSeedSpec(
            crop_slug="wheat",
            crop_name="Wheat",
            average_market_price_per_unit=285.0,
            price_unit="ton",
            base_cost_per_hectare=245.0,
            irrigation_cost_factor=0.08,
            fertilizer_cost_factor=0.16,
            labor_cost_factor=0.10,
            risk_cost_factor=0.05,
            region=None,
            description="Moderate-cost cereal economics with stable market assumptions.",
        ),
        CropEconomicProfileSeedSpec(
            crop_slug="sunflower",
            crop_name="Sunflower",
            average_market_price_per_unit=460.0,
            price_unit="ton",
            base_cost_per_hectare=225.0,
            irrigation_cost_factor=0.05,
            fertilizer_cost_factor=0.14,
            labor_cost_factor=0.09,
            risk_cost_factor=0.07,
            region=None,
            description="Lower-input oilseed economics suited to drier ground.",
        ),
        CropEconomicProfileSeedSpec(
            crop_slug="chickpea",
            crop_name="Chickpea",
            average_market_price_per_unit=610.0,
            price_unit="ton",
            base_cost_per_hectare=260.0,
            irrigation_cost_factor=0.06,
            fertilizer_cost_factor=0.10,
            labor_cost_factor=0.12,
            risk_cost_factor=0.06,
            region=None,
            description="Pulse economics with favorable price support and moderate risk load.",
        ),
    )


def build_soil_specs() -> tuple[SoilSeedSpec, ...]:
    """Return one latest soil panel per seeded field."""

    return (
        SoilSeedSpec(
            field_slug="foothill-blackberry-01",
            sample_date=date(2026, 3, 14),
            ph=5.9,
            ec=0.45,
            organic_matter_percent=5.7,
            nitrogen_ppm=44.0,
            phosphorus_ppm=29.0,
            potassium_ppm=240.0,
            calcium_ppm=1480.0,
            magnesium_ppm=188.0,
            texture_class="gravelly loam",
            drainage_class="good",
            depth_cm=120.0,
            water_holding_capacity=19.0,
            description="Acidic foothill profile with strong organic matter for berry demos.",
        ),
        SoilSeedSpec(
            field_slug="foothill-blackberry-02",
            sample_date=date(2026, 3, 15),
            ph=6.2,
            ec=0.38,
            organic_matter_percent=4.9,
            nitrogen_ppm=38.0,
            phosphorus_ppm=25.0,
            potassium_ppm=228.0,
            calcium_ppm=1560.0,
            magnesium_ppm=175.0,
            texture_class="loam",
            drainage_class="excellent",
            depth_cm=110.0,
            water_holding_capacity=21.0,
            description="Well-drained terrace soil with slightly lower fertility than the primary berry block.",
        ),
        SoilSeedSpec(
            field_slug="valley-corn-01",
            sample_date=date(2026, 3, 16),
            ph=6.5,
            ec=0.72,
            organic_matter_percent=3.8,
            nitrogen_ppm=62.0,
            phosphorus_ppm=31.0,
            potassium_ppm=235.0,
            calcium_ppm=1720.0,
            magnesium_ppm=214.0,
            texture_class="silty loam",
            drainage_class="good",
            depth_cm=145.0,
            water_holding_capacity=30.0,
            description="Deep, fertile alluvial soil tuned for corn and other irrigated row crops.",
        ),
        SoilSeedSpec(
            field_slug="valley-corn-02",
            sample_date=date(2026, 3, 16),
            ph=6.7,
            ec=0.88,
            organic_matter_percent=3.4,
            nitrogen_ppm=58.0,
            phosphorus_ppm=27.0,
            potassium_ppm=248.0,
            calcium_ppm=1810.0,
            magnesium_ppm=226.0,
            texture_class="clay loam",
            drainage_class="moderate",
            depth_cm=152.0,
            water_holding_capacity=32.0,
            description="Heavier valley profile with very good fertility and high water-holding capacity.",
        ),
        SoilSeedSpec(
            field_slug="prairie-wheat-01",
            sample_date=date(2026, 3, 17),
            ph=6.6,
            ec=1.05,
            organic_matter_percent=2.9,
            nitrogen_ppm=41.0,
            phosphorus_ppm=19.0,
            potassium_ppm=188.0,
            calcium_ppm=1640.0,
            magnesium_ppm=172.0,
            texture_class="silt loam",
            drainage_class="good",
            depth_cm=138.0,
            water_holding_capacity=24.0,
            description="Typical grain-belt dryland profile balanced for wheat scoring.",
        ),
        SoilSeedSpec(
            field_slug="prairie-wheat-02",
            sample_date=date(2026, 3, 17),
            ph=6.9,
            ec=0.94,
            organic_matter_percent=3.2,
            nitrogen_ppm=46.0,
            phosphorus_ppm=22.0,
            potassium_ppm=195.0,
            calcium_ppm=1695.0,
            magnesium_ppm=181.0,
            texture_class="loam",
            drainage_class="moderate",
            depth_cm=126.0,
            water_holding_capacity=22.0,
            description="Slightly better fertility and irrigation access than the dryland wheat block.",
        ),
        SoilSeedSpec(
            field_slug="highplains-sunflower-01",
            sample_date=date(2026, 3, 18),
            ph=7.5,
            ec=2.10,
            organic_matter_percent=1.5,
            nitrogen_ppm=24.0,
            phosphorus_ppm=17.0,
            potassium_ppm=182.0,
            calcium_ppm=2080.0,
            magnesium_ppm=144.0,
            texture_class="sandy loam",
            drainage_class="good",
            depth_cm=98.0,
            water_holding_capacity=14.0,
            description="Dry alkaline high-plains soil that favors sunflower more than high-water crops.",
        ),
        SoilSeedSpec(
            field_slug="highplains-chickpea-01",
            sample_date=date(2026, 3, 18),
            ph=7.4,
            ec=1.68,
            organic_matter_percent=2.1,
            nitrogen_ppm=28.0,
            phosphorus_ppm=18.0,
            potassium_ppm=171.0,
            calcium_ppm=1945.0,
            magnesium_ppm=152.0,
            texture_class="loam",
            drainage_class="good",
            depth_cm=112.0,
            water_holding_capacity=18.0,
            description="Pulse-oriented alkaline profile with adequate rooting depth and manageable salinity.",
        ),
        SoilSeedSpec(
            field_slug="delta-mixed-01",
            sample_date=date(2026, 3, 19),
            ph=6.4,
            ec=1.22,
            organic_matter_percent=4.3,
            nitrogen_ppm=52.0,
            phosphorus_ppm=24.0,
            potassium_ppm=260.0,
            calcium_ppm=1760.0,
            magnesium_ppm=236.0,
            texture_class="silty clay loam",
            drainage_class="poor",
            depth_cm=160.0,
            water_holding_capacity=34.0,
            description="Heavier delta soil with strong fertility but moderate drainage constraints.",
        ),
        SoilSeedSpec(
            field_slug="bench-mixed-01",
            sample_date=date(2026, 3, 19),
            ph=7.1,
            ec=0.86,
            organic_matter_percent=3.1,
            nitrogen_ppm=33.0,
            phosphorus_ppm=20.0,
            potassium_ppm=210.0,
            calcium_ppm=1710.0,
            magnesium_ppm=190.0,
            texture_class="loam",
            drainage_class="good",
            depth_cm=118.0,
            water_holding_capacity=23.0,
            description="Balanced inland bench profile that stays viable across multiple candidate crops.",
        ),
    )


def build_weather_patterns() -> dict[str, WeatherPattern]:
    """Return named weather-generation profiles used by the demo fields."""

    return {
        "foothill": WeatherPattern(
            key="foothill",
            base_avg_temp=12.5,
            warming_trend_per_day=0.14,
            diurnal_range=(7.0, 11.0),
            rainfall_cycle=(2.4, 0.6, 1.8, 0.0, 3.1, 0.4, 0.9),
            humidity_range=(58.0, 82.0),
            wind_range=(2.0, 5.5),
            solar_range=(12.0, 18.0),
            et0_range=(1.2, 3.0),
        ),
        "valley": WeatherPattern(
            key="valley",
            base_avg_temp=14.0,
            warming_trend_per_day=0.18,
            diurnal_range=(8.0, 12.0),
            rainfall_cycle=(1.0, 0.0, 0.8, 0.2, 1.5, 0.0, 0.4),
            humidity_range=(48.0, 72.0),
            wind_range=(2.5, 6.5),
            solar_range=(14.0, 21.0),
            et0_range=(1.8, 3.8),
        ),
        "plains": WeatherPattern(
            key="plains",
            base_avg_temp=9.5,
            warming_trend_per_day=0.20,
            diurnal_range=(9.0, 14.0),
            rainfall_cycle=(0.4, 0.0, 1.6, 0.8, 2.1, 0.2, 0.0),
            humidity_range=(42.0, 68.0),
            wind_range=(4.0, 9.5),
            solar_range=(13.0, 20.0),
            et0_range=(1.6, 4.2),
        ),
        "high_plains": WeatherPattern(
            key="high_plains",
            base_avg_temp=8.0,
            warming_trend_per_day=0.24,
            diurnal_range=(10.0, 15.0),
            rainfall_cycle=(0.0, 0.0, 0.4, 0.0, 0.8, 0.1, 0.0),
            humidity_range=(30.0, 56.0),
            wind_range=(5.0, 11.5),
            solar_range=(15.0, 23.0),
            et0_range=(2.2, 5.0),
        ),
        "delta": WeatherPattern(
            key="delta",
            base_avg_temp=15.0,
            warming_trend_per_day=0.16,
            diurnal_range=(7.0, 10.0),
            rainfall_cycle=(1.2, 0.8, 2.4, 0.0, 3.0, 0.6, 1.1),
            humidity_range=(62.0, 88.0),
            wind_range=(2.0, 6.0),
            solar_range=(11.0, 18.0),
            et0_range=(1.5, 3.4),
        ),
        "intermountain": WeatherPattern(
            key="intermountain",
            base_avg_temp=8.8,
            warming_trend_per_day=0.17,
            diurnal_range=(8.0, 13.0),
            rainfall_cycle=(0.6, 0.0, 0.9, 0.2, 1.4, 0.0, 0.3),
            humidity_range=(45.0, 70.0),
            wind_range=(3.0, 7.5),
            solar_range=(13.0, 19.5),
            et0_range=(1.4, 3.6),
        ),
    }


def build_weather_specs(field_specs: tuple[FieldSeedSpec, ...]) -> tuple[WeatherSeedSpec, ...]:
    """Generate recent daily weather rows for all seeded fields."""

    rng = Random(SEED_RANDOM_SEED)
    patterns = build_weather_patterns()
    weather_rows: list[WeatherSeedSpec] = []
    start_date = DEMO_WEATHER_END_DATE - timedelta(days=DEMO_WEATHER_DAYS - 1)

    for field_index, field_spec in enumerate(field_specs):
        pattern = patterns[field_spec.weather_profile]
        field_rng = Random(rng.randint(1, 10_000) + field_index * 37)

        for day_offset in range(DEMO_WEATHER_DAYS):
            weather_date = start_date + timedelta(days=day_offset)
            avg_temp = round(
                pattern.base_avg_temp
                + pattern.warming_trend_per_day * day_offset
                + ((day_offset % 6) - 2.5) * 0.35
                + field_rng.uniform(-0.6, 0.6),
                1,
            )
            diurnal_span = field_rng.uniform(*pattern.diurnal_range)
            min_temp = round(avg_temp - diurnal_span / 2, 1)
            max_temp = round(avg_temp + diurnal_span / 2, 1)
            rainfall_mm = round(max(0.0, pattern.rainfall_cycle[day_offset % 7] + field_rng.uniform(-0.3, 0.5)), 1)
            humidity = round(field_rng.uniform(*pattern.humidity_range), 1)
            wind_speed = round(field_rng.uniform(*pattern.wind_range), 1)
            solar_radiation = round(field_rng.uniform(*pattern.solar_range), 1)
            et0 = round(field_rng.uniform(*pattern.et0_range), 1)

            weather_rows.append(
                WeatherSeedSpec(
                    field_slug=field_spec.slug,
                    weather_date=weather_date,
                    min_temp=min_temp,
                    max_temp=max_temp,
                    avg_temp=avg_temp,
                    rainfall_mm=rainfall_mm,
                    humidity=humidity,
                    wind_speed=wind_speed,
                    solar_radiation=solar_radiation,
                    et0=et0,
                )
            )

    return tuple(weather_rows)


def build_seed_dataset() -> SeedDataset:
    """Return the complete deterministic dataset for the demo seed."""

    crops = build_crop_specs()
    economic_profiles = build_crop_economic_profile_specs()
    fields = build_field_specs()
    soils = build_soil_specs()
    weather = build_weather_specs(fields)
    return SeedDataset(
        crops=crops,
        economic_profiles=economic_profiles,
        fields=fields,
        soils=soils,
        weather=weather,
    )
