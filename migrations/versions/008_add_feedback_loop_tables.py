"""Add closed-loop feedback tables for recommendation learning.

Revision ID: 008
Revises: 007
Create Date: 2026-03-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("crop_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["crop_id"], ["crop_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendation_runs_crop_id", "recommendation_runs", ["crop_id"], unique=False)

    op.create_table(
        "recommendation_results",
        sa.Column("recommendation_run_id", sa.Integer(), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_recommendation_results_score_range"),
        sa.CheckConstraint("rank > 0", name="ck_recommendation_results_rank_positive"),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"]),
        sa.ForeignKeyConstraint(["recommendation_run_id"], ["recommendation_runs.id"]),
        sa.PrimaryKeyConstraint("recommendation_run_id", "field_id"),
        sa.UniqueConstraint("recommendation_run_id", "rank", name="uq_recommendation_results_run_rank"),
    )
    op.create_index("ix_recommendation_results_field_id", "recommendation_results", ["field_id"], unique=False)

    op.create_table(
        "user_decisions",
        sa.Column("recommendation_run_id", sa.Integer(), nullable=False),
        sa.Column("selected_field_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_run_id"], ["recommendation_runs.id"]),
        sa.ForeignKeyConstraint(["selected_field_id"], ["fields.id"]),
        sa.PrimaryKeyConstraint("recommendation_run_id"),
    )
    op.create_index("ix_user_decisions_selected_field_id", "user_decisions", ["selected_field_id"], unique=False)

    op.create_table(
        "season_results",
        sa.Column("recommendation_run_id", sa.Integer(), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=False),
        sa.Column("crop_id", sa.Integer(), nullable=False),
        sa.Column("yield", sa.Float(), nullable=False),
        sa.Column("actual_cost", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint('"yield" >= 0', name="ck_season_results_yield_non_negative"),
        sa.CheckConstraint("actual_cost >= 0", name="ck_season_results_actual_cost_non_negative"),
        sa.ForeignKeyConstraint(["crop_id"], ["crop_profiles.id"]),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"]),
        sa.ForeignKeyConstraint(["recommendation_run_id"], ["recommendation_runs.id"]),
        sa.PrimaryKeyConstraint("recommendation_run_id"),
    )
    op.create_index("ix_season_results_crop_id", "season_results", ["crop_id"], unique=False)
    op.create_index("ix_season_results_field_id", "season_results", ["field_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_season_results_field_id", table_name="season_results")
    op.drop_index("ix_season_results_crop_id", table_name="season_results")
    op.drop_table("season_results")
    op.drop_index("ix_user_decisions_selected_field_id", table_name="user_decisions")
    op.drop_table("user_decisions")
    op.drop_index("ix_recommendation_results_field_id", table_name="recommendation_results")
    op.drop_table("recommendation_results")
    op.drop_index("ix_recommendation_runs_crop_id", table_name="recommendation_runs")
    op.drop_table("recommendation_runs")
