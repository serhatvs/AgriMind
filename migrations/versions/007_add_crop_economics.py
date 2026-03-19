"""Add crop-scoped economics tables for pricing and input costs.

Revision ID: 007
Revises: 006
Create Date: 2026-03-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crop_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("crop_id", sa.Integer(), nullable=False),
        sa.Column("price_per_ton", sa.Float(), nullable=False),
        sa.CheckConstraint("price_per_ton > 0", name="ck_crop_prices_price_per_ton_positive"),
        sa.ForeignKeyConstraint(["crop_id"], ["crop_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("crop_id", name="uq_crop_prices_crop_id"),
    )
    op.create_index("ix_crop_prices_crop_id", "crop_prices", ["crop_id"], unique=False)

    op.create_table(
        "input_costs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("crop_id", sa.Integer(), nullable=False),
        sa.Column("fertilizer_cost", sa.Float(), nullable=False),
        sa.Column("water_cost", sa.Float(), nullable=False),
        sa.Column("labor_cost", sa.Float(), nullable=False),
        sa.CheckConstraint("fertilizer_cost >= 0", name="ck_input_costs_fertilizer_cost_non_negative"),
        sa.CheckConstraint("water_cost >= 0", name="ck_input_costs_water_cost_non_negative"),
        sa.CheckConstraint("labor_cost >= 0", name="ck_input_costs_labor_cost_non_negative"),
        sa.ForeignKeyConstraint(["crop_id"], ["crop_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("crop_id", name="uq_input_costs_crop_id"),
    )
    op.create_index("ix_input_costs_crop_id", "input_costs", ["crop_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_input_costs_crop_id", table_name="input_costs")
    op.drop_table("input_costs")
    op.drop_index("ix_crop_prices_crop_id", table_name="crop_prices")
    op.drop_table("crop_prices")
