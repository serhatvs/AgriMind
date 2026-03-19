"""Deterministic mock training data for the MVP yield model."""

from __future__ import annotations

import random

from app.ml.yield_pipeline import YieldFeatureBundle, YieldTrainingSample
from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    WaterRequirementLevel,
    WaterSourceType,
)

RANDOM_SEED = 20260319

BASE_YIELDS = {
    "blackberry": 13.5,
    "corn": 8.9,
    "wheat": 4.8,
    "sunflower": 3.2,
    "chickpea": 2.6,
}

NUTRIENT_TARGETS = {
    "blackberry": (55.0, 35.0, 240.0),
    "corn": (75.0, 32.0, 260.0),
    "wheat": (48.0, 26.0, 190.0),
    "sunflower": (42.0, 24.0, 220.0),
    "chickpea": (28.0, 22.0, 170.0),
}

DRAINAGE_ORDER = {"poor": 0, "moderate": 1, "good": 2, "excellent": 3}


def build_mock_crop_profiles() -> list[CropProfile]:
    """Return canonical crops used for synthetic training when real data is absent."""

    return [
        CropProfile(
            crop_name="Blackberry",
            scientific_name="Rubus fruticosus",
            ideal_ph_min=5.5,
            ideal_ph_max=6.5,
            tolerable_ph_min=5.0,
            tolerable_ph_max=7.0,
            water_requirement_level=WaterRequirementLevel.HIGH,
            drainage_requirement=CropDrainageRequirement.GOOD,
            frost_sensitivity=CropSensitivityLevel.HIGH,
            heat_sensitivity=CropSensitivityLevel.MEDIUM,
            salinity_tolerance=CropPreferenceLevel.LOW,
            rooting_depth_cm=140.0,
            slope_tolerance=12.0,
            optimal_temp_min_c=16.0,
            optimal_temp_max_c=24.0,
            rainfall_requirement_mm=700.0,
            frost_tolerance_days=8,
            heat_tolerance_days=12,
            organic_matter_preference=CropPreferenceLevel.HIGH,
            notes="Synthetic training crop profile",
        ),
        CropProfile(
            crop_name="Corn",
            scientific_name="Zea mays",
            ideal_ph_min=6.0,
            ideal_ph_max=6.8,
            tolerable_ph_min=5.5,
            tolerable_ph_max=7.5,
            water_requirement_level=WaterRequirementLevel.HIGH,
            drainage_requirement=CropDrainageRequirement.MODERATE,
            frost_sensitivity=CropSensitivityLevel.HIGH,
            heat_sensitivity=CropSensitivityLevel.MEDIUM,
            salinity_tolerance=CropPreferenceLevel.MODERATE,
            rooting_depth_cm=150.0,
            slope_tolerance=8.0,
            optimal_temp_min_c=18.0,
            optimal_temp_max_c=30.0,
            rainfall_requirement_mm=550.0,
            frost_tolerance_days=4,
            heat_tolerance_days=18,
            organic_matter_preference=CropPreferenceLevel.MODERATE,
            notes="Synthetic training crop profile",
        ),
        CropProfile(
            crop_name="Wheat",
            scientific_name="Triticum aestivum",
            ideal_ph_min=6.0,
            ideal_ph_max=7.0,
            tolerable_ph_min=5.5,
            tolerable_ph_max=7.8,
            water_requirement_level=WaterRequirementLevel.MEDIUM,
            drainage_requirement=CropDrainageRequirement.GOOD,
            frost_sensitivity=CropSensitivityLevel.MEDIUM,
            heat_sensitivity=CropSensitivityLevel.MEDIUM,
            salinity_tolerance=CropPreferenceLevel.LOW,
            rooting_depth_cm=120.0,
            slope_tolerance=10.0,
            optimal_temp_min_c=12.0,
            optimal_temp_max_c=22.0,
            rainfall_requirement_mm=450.0,
            frost_tolerance_days=20,
            heat_tolerance_days=12,
            organic_matter_preference=CropPreferenceLevel.MODERATE,
            notes="Synthetic training crop profile",
        ),
        CropProfile(
            crop_name="Sunflower",
            scientific_name="Helianthus annuus",
            ideal_ph_min=6.0,
            ideal_ph_max=7.5,
            tolerable_ph_min=5.5,
            tolerable_ph_max=8.0,
            water_requirement_level=WaterRequirementLevel.LOW,
            drainage_requirement=CropDrainageRequirement.MODERATE,
            frost_sensitivity=CropSensitivityLevel.HIGH,
            heat_sensitivity=CropSensitivityLevel.LOW,
            salinity_tolerance=CropPreferenceLevel.HIGH,
            rooting_depth_cm=160.0,
            slope_tolerance=12.0,
            optimal_temp_min_c=18.0,
            optimal_temp_max_c=32.0,
            rainfall_requirement_mm=360.0,
            frost_tolerance_days=2,
            heat_tolerance_days=24,
            organic_matter_preference=CropPreferenceLevel.LOW,
            notes="Synthetic training crop profile",
        ),
        CropProfile(
            crop_name="Chickpea",
            scientific_name="Cicer arietinum",
            ideal_ph_min=6.0,
            ideal_ph_max=7.5,
            tolerable_ph_min=5.8,
            tolerable_ph_max=8.0,
            water_requirement_level=WaterRequirementLevel.LOW,
            drainage_requirement=CropDrainageRequirement.GOOD,
            frost_sensitivity=CropSensitivityLevel.MEDIUM,
            heat_sensitivity=CropSensitivityLevel.MEDIUM,
            salinity_tolerance=CropPreferenceLevel.MODERATE,
            rooting_depth_cm=110.0,
            slope_tolerance=10.0,
            optimal_temp_min_c=14.0,
            optimal_temp_max_c=28.0,
            rainfall_requirement_mm=320.0,
            frost_tolerance_days=10,
            heat_tolerance_days=14,
            organic_matter_preference=CropPreferenceLevel.LOW,
            notes="Synthetic training crop profile",
        ),
    ]


