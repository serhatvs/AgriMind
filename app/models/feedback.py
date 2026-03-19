"""Closed-loop feedback ORM models for recommendations, decisions, and outcomes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.crop_profile import CropProfile
    from app.models.field import Field


class RecommendationRun(CreatedAtMixin, Base):
    """A single recommendation cycle for a selected crop."""

    __tablename__ = "recommendation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crop_id: Mapped[int] = mapped_column(Integer, ForeignKey("crop_profiles.id"), nullable=False, index=True)

    crop: Mapped["CropProfile"] = relationship("CropProfile", back_populates="recommendation_runs")
    results: Mapped[list["RecommendationResult"]] = relationship(
        "RecommendationResult",
        back_populates="recommendation_run",
        cascade="all, delete-orphan",
        order_by=lambda: (RecommendationResult.rank.asc(), RecommendationResult.field_id.asc()),
    )
    user_decision: Mapped["UserDecision | None"] = relationship(
        "UserDecision",
        back_populates="recommendation_run",
        cascade="all, delete-orphan",
        uselist=False,
    )
    season_result: Mapped["SeasonResult | None"] = relationship(
        "SeasonResult",
        back_populates="recommendation_run",
        cascade="all, delete-orphan",
        uselist=False,
    )


class RecommendationResult(Base):
    """A ranked field recommendation emitted as part of a recommendation run."""

    __tablename__ = "recommendation_results"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_recommendation_results_score_range"),
        CheckConstraint("rank > 0", name="ck_recommendation_results_rank_positive"),
        UniqueConstraint("recommendation_run_id", "rank", name="uq_recommendation_results_run_rank"),
    )

    recommendation_run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recommendation_runs.id"),
        primary_key=True,
    )
    field_id: Mapped[int] = mapped_column(Integer, ForeignKey("fields.id"), primary_key=True, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    recommendation_run: Mapped["RecommendationRun"] = relationship(
        "RecommendationRun",
        back_populates="results",
    )
    field: Mapped["Field"] = relationship("Field", back_populates="recommendation_results")


class UserDecision(Base):
    """The field selected by the user from a recommendation run."""

    __tablename__ = "user_decisions"

    recommendation_run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recommendation_runs.id"),
        primary_key=True,
    )
    selected_field_id: Mapped[int] = mapped_column(Integer, ForeignKey("fields.id"), nullable=False, index=True)

    recommendation_run: Mapped["RecommendationRun"] = relationship(
        "RecommendationRun",
        back_populates="user_decision",
    )
    selected_field: Mapped["Field"] = relationship("Field", back_populates="user_decisions")


class SeasonResult(Base):
    """The observed outcome for the field selected in a recommendation run."""

    __tablename__ = "season_results"
    __table_args__ = (
        CheckConstraint('"yield" >= 0', name="ck_season_results_yield_non_negative"),
        CheckConstraint("actual_cost >= 0", name="ck_season_results_actual_cost_non_negative"),
    )

    recommendation_run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recommendation_runs.id"),
        primary_key=True,
    )
    field_id: Mapped[int] = mapped_column(Integer, ForeignKey("fields.id"), nullable=False, index=True)
    crop_id: Mapped[int] = mapped_column(Integer, ForeignKey("crop_profiles.id"), nullable=False, index=True)
    yield_amount: Mapped[float] = mapped_column("yield", Float, nullable=False)
    actual_cost: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    recommendation_run: Mapped["RecommendationRun"] = relationship(
        "RecommendationRun",
        back_populates="season_result",
    )
    field: Mapped["Field"] = relationship("Field", back_populates="season_results")
    crop: Mapped["CropProfile"] = relationship("CropProfile", back_populates="season_results")
