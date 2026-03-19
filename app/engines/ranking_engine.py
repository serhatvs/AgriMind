from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from app.engines.suitability_engine import calculate_suitability, SuitabilityResult
from app.services.field_service import get_field
from app.services.soil_service import get_latest_soil_test_for_field
from app.services.crop_service import get_crop


@dataclass
class RankedEntry:
    rank: int
    field_id: int
    crop_id: int
    score: float
    result: SuitabilityResult


@dataclass
class RankingResult:
    crop_id: int
    ranked_fields: list[RankedEntry] = field(default_factory=list)


def rank_fields(
    db: Session,
    field_ids: list[int],
    crop_id: int,
    top_n: int = 5,
) -> RankingResult:
    """Rank fields by suitability for a given crop."""
    crop = get_crop(db, crop_id)
    if not crop:
        raise ValueError(f"Crop with id {crop_id} not found")

    results: list[SuitabilityResult] = []
    for fid in field_ids:
        f = get_field(db, fid)
        if not f:
            continue
        soil_test = get_latest_soil_test_for_field(db, fid)
        result = calculate_suitability(f, crop, soil_test)
        results.append(result)

    results.sort(key=lambda r: r.total_score, reverse=True)
    top = results[:top_n]

    ranked_entries = [
        RankedEntry(
            rank=i + 1,
            field_id=r.field_id,
            crop_id=r.crop_id,
            score=r.total_score,
            result=r,
        )
        for i, r in enumerate(top)
    ]

    return RankingResult(crop_id=crop_id, ranked_fields=ranked_entries)
