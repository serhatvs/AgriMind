"""Rule-based fertilizer planning for weekly field management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from app.models.enums import ManagementNeedLevel
from app.schemas.management import (
    FertilizerActionRead,
    ManagementBlocker,
    ManagementPriority,
    NutrientGapRead,
)

if TYPE_CHECKING:
    from app.models.crop_profile import CropProfile
    from app.models.soil_test import SoilTest
    from app.services.lifecycle_service import LifecycleStageResult


@dataclass(slots=True)
class FertilityAssessment:
    """Intermediate fertilizer state reused across weekly planning."""

    nutrient_gaps: list[NutrientGapRead] = field(default_factory=list)
    blockers: list[ManagementBlocker] = field(default_factory=list)
    product: str | None = None
    dominant_nutrient: str | None = None

    @property
    def has_gaps(self) -> bool:
        return bool(self.nutrient_gaps)

    @property
    def has_high_gap(self) -> bool:
        return any(gap.severity is ManagementPriority.HIGH for gap in self.nutrient_gaps)

    @property
    def max_priority(self) -> ManagementPriority:
        if any(gap.severity is ManagementPriority.HIGH for gap in self.nutrient_gaps):
            return ManagementPriority.HIGH
        if any(gap.severity is ManagementPriority.MEDIUM for gap in self.nutrient_gaps):
            return ManagementPriority.MEDIUM
        return ManagementPriority.LOW


class FertilizerService:
    """Build fertilizer actions from crop nutrient targets and soil tests."""

    _NUTRIENT_FIELDS = {
        "nitrogen": ("target_nitrogen_ppm", "nitrogen_ppm"),
        "phosphorus": ("target_phosphorus_ppm", "phosphorus_ppm"),
        "potassium": ("target_potassium_ppm", "potassium_ppm"),
    }
    _PRODUCTS = {
        frozenset({"nitrogen"}): "Urea (46-0-0)",
        frozenset({"phosphorus"}): "MAP (11-52-0)",
        frozenset({"potassium"}): "MOP (0-0-60)",
        frozenset({"nitrogen", "phosphorus"}): "DAP (18-46-0)",
        frozenset({"nitrogen", "potassium"}): "Urea + MOP",
        frozenset({"phosphorus", "potassium"}): "MAP + MOP",
    }

    def assess_nutrients(
        self,
        *,
        crop: "CropProfile",
        soil_test: "SoilTest | None",
    ) -> FertilityAssessment:
        """Evaluate nutrient deficits and return reusable fertilizer state."""

        blockers: list[ManagementBlocker] = []
        nutrient_gaps: list[NutrientGapRead] = []

        if soil_test is None:
            blockers.append(
                ManagementBlocker(
                    code="missing_soil_test",
                    message="Latest soil test is required for fertilizer planning.",
                    priority=ManagementPriority.HIGH,
                )
            )
            return FertilityAssessment(blockers=blockers)

        for nutrient_name, (target_attr, soil_attr) in self._NUTRIENT_FIELDS.items():
            target_ppm = getattr(crop, target_attr)
            if target_ppm is None or target_ppm <= 0:
                blockers.append(
                    ManagementBlocker(
                        code=f"missing_{target_attr}",
                        message=f"Crop nutrient target '{target_attr}' is not configured.",
                        priority=ManagementPriority.MEDIUM,
                    )
                )
                continue

            current_ppm = float(getattr(soil_test, soil_attr))
            deficit_ppm = round(max(float(target_ppm) - current_ppm, 0.0), 2)
            if deficit_ppm <= 0:
                continue

            nutrient_gaps.append(
                NutrientGapRead(
                    nutrient=nutrient_name,
                    current_ppm=round(current_ppm, 2),
                    target_ppm=round(float(target_ppm), 2),
                    deficit_ppm=deficit_ppm,
                    severity=self._severity_for_ratio(deficit_ppm / float(target_ppm)),
                )
            )

        product = self._select_product(nutrient_gaps)
        dominant_nutrient = None
        if nutrient_gaps:
            dominant_nutrient = max(
                nutrient_gaps,
                key=lambda gap: (self._priority_rank(gap.severity), gap.deficit_ppm),
            ).nutrient

        return FertilityAssessment(
            nutrient_gaps=nutrient_gaps,
            blockers=blockers,
            product=product,
            dominant_nutrient=dominant_nutrient,
        )

    def build_weekly_actions(
        self,
        *,
        assessment: FertilityAssessment,
        week_start: date,
        stage_at_week_start: "LifecycleStageResult",
        stage_starts_in_week: list["LifecycleStageResult"],
        include_immediate_correction: bool,
    ) -> list[FertilizerActionRead]:
        """Return fertilizer actions for the supplied planning week."""

        if not assessment.has_gaps or assessment.product is None:
            return []

        actions: list[FertilizerActionRead] = []
        if include_immediate_correction and assessment.has_high_gap:
            actions.append(
                FertilizerActionRead(
                    planned_date=week_start,
                    stage_name=stage_at_week_start.stage_name,
                    product=assessment.product,
                    priority=ManagementPriority.HIGH,
                    nutrient_gaps=assessment.nutrient_gaps,
                    notes=["Immediate corrective application due to a high nutrient deficit."],
                )
            )

        for stage in stage_starts_in_week:
            if stage.fertilizer_need not in {ManagementNeedLevel.MEDIUM, ManagementNeedLevel.HIGH}:
                continue
            notes = [f"Triggered by the start of the {stage.stage_name} stage."]
            if assessment.product == "NPK blend (15-15-15)" and assessment.dominant_nutrient is not None:
                notes.append(f"Dominant nutrient deficit: {assessment.dominant_nutrient}.")
            actions.append(
                FertilizerActionRead(
                    planned_date=stage.stage_start_date,
                    stage_name=stage.stage_name,
                    product=assessment.product,
                    priority=self._merge_priorities(
                        assessment.max_priority,
                        self._priority_from_need(stage.fertilizer_need),
                    ),
                    nutrient_gaps=assessment.nutrient_gaps,
                    notes=notes,
                )
            )
        return actions

    @staticmethod
    def _severity_for_ratio(deficit_ratio: float) -> ManagementPriority:
        if deficit_ratio <= 0.15:
            return ManagementPriority.LOW
        if deficit_ratio <= 0.35:
            return ManagementPriority.MEDIUM
        return ManagementPriority.HIGH

    def _select_product(self, nutrient_gaps: list[NutrientGapRead]) -> str | None:
        if not nutrient_gaps:
            return None

        nutrients = {gap.nutrient for gap in nutrient_gaps}
        medium_high_count = sum(
            1 for gap in nutrient_gaps if gap.severity in {ManagementPriority.MEDIUM, ManagementPriority.HIGH}
        )
        if len(nutrients) >= 3 or medium_high_count >= 2:
            return "NPK blend (15-15-15)"
        return self._PRODUCTS.get(frozenset(nutrients), "NPK blend (15-15-15)")

    @staticmethod
    def _priority_rank(priority: ManagementPriority) -> int:
        return {
            ManagementPriority.LOW: 1,
            ManagementPriority.MEDIUM: 2,
            ManagementPriority.HIGH: 3,
        }[priority]

    @staticmethod
    def _priority_from_need(need_level: ManagementNeedLevel) -> ManagementPriority:
        return {
            ManagementNeedLevel.LOW: ManagementPriority.LOW,
            ManagementNeedLevel.MEDIUM: ManagementPriority.MEDIUM,
            ManagementNeedLevel.HIGH: ManagementPriority.HIGH,
        }[need_level]

    def _merge_priorities(
        self,
        left: ManagementPriority,
        right: ManagementPriority,
    ) -> ManagementPriority:
        return left if self._priority_rank(left) >= self._priority_rank(right) else right
