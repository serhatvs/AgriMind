from datetime import date
from types import SimpleNamespace

from app.models.enums import ManagementNeedLevel
from app.schemas.management import ManagementPriority
from app.services.fertilizer_service import FertilizerService
from app.services.lifecycle_service import LifecycleStageResult


def _build_crop(**overrides):
    values = {
        "target_nitrogen_ppm": 60.0,
        "target_phosphorus_ppm": 28.0,
        "target_potassium_ppm": 220.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _build_soil(**overrides):
    values = {
        "nitrogen_ppm": 30.0,
        "phosphorus_ppm": 18.0,
        "potassium_ppm": 180.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _build_stage(**overrides):
    values = {
        "stage_name": "vegetative",
        "stage_index": 1,
        "day_offset": 7,
        "stage_start_date": date(2026, 3, 8),
        "stage_end_date": date(2026, 3, 28),
        "irrigation_need": ManagementNeedLevel.HIGH,
        "fertilizer_need": ManagementNeedLevel.HIGH,
    }
    values.update(overrides)
    return LifecycleStageResult(**values)


def test_fertilizer_service_matches_deficits_to_npk_blend_when_multiple_gaps_are_severe():
    service = FertilizerService()

    assessment = service.assess_nutrients(crop=_build_crop(), soil_test=_build_soil())

    assert [gap.nutrient for gap in assessment.nutrient_gaps] == ["nitrogen", "phosphorus", "potassium"]
    assert assessment.product == "NPK blend (15-15-15)"
    assert assessment.has_high_gap


def test_fertilizer_service_creates_stage_start_and_immediate_actions():
    service = FertilizerService()
    assessment = service.assess_nutrients(crop=_build_crop(), soil_test=_build_soil())
    stage = _build_stage()

    actions = service.build_weekly_actions(
        assessment=assessment,
        week_start=date(2026, 3, 8),
        stage_at_week_start=stage,
        stage_starts_in_week=[stage],
        include_immediate_correction=True,
    )

    assert len(actions) == 2
    assert actions[0].notes == ["Immediate corrective application due to a high nutrient deficit."]
    assert actions[1].planned_date == date(2026, 3, 8)
    assert actions[1].priority is ManagementPriority.HIGH


def test_fertilizer_service_returns_blockers_when_soil_or_targets_are_missing():
    service = FertilizerService()

    missing_soil = service.assess_nutrients(crop=_build_crop(), soil_test=None)
    missing_targets = service.assess_nutrients(
        crop=_build_crop(target_phosphorus_ppm=None),
        soil_test=_build_soil(),
    )

    assert missing_soil.blockers[0].code == "missing_soil_test"
    assert missing_targets.blockers[0].code == "missing_target_phosphorus_ppm"
    assert missing_targets.product == "NPK blend (15-15-15)"
