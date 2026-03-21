"""Add extended crop climate range fields.

Revision ID: 013
Revises: 012
Create Date: 2026-03-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.add_column(sa.Column("tolerable_temp_min_c", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("tolerable_temp_max_c", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("preferred_rainfall_min_mm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("preferred_rainfall_max_mm", sa.Float(), nullable=True))
        batch_op.create_check_constraint(
            "ck_crop_profiles_tolerable_temp_order",
            "tolerable_temp_min_c IS NULL OR tolerable_temp_max_c IS NULL OR tolerable_temp_min_c <= tolerable_temp_max_c",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_tolerable_temp_min_not_above_optimal_min",
            "optimal_temp_min_c IS NULL OR tolerable_temp_min_c IS NULL OR tolerable_temp_min_c <= optimal_temp_min_c",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_optimal_temp_max_not_above_tolerable_max",
            "optimal_temp_max_c IS NULL OR tolerable_temp_max_c IS NULL OR optimal_temp_max_c <= tolerable_temp_max_c",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_preferred_rainfall_min_non_negative",
            "preferred_rainfall_min_mm IS NULL OR preferred_rainfall_min_mm >= 0",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_preferred_rainfall_max_non_negative",
            "preferred_rainfall_max_mm IS NULL OR preferred_rainfall_max_mm >= 0",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_preferred_rainfall_order",
            "preferred_rainfall_min_mm IS NULL OR preferred_rainfall_max_mm IS NULL OR preferred_rainfall_min_mm <= preferred_rainfall_max_mm",
        )


def downgrade() -> None:
    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.drop_constraint("ck_crop_profiles_preferred_rainfall_order", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_preferred_rainfall_max_non_negative", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_preferred_rainfall_min_non_negative", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_optimal_temp_max_not_above_tolerable_max", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_tolerable_temp_min_not_above_optimal_min", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_tolerable_temp_order", type_="check")
        batch_op.drop_column("preferred_rainfall_max_mm")
        batch_op.drop_column("preferred_rainfall_min_mm")
        batch_op.drop_column("tolerable_temp_max_c")
        batch_op.drop_column("tolerable_temp_min_c")
