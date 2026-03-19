"""Expand crop_profiles into the agronomic crop requirement domain model.

Revision ID: 004
Revises: 003
Create Date: 2026-03-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.alter_column(
            "name",
            existing_type=sa.String(),
            new_column_name="crop_name",
        )
        batch_op.alter_column(
            "optimal_ph_min",
            existing_type=sa.Float(),
            new_column_name="ideal_ph_min",
        )
        batch_op.alter_column(
            "optimal_ph_max",
            existing_type=sa.Float(),
            new_column_name="ideal_ph_max",
        )
        batch_op.alter_column(
            "min_ph",
            existing_type=sa.Float(),
            new_column_name="tolerable_ph_min",
        )
        batch_op.alter_column(
            "max_ph",
            existing_type=sa.Float(),
            new_column_name="tolerable_ph_max",
        )
        batch_op.alter_column(
            "water_requirement",
            existing_type=sa.String(),
            new_column_name="water_requirement_level",
        )
        batch_op.alter_column(
            "max_slope_percent",
            existing_type=sa.Float(),
            new_column_name="slope_tolerance",
        )
        batch_op.add_column(sa.Column("scientific_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("frost_sensitivity", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("heat_sensitivity", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("salinity_tolerance", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("rooting_depth_cm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("organic_matter_preference", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    crop_profiles = sa.table(
        "crop_profiles",
        sa.column("variety", sa.String()),
        sa.column("frost_sensitivity", sa.String()),
        sa.column("heat_sensitivity", sa.String()),
        sa.column("organic_matter_preference", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("notes", sa.Text()),
    )

    op.execute(
        crop_profiles.update().values(
            frost_sensitivity="medium",
            heat_sensitivity="medium",
            organic_matter_preference="moderate",
            created_at=sa.func.current_timestamp(),
            updated_at=sa.func.current_timestamp(),
        )
    )
    op.execute(
        crop_profiles.update()
        .where(crop_profiles.c.variety.is_not(None))
        .values(notes=sa.literal("Legacy variety: ") + crop_profiles.c.variety)
    )

    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.drop_column("variety")
        batch_op.drop_column("min_nitrogen_ppm")
        batch_op.drop_column("min_phosphorus_ppm")
        batch_op.drop_column("min_potassium_ppm")
        batch_op.drop_column("preferred_soil_textures")
        batch_op.drop_column("min_area_hectares")
        batch_op.alter_column(
            "crop_name",
            existing_type=sa.String(),
            type_=sa.String(length=255),
            nullable=False,
        )
        batch_op.alter_column(
            "water_requirement_level",
            existing_type=sa.String(),
            type_=sa.String(length=16),
            nullable=False,
        )
        batch_op.alter_column(
            "drainage_requirement",
            existing_type=sa.String(),
            type_=sa.String(length=16),
            nullable=False,
        )
        batch_op.alter_column(
            "frost_sensitivity",
            existing_type=sa.String(length=16),
            nullable=False,
        )
        batch_op.alter_column(
            "heat_sensitivity",
            existing_type=sa.String(length=16),
            nullable=False,
        )
        batch_op.alter_column(
            "organic_matter_preference",
            existing_type=sa.String(length=16),
            nullable=True,
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.create_index("ix_crop_profiles_crop_name", ["crop_name"], unique=False)
        batch_op.create_check_constraint(
            "ck_crop_profiles_ideal_ph_min_range",
            "ideal_ph_min >= 0 AND ideal_ph_min <= 14",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_ideal_ph_max_range",
            "ideal_ph_max >= 0 AND ideal_ph_max <= 14",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_tolerable_ph_min_range",
            "tolerable_ph_min >= 0 AND tolerable_ph_min <= 14",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_tolerable_ph_max_range",
            "tolerable_ph_max >= 0 AND tolerable_ph_max <= 14",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_ideal_ph_order",
            "ideal_ph_min <= ideal_ph_max",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_tolerable_ph_order",
            "tolerable_ph_min <= tolerable_ph_max",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_tolerable_min_not_above_ideal_min",
            "tolerable_ph_min <= ideal_ph_min",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_ideal_max_not_above_tolerable_max",
            "ideal_ph_max <= tolerable_ph_max",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_rooting_depth_cm_positive",
            "rooting_depth_cm IS NULL OR rooting_depth_cm > 0",
        )
        batch_op.create_check_constraint(
            "ck_crop_profiles_slope_tolerance_range",
            "slope_tolerance IS NULL OR (slope_tolerance >= 0 AND slope_tolerance <= 100)",
        )


def downgrade() -> None:
    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.add_column(sa.Column("variety", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("min_nitrogen_ppm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("min_phosphorus_ppm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("min_potassium_ppm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("preferred_soil_textures", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("min_area_hectares", sa.Float(), nullable=True))

    crop_profiles = sa.table(
        "crop_profiles",
        sa.column("min_nitrogen_ppm", sa.Float()),
        sa.column("min_phosphorus_ppm", sa.Float()),
        sa.column("min_potassium_ppm", sa.Float()),
        sa.column("preferred_soil_textures", sa.String()),
        sa.column("min_area_hectares", sa.Float()),
    )

    op.execute(
        crop_profiles.update().values(
            min_nitrogen_ppm=0.0,
            min_phosphorus_ppm=0.0,
            min_potassium_ppm=0.0,
            preferred_soil_textures="",
            min_area_hectares=0.0,
        )
    )

    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.drop_constraint("ck_crop_profiles_slope_tolerance_range", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_rooting_depth_cm_positive", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_ideal_max_not_above_tolerable_max", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_tolerable_min_not_above_ideal_min", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_tolerable_ph_order", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_ideal_ph_order", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_tolerable_ph_max_range", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_tolerable_ph_min_range", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_ideal_ph_max_range", type_="check")
        batch_op.drop_constraint("ck_crop_profiles_ideal_ph_min_range", type_="check")
        batch_op.drop_index("ix_crop_profiles_crop_name")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("notes")
        batch_op.drop_column("organic_matter_preference")
        batch_op.drop_column("rooting_depth_cm")
        batch_op.drop_column("salinity_tolerance")
        batch_op.drop_column("heat_sensitivity")
        batch_op.drop_column("frost_sensitivity")
        batch_op.drop_column("scientific_name")
        batch_op.alter_column(
            "slope_tolerance",
            existing_type=sa.Float(),
            new_column_name="max_slope_percent",
        )
        batch_op.alter_column(
            "water_requirement_level",
            existing_type=sa.String(length=16),
            type_=sa.String(),
            new_column_name="water_requirement",
        )
        batch_op.alter_column(
            "tolerable_ph_max",
            existing_type=sa.Float(),
            new_column_name="max_ph",
        )
        batch_op.alter_column(
            "tolerable_ph_min",
            existing_type=sa.Float(),
            new_column_name="min_ph",
        )
        batch_op.alter_column(
            "ideal_ph_max",
            existing_type=sa.Float(),
            new_column_name="optimal_ph_max",
        )
        batch_op.alter_column(
            "ideal_ph_min",
            existing_type=sa.Float(),
            new_column_name="optimal_ph_min",
        )
        batch_op.alter_column(
            "crop_name",
            existing_type=sa.String(length=255),
            type_=sa.String(),
            new_column_name="name",
        )
        batch_op.alter_column(
            "min_nitrogen_ppm",
            existing_type=sa.Float(),
            nullable=False,
        )
        batch_op.alter_column(
            "min_phosphorus_ppm",
            existing_type=sa.Float(),
            nullable=False,
        )
        batch_op.alter_column(
            "min_potassium_ppm",
            existing_type=sa.Float(),
            nullable=False,
        )
        batch_op.alter_column(
            "preferred_soil_textures",
            existing_type=sa.String(),
            nullable=False,
        )
        batch_op.alter_column(
            "min_area_hectares",
            existing_type=sa.Float(),
            nullable=True,
        )