def generate_mock_training_samples(
    crop_profiles: list[CropProfile] | None = None,
    *,
    sample_count: int = 600,
    random_seed: int = RANDOM_SEED,
) -> list[YieldTrainingSample]:
    """Generate deterministic synthetic training rows for MVP model bootstrapping."""

    crops = crop_profiles or build_mock_crop_profiles()
    rng = random.Random(random_seed)
    samples: list[YieldTrainingSample] = []

    for index in range(sample_count):
        crop = crops[index % len(crops)]
        bundle = _build_mock_feature_bundle(crop, rng)
        yield_per_hectare = _simulate_yield(bundle, crop, rng)
        samples.append(
            YieldTrainingSample(
                features=bundle,
                yield_per_hectare=round(yield_per_hectare, 2),
            )
        )

    return samples


def _build_mock_feature_bundle(crop: CropProfile, rng: random.Random) -> YieldFeatureBundle:
    crop_name = crop.crop_name.lower()
    irrigated = _sample_irrigation(crop, rng)
    rainfall_target = crop.rainfall_requirement_mm or 500.0
    temp_min = crop.optimal_temp_min_c if crop.optimal_temp_min_c is not None else 16.0
    temp_max = crop.optimal_temp_max_c if crop.optimal_temp_max_c is not None else 26.0
    temp_mid = (temp_min + temp_max) / 2
    organic_pref = crop.organic_matter_preference.value if crop.organic_matter_preference is not None else "moderate"

    organic_matter = _sample_organic_matter(organic_pref, rng)
    drainage_quality = _sample_drainage(crop.drainage_requirement.value, rng)
    soil_drainage = _sample_drainage(crop.drainage_requirement.value, rng)
    texture_class = _sample_texture(crop_name, rng)
    ph = _sample_ph(crop, rng)
    ec = _sample_ec(crop_name, rng)
    nitrogen_ppm, phosphorus_ppm, potassium_ppm = _sample_nutrients(crop_name, rng)

    climate_summary_available = rng.random() > 0.05
    soil_test_available = rng.random() > 0.04

    return YieldFeatureBundle(
        crop_name=crop.crop_name,
        soil_ph=ph if soil_test_available else None,
        soil_ec=ec if soil_test_available else None,
        organic_matter_percent=organic_matter if soil_test_available else None,
        nitrogen_ppm=nitrogen_ppm if soil_test_available else None,
        phosphorus_ppm=phosphorus_ppm if soil_test_available else None,
        potassium_ppm=potassium_ppm if soil_test_available else None,
        soil_depth_cm=(crop.rooting_depth_cm or 120.0) * rng.uniform(0.75, 1.25) if soil_test_available else None,
        water_holding_capacity=rng.uniform(14.0, 28.0) if soil_test_available else None,
        texture_class=texture_class if soil_test_available else None,
        soil_drainage_class=soil_drainage if soil_test_available else None,
        slope_percent=max(0.0, rng.uniform(0.3, max((crop.slope_tolerance or 10.0) * 1.8, 4.0))),
        irrigation_available=irrigated,
        area_hectares=rng.uniform(3.0, 40.0),
        elevation_meters=rng.uniform(80.0, 850.0),
        field_drainage_quality=drainage_quality,
        infrastructure_score=int(rng.uniform(45.0, 95.0 if irrigated else 82.0)),
        water_source_type=_sample_water_source(irrigated, rng),
        aspect=rng.choice(["flat", "north", "south", "east", "west", "southeast", "southwest"]),
        crop_water_requirement=crop.water_requirement_level.value,
        crop_drainage_requirement=crop.drainage_requirement.value,
        crop_salinity_tolerance=crop.salinity_tolerance.value if crop.salinity_tolerance is not None else None,
        crop_rooting_depth_cm=crop.rooting_depth_cm,
        crop_slope_tolerance=crop.slope_tolerance,
        crop_optimal_temp_min_c=crop.optimal_temp_min_c,
        crop_optimal_temp_max_c=crop.optimal_temp_max_c,
        crop_rainfall_requirement_mm=crop.rainfall_requirement_mm,
        crop_frost_tolerance_days=crop.frost_tolerance_days,
        crop_heat_tolerance_days=crop.heat_tolerance_days,
        crop_organic_matter_preference=organic_pref,
        climate_avg_temp=(temp_mid + rng.uniform(-5.5, 5.5)) if climate_summary_available else None,
        climate_total_rainfall=(rainfall_target * rng.uniform(0.45, 1.45)) if climate_summary_available else None,
        climate_frost_days=int(max(0, rng.gauss((crop.frost_tolerance_days or 8) * 0.9, 4))) if climate_summary_available else None,
        climate_heat_days=int(max(0, rng.gauss((crop.heat_tolerance_days or 10) * 0.9, 4))) if climate_summary_available else None,
        has_soil_test=soil_test_available,
        has_climate_summary=climate_summary_available,
    )


