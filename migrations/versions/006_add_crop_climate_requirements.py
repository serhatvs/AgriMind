"""Add climate requirement fields to crop_profiles.

Revision ID: 006
Revises: 005
Create Date: 2026-03-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.add_column(sa.Column("optimal_temp_min_c", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("optimal_temp_max_c", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("rainfall_requirement_mm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("frost_tolerance_days", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("heat_tolerance_days", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_crop_profiles_optimal_temp_order",
            "optimal_temp_min_c IS NULL OR optimal_temp_max_c IS NULL OR optimal_temp_min_c <= optimal_temp_max_c",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_rainfall_requirement_non_negative",
            "rainfall_requirement_mm IS NULL OR rainfall_requirement_mm >= 0",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_frost_tolerance_non_negative",
            "frost_tolerance_days IS NULL OR frost_tolerance_days >= 0",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_heat_tolerance_non_negative",
            "heat_tolerance_days IS NULL OR heat_tolerance_days >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.drop_constraint("ck_crop_profiles_heat_tolerance_non_negative", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_frost_tolerance_non_negative", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_rainfall_requirement_non_negative", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_optimal_temp_order", type_="check")
        batch_op.drop_column("heat_tolerance_days")
        batch_op.drop_column("frost_tolerance_days")
        batch_op.drop_column("rainfall_requirement_mm")
        batch_op.drop_column("optimal_temp_max_c")
        batch_op.drop_column("optimal_temp_min_c")
