from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import settings
from app.database import Base
from app.models import crop_economic_profile, crop_price, crop_profile, external_crop_statistics, feedback, field, field_crop_cycle, ingestion, input_cost, recommendation, soil_test, weather_history  # noqa

config = context.config
legacy_database_url = "postgresql://postgres:postgres@localhost:5432/agrimind"


def _escape_config_value(value: str) -> str:
    """Escape percent signs before storing values in the Alembic config parser."""

    return value.replace("%", "%%")


configured_database_url = config.get_main_option("sqlalchemy.url")
if configured_database_url in {"", legacy_database_url}:
    config.set_main_option("sqlalchemy.url", _escape_config_value(settings.DATABASE_URL))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
