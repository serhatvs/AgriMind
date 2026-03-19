"""Expand the soil_tests table into the core soil test domain model.

Revision ID: 003
Revises: 002
Create Date: 2026-03-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("soil_tests") as batch_op:
        batch_op.alter_column(
            "ph_level",
            existing_type=sa.Float(),
            new_column_name="ph",
        )
        batch_op.alter_column(
            "soil_texture",
            existing_type=sa.String(),
            new_column_name="texture_class",
        )
        batch_op.alter_column(
            "tested_at",
            existing_type=sa.DateTime(),
            new_column_name="sample_date",
        )
        batch_op.add_column(sa.Column("ec", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("calcium_ppm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("magnesium_ppm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("drainage_class", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("depth_cm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("water_holding_capacity", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))

    soil_tests = sa.table(
        "soil_tests",
        sa.column("sample_date", sa.DateTime()),
        sa.column("created_at", sa.DateTime()),
    )

    op.execute(
        soil_tests.update()
        .where(soil_tests.c.sample_date.is_(None))
        .values(sample_date=sa.func.current_timestamp())
    )
    op.execute(soil_tests.update().values(created_at=sa.func.current_timestamp()))

    with op.batch_alter_table("soil_tests") as batch_op:
        batch_op.alter_column(
            "sample_date",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            "texture_class",
            existing_type=sa.String(),
            type_=sa.String(length=64),
            nullable=False,
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.create_index("ix_soil_tests_field_id", ["field_id"], unique=False)
        batch_op.create_check_constraint("ck_soil_tests_ph_range", "ph >= 0 AND ph <= 14")
        batch_op.create_check_constraint(
            "ck_soil_tests_ec_non_negative",
            "ec IS NULL OR ec >= 0",
        )
        batch_op.create_check_constraint(
            "ck_soil_tests_organic_matter_percent_range",
            "organic_matter_percent >= 0 AND organic_matter_percent <= 100",
        )
        batch_op.create_check_constraint(
            "ck_soil_tests_nitrogen_ppm_non_negative",
            "nitrogen_ppm >= 0",
        )
        batch_op.create_check_constraint(
            "ck_soil_tests_phosphorus_ppm_non_negative",
            "phosphorus_ppm >= 0",
        )
        batch_op.create_check_constraint(
            "ck_soil_tests_potassium_ppm_non_negative",
            "potassium_ppm >= 0",
        )
        batch_op.create_check_constraint(
            "ck_soil_tests_calcium_ppm_non_negative",
            "calcium_ppm IS NULL OR calcium_ppm >= 0",
        )
        batch_op.create_check_constraint(
            "ck_soil_tests_magnesium_ppm_non_negative",
            "magnesium_ppm IS NULL OR magnesium_ppm >= 0",
        )
        batch_op.create_check_constraint(
            "ck_soil_tests_depth_cm_positive",
            "depth_cm IS NULL OR depth_cm > 0",
        )
        batch_op.create_check_constraint(
            "ck_soil_tests_water_holding_capacity_non_negative",
            "water_holding_capacity IS NULL OR water_holding_capacity >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("soil_tests") as batch_op:
        batch_op.drop_constraint("ck_soil_tests_water_holding_capacity_non_negative", type_="check")
        batch_op.drop_constraint("ck_soil_tests_depth_cm_positive", type_="check")
        batch_op.drop_constraint("ck_soil_tests_magnesium_ppm_non_negative", type_="check")
        batch_op.drop_constraint("ck_soil_tests_calcium_ppm_non_negative", type_="check")
        batch_op.drop_constraint("ck_soil_tests_potassium_ppm_non_negative", type_="check")
        batch_op.drop_constraint("ck_soil_tests_phosphorus_ppm_non_negative", type_="check")
        batch_op.drop_constraint("ck_soil_tests_nitrogen_ppm_non_negative", type_="check")
        batch_op.drop_constraint("ck_soil_tests_organic_matter_percent_range", type_="check")
        batch_op.drop_constraint("ck_soil_tests_ec_non_negative", type_="check")
        batch_op.drop_constraint("ck_soil_tests_ph_range", type_="check")
        batch_op.drop_index("ix_soil_tests_field_id")
        batch_op.drop_column("created_at")
        batch_op.drop_column("notes")
        batch_op.drop_column("water_holding_capacity")
        batch_op.drop_column("depth_cm")
        batch_op.drop_column("drainage_class")
        batch_op.drop_column("magnesium_ppm")
        batch_op.drop_column("calcium_ppm")
        batch_op.drop_column("ec")
        batch_op.alter_column(
            "sample_date",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            nullable=True,
            new_column_name="tested_at",
        )
        batch_op.alter_column(
            "texture_class",
            existing_type=sa.String(length=64),
            type_=sa.String(),
            new_column_name="soil_texture",
        )
        batch_op.alter_column(
            "ph",
            existing_type=sa.Float(),
            new_column_name="ph_level",
        )