def _simulate_yield(bundle: YieldFeatureBundle, crop: CropProfile, rng: random.Random) -> float:
    crop_name = crop.crop_name.lower()
    base_yield = BASE_YIELDS.get(crop_name, 5.0)
    nutrient_targets = NUTRIENT_TARGETS.get(crop_name, (45.0, 25.0, 190.0))

    yield_factor = 1.0
    yield_factor *= _ph_factor(bundle.soil_ph, crop)
    yield_factor *= _organic_matter_factor(bundle.organic_matter_percent, bundle.crop_organic_matter_preference)
    yield_factor *= _nutrient_factor(bundle.nitrogen_ppm, bundle.phosphorus_ppm, bundle.potassium_ppm, nutrient_targets)
    yield_factor *= _drainage_factor(bundle.field_drainage_quality, bundle.crop_drainage_requirement)
    yield_factor *= _slope_factor(bundle.slope_percent, bundle.crop_slope_tolerance)
    yield_factor *= _irrigation_factor(bundle.irrigation_available, bundle.crop_water_requirement)
    yield_factor *= _temperature_factor(bundle.climate_avg_temp, crop)
    yield_factor *= _rainfall_factor(bundle.climate_total_rainfall, crop.rainfall_requirement_mm)
    yield_factor *= _frost_factor(bundle.climate_frost_days, crop.frost_tolerance_days)
    yield_factor *= _heat_factor(bundle.climate_heat_days, crop.heat_tolerance_days)
    yield_factor *= _depth_factor(bundle.soil_depth_cm, crop.rooting_depth_cm)
    yield_factor *= 0.9 + (bundle.infrastructure_score / 1000.0)

    if not bundle.has_soil_test:
        yield_factor *= 0.9
    if not bundle.has_climate_summary:
        yield_factor *= 0.92

    noise = rng.uniform(-0.12, 0.12)
    predicted = base_yield * max(0.35, min(yield_factor + noise, 1.45))
    return max(predicted, base_yield * 0.3)


