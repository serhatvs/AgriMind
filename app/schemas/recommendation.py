from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class RecommendationRead(BaseModel):
    id: int
    field_id: int
    crop_id: int
    suitability_score: float
    rank: int
    explanation: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RankFieldsRequest(BaseModel):
    field_ids: list[int]
    crop_id: int
    top_n: int = 5


class RankedFieldResult(BaseModel):
    rank: int
    field_id: int
    crop_id: int
    score: float
    explanation: str
