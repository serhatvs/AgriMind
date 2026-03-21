"""Add external crop statistics table for FAOSTAT-style annual datasets.

Revision ID: 012
Revises: 011
Create Date: 2026-03-21 00:00:01.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


external_crop_statistic_type_enum = sa.Enum(
    "production",
    "yield",
    "harvested_area",
    name="external_crop_statistic_type_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "external_crop_statistics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=255), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("crop_name", sa.String(length=255), nullable=False),
        sa.Column("statistic_type", external_crop_statistic_type_enum, nullable=False),
        sa.Column("statistic_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("year >= 1900", name="ck_external_crop_statistics_year_floor"),
        sa.CheckConstraint(
            "statistic_value >= 0",
            name="ck_external_crop_statistics_value_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_name",
            "country",
            "year",
            "crop_name",
            "statistic_type",
            name="uq_external_crop_statistics_source_country_year_crop_stat",
        ),
    )
    op.create_index(op.f("ix_external_crop_statistics_country"), "external_crop_statistics", ["country"], unique=False)
    op.create_index(op.f("ix_external_crop_statistics_crop_name"), "external_crop_statistics", ["crop_name"], unique=False)
    op.create_index(op.f("ix_external_crop_statistics_id"), "external_crop_statistics", ["id"], unique=False)
    op.create_index(
        op.f("ix_external_crop_statistics_source_name"),
        "external_crop_statistics",
        ["source_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_crop_statistics_statistic_type"),
        "external_crop_statistics",
        ["statistic_type"],
        unique=False,
    )
    op.create_index(op.f("ix_external_crop_statistics_year"), "external_crop_statistics", ["year"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_external_crop_statistics_year"), table_name="external_crop_statistics")
    op.drop_index(op.f("ix_external_crop_statistics_statistic_type"), table_name="external_crop_statistics")
    op.drop_index(op.f("ix_external_crop_statistics_source_name"), table_name="external_crop_statistics")
    op.drop_index(op.f("ix_external_crop_statistics_id"), table_name="external_crop_statistics")
    op.drop_index(op.f("ix_external_crop_statistics_crop_name"), table_name="external_crop_statistics")
    op.drop_index(op.f("ix_external_crop_statistics_country"), table_name="external_crop_statistics")
    op.drop_table("external_crop_statistics")
