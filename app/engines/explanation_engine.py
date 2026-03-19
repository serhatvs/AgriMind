from app.engines.suitability_engine import SuitabilityResult
from app.models.field import Field
from app.models.crop_profile import CropProfile


WEIGHT_LABELS = {
    "ph_score": ("pH", 25),
    "nitrogen_score": ("Nitrogen", 15),
    "phosphorus_score": ("Phosphorus", 10),
    "potassium_score": ("Potassium", 10),
    "drainage_score": ("Drainage", 15),
    "irrigation_score": ("Irrigation", 10),
    "slope_score": ("Slope", 10),
    "soil_texture_score": ("Soil texture", 5),
}


def _suitability_label(score: float) -> str:
    if score >= 80:
        return "highly suitable"
    elif score >= 60:
        return "moderately suitable"
    elif score >= 40:
        return "marginally suitable"
    return "not suitable"


def generate_explanation(
    result: SuitabilityResult,
    field_obj: Field,
    crop: CropProfile,
) -> str:
    """Generate a human-readable explanation for a suitability result."""
    label = _suitability_label(result.total_score)
    lines = [
        f"Field '{field_obj.name}' is {label} for {crop.name} (score: {result.total_score}/100)."
    ]

    strengths = []
    weaknesses = []

    for key, (label_name, max_pts) in WEIGHT_LABELS.items():
        earned = result.component_scores.get(key, 0.0)
        if max_pts == 0:
            continue
        ratio = earned / max_pts
        entry = f"{label_name} ({earned}/{max_pts} pts)"
        if ratio >= 0.9:
            strengths.append(entry)
        elif ratio < 0.6:
            weaknesses.append(entry)

    if strengths:
        lines.append("Strengths: " + ", ".join(strengths) + ".")
    if weaknesses:
        lines.append("Weaknesses: " + ", ".join(weaknesses) + ".")
    if not strengths and not weaknesses:
        lines.append("All factors are adequate.")

    return " ".join(lines)
