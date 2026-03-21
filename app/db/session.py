"""SQLAlchemy engine, session factory, and FastAPI database dependency."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, settings


SessionFactory = sessionmaker[Session]


def _is_sqlite_database(database_url: str) -> bool:
    """Return whether the configured database URL targets SQLite."""

    return make_url(database_url).get_backend_name() == "sqlite"


def build_engine_options(app_settings: Settings) -> dict[str, Any]:
    """Build SQLAlchemy engine options from application settings."""

    options: dict[str, Any] = {
        "echo": app_settings.DATABASE_ECHO,
        "pool_pre_ping": app_settings.DATABASE_POOL_PRE_PING,
    }

    if _is_sqlite_database(app_settings.DATABASE_URL):
        options["connect_args"] = {"check_same_thread": False}
        if app_settings.DATABASE_URL in {"sqlite://", "sqlite:///:memory:"}:
            options["poolclass"] = StaticPool
        return options

    options["pool_size"] = app_settings.DATABASE_POOL_SIZE
    options["max_overflow"] = app_settings.DATABASE_MAX_OVERFLOW
    options["pool_timeout"] = app_settings.DATABASE_POOL_TIMEOUT_SECONDS
    options["connect_args"] = {
        "connect_timeout": app_settings.DATABASE_CONNECT_TIMEOUT_SECONDS,
    }
    return options


def create_engine_from_settings(app_settings: Settings) -> Engine:
    """Create a SQLAlchemy engine using the configured environment settings."""

    return create_engine(
        app_settings.DATABASE_URL,
        **build_engine_options(app_settings),
    )


def create_session_factory(db_engine: Engine) -> SessionFactory:
    """Create the configured SQLAlchemy session factory for the application."""

    return sessionmaker(
        bind=db_engine,
        class_=Session,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


engine = create_engine_from_settings(settings)
SessionLocal = create_session_factory(engine)


def get_db_session(session_factory: Callable[[], Session]) -> Generator[Session, None, None]:
    """Yield a database session and always close it after the request lifecycle."""

    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a SQLAlchemy session per request."""

    yield from get_db_session(SessionLocal)


def check_database_connection(db_engine: Engine | None = None) -> None:
    """Fail fast if the configured database is unavailable."""

    engine_to_check = db_engine or engine
    with engine_to_check.connect() as connection:
        connection.execute(text("SELECT 1"))


def dispose_database_engine(db_engine: Engine | None = None) -> None:
    """Release pooled database connections on application shutdown."""

    engine_to_dispose = db_engine or engine
    engine_to_dispose.dispose()

