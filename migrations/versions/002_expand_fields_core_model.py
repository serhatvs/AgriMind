"""Expand the fields table into the core field domain model.

Revision ID: 002
Revises: 001
Create Date: 2026-03-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

FIELD_ASPECT_VALUES = (
    "flat",
    "north",
    "northeast",
    "east",
    "southeast",
    "south",
    "southwest",
    "west",
    "northwest",
)
WATER_SOURCE_TYPE_VALUES = (
    "none",
    "canal",
    "river",
    "reservoir",
    "well",
    "borehole",
    "rainwater_harvest",
    "municipal",
    "mixed",
)
FIELD_ASPECT_ENUM_NAME = "field_aspect_enum"
WATER_SOURCE_TYPE_ENUM_NAME = "water_source_type_enum"


def _enum_type(enum_name: str, values: tuple[str, ...], dialect_name: str) -> sa.Enum:
    if dialect_name == "postgresql":
        return postgresql.ENUM(*values, name=enum_name, create_type=False)
    return sa.Enum(*values, name=enum_name, native_enum=False)


def _create_enum_types(bind: sa.Connection, dialect_name: str) -> None:
    if dialect_name != "postgresql":
        return

    postgresql.ENUM(*FIELD_ASPECT_VALUES, name=FIELD_ASPECT_ENUM_NAME).create(bind, checkfirst=True)
    postgresql.ENUM(*WATER_SOURCE_TYPE_VALUES, name=WATER_SOURCE_TYPE_ENUM_NAME).create(bind, checkfirst=True)


def _drop_enum_types(bind: sa.Connection, dialect_name: str) -> None:
    if dialect_name != "postgresql":
        return

    postgresql.ENUM(*WATER_SOURCE_TYPE_VALUES, name=WATER_SOURCE_TYPE_ENUM_NAME).drop(bind, checkfirst=True)
    postgresql.ENUM(*FIELD_ASPECT_VALUES, name=FIELD_ASPECT_ENUM_NAME).drop(bind, checkfirst=True)


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    aspect_type = _enum_type(FIELD_ASPECT_ENUM_NAME, FIELD_ASPECT_VALUES, dialect_name)
    water_source_type = _enum_type(
        WATER_SOURCE_TYPE_ENUM_NAME,
        WATER_SOURCE_TYPE_VALUES,
        dialect_name,
    )

    _create_enum_types(bind, dialect_name)

    with op.batch_alter_table("fields") as batch_op:
        batch_op.alter_column(
            "location",
            existing_type=sa.String(),
            new_column_name="location_name",
        )
        batch_op.add_column(sa.Column("latitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("longitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("elevation_meters", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("aspect", aspect_type, nullable=True))
        batch_op.add_column(sa.Column("water_source_type", water_source_type, nullable=True))
        batch_op.add_column(sa.Column("infrastructure_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))

    fields = sa.table(
        "fields",
        sa.column("slope_percent", sa.Float()),
        sa.column("irrigation_available", sa.Boolean()),
        sa.column("drainage_quality", sa.String()),
        sa.column("infrastructure_score", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("location_name", sa.String()),
    )

    op.execute(
        fields.update()
        .where(fields.c.slope_percent.is_(None))
        .values(slope_percent=0.0)
    )
    op.execute(
        fields.update()
        .where(fields.c.irrigation_available.is_(None))
        .values(irrigation_available=False)
    )
    op.execute(
        fields.update()
        .where(fields.c.drainage_quality.is_(None))
        .values(drainage_quality="moderate")
    )
    op.execute(fields.update().values(infrastructure_score=0))
    op.execute(
        fields.update()
        .where(fields.c.created_at.is_(None))
        .values(created_at=sa.func.current_timestamp())
    )
    op.execute(
        fields.update()
        .where(fields.c.updated_at.is_(None))
        .values(updated_at=fields.c.created_at)
    )

    with op.batch_alter_table("fields") as batch_op:
        batch_op.alter_column(
            "location_name",
            existing_type=sa.String(),
            type_=sa.String(length=255),
            nullable=False,
        )
        batch_op.alter_column(
            "name",
            existing_type=sa.String(),
            type_=sa.String(length=255),
            nullable=False,
        )
        batch_op.alter_column(
            "slope_percent",
            existing_type=sa.Float(),
            nullable=False,
        )
        batch_op.alter_column(
            "irrigation_available",
            existing_type=sa.Boolean(),
            nullable=False,
        )
        batch_op.alter_column(
            "drainage_quality",
            existing_type=sa.String(),
            type_=sa.String(length=32),
            nullable=False,
        )
        batch_op.alter_column(
            "infrastructure_score",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_fields_latitude_range",
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
        )
        batch_op.create_check_constraint(
            "ck_fields_longitude_range",
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
        )
        batch_op.create_check_constraint(
            "ck_fields_area_hectares_positive",
            "area_hectares > 0",
        )
        batch_op.create_check_constraint(
            "ck_fields_slope_percent_range",
            "slope_percent >= 0 AND slope_percent <= 100",
        )
        batch_op.create_check_constraint(
            "ck_fields_infrastructure_score_range",
            "infrastructure_score >= 0 AND infrastructure_score <= 100",
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    with op.batch_alter_table("fields") as batch_op:
        batch_op.drop_constraint("ck_fields_infrastructure_score_range", type_="check")
        batch_op.drop_constraint("ck_fields_slope_percent_range", type_="check")
        batch_op.drop_constraint("ck_fields_area_hectares_positive", type_="check")
        batch_op.drop_constraint("ck_fields_longitude_range", type_="check")
        batch_op.drop_constraint("ck_fields_latitude_range", type_="check")
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            nullable=True,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            nullable=True,
        )
        batch_op.alter_column(
            "drainage_quality",
            existing_type=sa.String(length=32),
            type_=sa.String(),
            nullable=True,
        )
        batch_op.alter_column(
            "irrigation_available",
            existing_type=sa.Boolean(),
            nullable=True,
        )
        batch_op.alter_column(
            "slope_percent",
            existing_type=sa.Float(),
            nullable=True,
        )
        batch_op.drop_column("notes")
        batch_op.drop_column("infrastructure_score")
        batch_op.drop_column("water_source_type")
        batch_op.drop_column("aspect")
        batch_op.drop_column("elevation_meters")
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")
        batch_op.alter_column(
            "location_name",
            existing_type=sa.String(length=255),
            new_column_name="location",
        )

    _drop_enum_types(bind, dialect_name)
