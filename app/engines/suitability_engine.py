import json
import os
from dataclasses import dataclass, field
from app.models.field import Field
from app.models.crop_profile import CropProfile
from app.models.soil_test import SoilTest

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "../../config/scoring_weights.json")

_weights: dict | None = None


def load_weights() -> dict:
    global _weights
    if _weights is None:
        with open(WEIGHTS_PATH) as f:
            _weights = json.load(f)
    return _weights


DRAINAGE_LEVELS = {"poor": 1, "moderate": 2, "good": 3, "excellent": 4}


@dataclass
class SuitabilityResult:
    field_id: int
    crop_id: int
    total_score: float
    component_scores: dict = field(default_factory=dict)
    blocking_constraints: list[str] = field(default_factory=list)


def score_ph(ph_level: float, crop: CropProfile, weight: float) -> float:
    if crop.optimal_ph_min <= ph_level <= crop.optimal_ph_max:
        return weight
    elif crop.min_ph <= ph_level <= crop.max_ph:
        return weight * 0.6
    return 0.0


def score_nutrient(actual: float, minimum: float, weight: float) -> float:
    if minimum <= 0:
        return weight
    if actual >= minimum:
        return weight
    return max(0.0, weight * (actual / minimum))


def score_drainage(field_drainage: str, crop_drainage: str, weight: float) -> float:
    field_level = DRAINAGE_LEVELS.get(field_drainage, 2)
    crop_level = DRAINAGE_LEVELS.get(crop_drainage, 2)
    if field_level >= crop_level:
        return weight
    return max(0.0, weight * (field_level / crop_level))


def score_irrigation(irrigation_available: bool, water_req: str, weight: float) -> float:
    if irrigation_available or water_req == "low":
        return weight
    if water_req == "medium":
        return weight * 0.5
    return 0.0


def score_slope(field_slope: float, max_slope: float, weight: float) -> float:
    if field_slope <= max_slope:
        return weight
    if max_slope > 0 and field_slope < max_slope * 2:
        return max(0.0, weight * (1 - (field_slope - max_slope) / max_slope))
    return 0.0


def score_soil_texture(field_texture: str, preferred_textures: str, weight: float) -> float:
    textures = [t.strip().lower() for t in preferred_textures.split(",")]
    if field_texture.lower() in textures:
        return weight
    return 0.0


def check_blocking_constraints(field_obj: Field, crop: CropProfile) -> list[str]:
    constraints: list[str] = []

    if crop.min_area_hectares > 0 and field_obj.area_hectares < crop.min_area_hectares:
        constraints.append(
            f"Field area {field_obj.area_hectares:g} ha is below the minimum {crop.min_area_hectares:g} ha."
        )

    return constraints


def calculate_suitability(
    field_obj: Field,
    crop: CropProfile,
    soil_test: SoilTest | None,
) -> SuitabilityResult:
    """Calculate crop suitability score for a given field and crop."""
    weights = load_weights()

    component_scores = {}

    if soil_test is not None:
        ph_pts = score_ph(soil_test.ph_level, crop, weights["ph_score"])
        n_pts = score_nutrient(soil_test.nitrogen_ppm, crop.min_nitrogen_ppm, weights["nitrogen_score"])
        p_pts = score_nutrient(soil_test.phosphorus_ppm, crop.min_phosphorus_ppm, weights["phosphorus_score"])
        k_pts = score_nutrient(soil_test.potassium_ppm, crop.min_potassium_ppm, weights["potassium_score"])
        texture_pts = score_soil_texture(soil_test.soil_texture, crop.preferred_soil_textures, weights["soil_texture_score"])
    else:
        ph_pts = 0.0
        n_pts = 0.0
        p_pts = 0.0
        k_pts = 0.0
        texture_pts = 0.0

    drainage_pts = score_drainage(field_obj.drainage_quality, crop.drainage_requirement, weights["drainage_score"])
    irrigation_pts = score_irrigation(field_obj.irrigation_available, crop.water_requirement, weights["irrigation_score"])
    slope_pts = score_slope(field_obj.slope_percent, crop.max_slope_percent, weights["slope_score"])

    component_scores = {
        "ph_score": round(ph_pts, 2),
        "nitrogen_score": round(n_pts, 2),
        "phosphorus_score": round(p_pts, 2),
        "potassium_score": round(k_pts, 2),
        "drainage_score": round(drainage_pts, 2),
        "irrigation_score": round(irrigation_pts, 2),
        "slope_score": round(slope_pts, 2),
        "soil_texture_score": round(texture_pts, 2),
    }

    total = sum(component_scores.values())

    if soil_test is None:
        base_non_soil = drainage_pts + irrigation_pts + slope_pts
        total = max(base_non_soil, 5.0)

    blocking_constraints = check_blocking_constraints(field_obj, crop)
    if blocking_constraints:
        total = 0.0

    return SuitabilityResult(
        field_id=field_obj.id,
        crop_id=crop.id,
        total_score=round(min(total, 100.0), 2),
        component_scores=component_scores,
        blocking_constraints=blocking_constraints,
    )
