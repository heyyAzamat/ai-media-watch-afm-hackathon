"""SQLAlchemy engine + session management (sync, psycopg3).

A sync engine is used deliberately: it is shared cleanly between Celery workers
(sync) and FastAPI (sync path operations run in a threadpool), avoiding the
complexity of mixing async DB sessions across two runtimes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    pass


def init_engine(database_url: str | None = None, echo: bool = False) -> Engine:
    """Initialise (once) and return the process-wide engine."""
    global _engine, _SessionLocal
    if _engine is None:
        url = database_url or get_settings().database_url
        _engine = create_engine(url, echo=echo, pool_pre_ping=True, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    if _SessionLocal is None:
        init_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_session() -> Session:
    """Return a new Session (caller is responsible for closing)."""
    return get_sessionmaker()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