def _sample_irrigation(crop: CropProfile, rng: random.Random) -> bool:
    if crop.water_requirement_level is WaterRequirementLevel.HIGH:
        return rng.random() > 0.18
    if crop.water_requirement_level is WaterRequirementLevel.MEDIUM:
        return rng.random() > 0.45
    return rng.random() > 0.72


def _sample_texture(crop_name: str, rng: random.Random) -> str:
    if crop_name == "blackberry":
        return rng.choice(["loamy", "silt loam", "clay loam"])
    if crop_name == "sunflower":
        return rng.choice(["sandy loam", "loamy", "loam"])
    if crop_name == "chickpea":
        return rng.choice(["sandy loam", "loamy", "silt loam"])
    return rng.choice(["loamy", "silt loam", "clay loam", "sandy loam"])


def _sample_drainage(required: str, rng: random.Random) -> str:
    required_level = DRAINAGE_ORDER[required]
    choices = [name for name, level in DRAINAGE_ORDER.items() if abs(level - required_level) <= 1]
    if rng.random() < 0.2:
        choices = list(DRAINAGE_ORDER)
    return rng.choice(choices)


def _sample_organic_matter(preference: str, rng: random.Random) -> float:
    if preference == "high":
        return rng.uniform(3.5, 6.8)
    if preference == "low":
        return rng.uniform(1.0, 3.8)
    return rng.uniform(2.0, 5.0)


def _sample_ph(crop: CropProfile, rng: random.Random) -> float:
    if rng.random() < 0.7:
        return round(rng.uniform(crop.ideal_ph_min, crop.ideal_ph_max), 2)
    return round(rng.uniform(crop.tolerable_ph_min - 0.4, crop.tolerable_ph_max + 0.4), 2)


def _sample_ec(crop_name: str, rng: random.Random) -> float:
    if crop_name == "sunflower":
        return round(rng.uniform(0.8, 3.8), 2)
    if crop_name == "blackberry":
        return round(rng.uniform(0.3, 1.6), 2)
    return round(rng.uniform(0.4, 2.6), 2)


def _sample_nutrients(crop_name: str, rng: random.Random) -> tuple[float, float, float]:
    n_target, p_target, k_target = NUTRIENT_TARGETS[crop_name]
    return (
        round(rng.uniform(n_target * 0.55, n_target * 1.35), 2),
        round(rng.uniform(p_target * 0.55, p_target * 1.35), 2),
        round(rng.uniform(k_target * 0.55, k_target * 1.35), 2),
    )


def _sample_water_source(irrigated: bool, rng: random.Random) -> str | None:
    if not irrigated:
        return None
    return rng.choice(
        [
            WaterSourceType.WELL.value,
            WaterSourceType.CANAL.value,
            WaterSourceType.RESERVOIR.value,
            WaterSourceType.RIVER.value,
            WaterSourceType.MIXED.value,
        ]
    )


