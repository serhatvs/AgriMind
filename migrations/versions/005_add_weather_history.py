"""Add weather_history for daily field-scoped weather observations.

Revision ID: 005
Revises: 004
Create Date: 2026-03-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weather_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("min_temp", sa.Float(), nullable=False),
        sa.Column("max_temp", sa.Float(), nullable=False),
        sa.Column("avg_temp", sa.Float(), nullable=False),
        sa.Column("rainfall_mm", sa.Float(), nullable=False),
        sa.Column("humidity", sa.Float(), nullable=False),
        sa.Column("wind_speed", sa.Float(), nullable=False),
        sa.Column("solar_radiation", sa.Float(), nullable=True),
        sa.Column("et0", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_id", "date", name="uq_weather_history_field_id_date"),
        sa.CheckConstraint(
            "min_temp <= avg_temp AND avg_temp <= max_temp",
            name="ck_weather_history_temperature_order",
        ),
        sa.CheckConstraint(
            "rainfall_mm >= 0",
            name="ck_weather_history_rainfall_non_negative",
        ),
        sa.CheckConstraint(
            "humidity >= 0 AND humidity <= 100",
            name="ck_weather_history_humidity_range",
        ),
        sa.CheckConstraint(
            "wind_speed >= 0",
            name="ck_weather_history_wind_speed_non_negative",
        ),
        sa.CheckConstraint(
            "solar_radiation IS NULL OR solar_radiation >= 0",
            name="ck_weather_history_solar_radiation_non_negative",
        ),
        sa.CheckConstraint(
            "et0 IS NULL OR et0 >= 0",
            name="ck_weather_history_et0_non_negative",
        ),
    )
    op.create_index("ix_weather_history_id", "weather_history", ["id"], unique=False)
    op.create_index("ix_weather_history_field_id", "weather_history", ["field_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_weather_history_field_id", table_name="weather_history")
    op.drop_index("ix_weather_history_id", table_name="weather_history")
    op.drop_table("weather_history")
