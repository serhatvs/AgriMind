from __future__ import annotations

from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.session import build_engine_options, get_db_session


class DummySession:
    """Minimal session stub used to verify cleanup behavior."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_build_engine_options_for_sqlite_memory_database():
    config = Settings(_env_file=None, DATABASE_URL="sqlite://")

    options = build_engine_options(config)

    assert options["connect_args"] == {"check_same_thread": False}
    assert options["poolclass"] is StaticPool
    assert "pool_size" not in options
    assert "max_overflow" not in options


def test_build_engine_options_for_postgresql_database():
    config = Settings(_env_file=None, DATABASE_URL="postgresql://user:pass@localhost:5432/agrimind")

    options = build_engine_options(config)

    assert options["pool_pre_ping"] is True
    assert options["pool_size"] == config.DATABASE_POOL_SIZE
    assert options["max_overflow"] == config.DATABASE_MAX_OVERFLOW
    assert options["pool_timeout"] == config.DATABASE_POOL_TIMEOUT_SECONDS
    assert options["connect_args"] == {"connect_timeout": config.DATABASE_CONNECT_TIMEOUT_SECONDS}


def test_get_db_session_closes_session_after_generator_finishes():
    session = DummySession()
    dependency = get_db_session(lambda: session)

    yielded_session = next(dependency)

    assert yielded_session is session
    assert session.closed is False

    try:
        next(dependency)
    except StopIteration:
        pass

    assert session.closed is True
