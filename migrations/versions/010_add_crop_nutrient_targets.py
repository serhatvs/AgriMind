"""Add persisted crop nutrient targets for management planning.

Revision ID: 010
Revises: 009
Create Date: 2026-03-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.add_column(sa.Column("target_nitrogen_ppm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("target_phosphorus_ppm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("target_potassium_ppm", sa.Float(), nullable=True))
        batch_op.create_check_constraint(
            "ck_crop_profiles_target_nitrogen_ppm_non_negative",
            "target_nitrogen_ppm IS NULL OR target_nitrogen_ppm >= 0",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_target_phosphorus_ppm_non_negative",
            "target_phosphorus_ppm IS NULL OR target_phosphorus_ppm >= 0",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_target_potassium_ppm_non_negative",
            "target_potassium_ppm IS NULL OR target_potassium_ppm >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.drop_constraint("ck_crop_profiles_target_potassium_ppm_non_negative", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_target_phosphorus_ppm_non_negative", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_target_nitrogen_ppm_non_negative", type_="check")
        batch_op.drop_column("target_potassium_ppm")
        batch_op.drop_column("target_phosphorus_ppm")
        batch_op.drop_column("target_nitrogen_ppm")
