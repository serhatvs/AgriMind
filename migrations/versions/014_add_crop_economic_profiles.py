"""Add crop economic profiles for profitability-aware ranking.

Revision ID: 014_add_crop_economic_profiles
Revises: 013
Create Date: 2026-03-21 20:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "014_add_crop_economic_profiles"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crop_economic_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("crop_name", sa.String(length=255), nullable=False),
        sa.Column("average_market_price_per_unit", sa.Float(), nullable=False),
        sa.Column("price_unit", sa.String(length=64), nullable=False),
        sa.Column("base_cost_per_hectare", sa.Float(), nullable=False),
        sa.Column("irrigation_cost_factor", sa.Float(), nullable=False),
        sa.Column("fertilizer_cost_factor", sa.Float(), nullable=False),
        sa.Column("labor_cost_factor", sa.Float(), nullable=False),
        sa.Column("risk_cost_factor", sa.Float(), nullable=False),
        sa.Column("region", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "average_market_price_per_unit > 0",
            name="ck_crop_economic_profiles_average_market_price_positive",
        ),
        sa.CheckConstraint(
            "base_cost_per_hectare >= 0",
            name="ck_crop_economic_profiles_base_cost_non_negative",
        ),
        sa.CheckConstraint(
            "irrigation_cost_factor >= 0",
            name="ck_crop_economic_profiles_irrigation_cost_factor_non_negative",
        ),
        sa.CheckConstraint(
            "fertilizer_cost_factor >= 0",
            name="ck_crop_economic_profiles_fertilizer_cost_factor_non_negative",
        ),
        sa.CheckConstraint(
            "labor_cost_factor >= 0",
            name="ck_crop_economic_profiles_labor_cost_factor_non_negative",
        ),
        sa.CheckConstraint(
            "risk_cost_factor >= 0",
            name="ck_crop_economic_profiles_risk_cost_factor_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("crop_name", "region", name="uq_crop_economic_profiles_crop_region"),
    )
    op.create_index(
        "ix_crop_economic_profiles_crop_name",
        "crop_economic_profiles",
        ["crop_name"],
        unique=False,
    )
    op.create_index(
        "ix_crop_economic_profiles_region",
        "crop_economic_profiles",
        ["region"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_crop_economic_profiles_region", table_name="crop_economic_profiles")
    op.drop_index("ix_crop_economic_profiles_crop_name", table_name="crop_economic_profiles")
    op.drop_table("crop_economic_profiles")