def _ph_factor(ph: float | None, crop: CropProfile) -> float:
    if ph is None:
        return 0.92
    if crop.ideal_ph_min <= ph <= crop.ideal_ph_max:
        return 1.05
    if crop.tolerable_ph_min <= ph <= crop.tolerable_ph_max:
        return 0.92
    return 0.72


def _organic_matter_factor(organic_matter: float | None, preference: str | None) -> float:
    if organic_matter is None:
        return 0.94
    if preference == "high":
        return 1.04 if organic_matter >= 4.0 else 0.84
    if preference == "low":
        return 1.03 if organic_matter <= 3.5 else 0.9
    return 1.03 if 2.0 <= organic_matter <= 5.5 else 0.88


def _nutrient_factor(
    nitrogen: float | None,
    phosphorus: float | None,
    potassium: float | None,
    targets: tuple[float, float, float],
) -> float:
    values = [nitrogen, phosphorus, potassium]
    if any(value is None for value in values):
        return 0.93

    ratios = [min(value / target, 1.2) for value, target in zip(values, targets, strict=True)]
    return max(0.7, min(sum(ratios) / len(ratios), 1.08))


def _drainage_factor(field_drainage: str, crop_requirement: str) -> float:
    field_level = DRAINAGE_ORDER.get(field_drainage, 1)
    crop_level = DRAINAGE_ORDER.get(crop_requirement, 1)
    if field_level >= crop_level:
        return 1.03
    gap = crop_level - field_level
    return max(0.7, 0.95 - (gap * 0.1))


def _slope_factor(slope_percent: float, slope_tolerance: float | None) -> float:
    if slope_tolerance is None or slope_percent <= slope_tolerance:
        return 1.02
    if slope_percent <= slope_tolerance * 1.5:
        return 0.9
    return 0.74


def _irrigation_factor(irrigated: bool, water_requirement: str) -> float:
    if water_requirement == WaterRequirementLevel.HIGH.value:
        return 1.06 if irrigated else 0.72
    if water_requirement == WaterRequirementLevel.MEDIUM.value:
        return 1.03 if irrigated else 0.9
    return 1.01 if irrigated else 1.0


def _temperature_factor(avg_temp: float | None, crop: CropProfile) -> float:
    if avg_temp is None or crop.optimal_temp_min_c is None or crop.optimal_temp_max_c is None:
        return 0.95
    if crop.optimal_temp_min_c <= avg_temp <= crop.optimal_temp_max_c:
        return 1.05
    if crop.optimal_temp_min_c - 3.0 <= avg_temp <= crop.optimal_temp_max_c + 3.0:
        return 0.92
    return 0.76


def _rainfall_factor(total_rainfall: float | None, rainfall_requirement: float | None) -> float:
    if total_rainfall is None or rainfall_requirement is None or rainfall_requirement == 0:
        return 0.95
    ratio = total_rainfall / rainfall_requirement
    if 0.85 <= ratio <= 1.15:
        return 1.05
    if 0.6 <= ratio <= 1.4:
        return 0.9
    return 0.72


def _frost_factor(frost_days: int | None, frost_tolerance: int | None) -> float:
    if frost_days is None or frost_tolerance is None:
        return 0.96
    if frost_days <= frost_tolerance:
        return 1.03
    if frost_days <= frost_tolerance * 1.5:
        return 0.88
    return 0.7


def _heat_factor(heat_days: int | None, heat_tolerance: int | None) -> float:
    if heat_days is None or heat_tolerance is None:
        return 0.96
    if heat_days <= heat_tolerance:
        return 1.03
    if heat_days <= heat_tolerance * 1.5:
        return 0.88
    return 0.72


def _depth_factor(depth_cm: float | None, rooting_depth_cm: float | None) -> float:
    if depth_cm is None or rooting_depth_cm is None:
        return 0.95
    if depth_cm >= rooting_depth_cm:
        return 1.03
    if depth_cm >= rooting_depth_cm * 0.7:
        return 0.9
    return 0.76
