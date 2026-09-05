"""Backend database — SQLAlchemy 2.0; SQLite by default, PostgreSQL +
PostGIS in production via DATABASE_URL.

Set DATABASE_URL BEFORE importing netra_backend.models (the PostGIS
geometry column is decided at import time):

    DATABASE_URL=postgresql+psycopg2://user:pass@host/db

with `pip install netra-backend[postgres]` (geoalchemy2 + psycopg2).
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_ENGINE = None
_SESSION_FACTORY = None


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///netra_backend.db")


def postgis_enabled(url: str = None) -> bool:
    url = url or database_url()
    if not url.startswith("postgresql"):
        return False
    try:
        import geoalchemy2                    # noqa: F401
    except Exception:
        return False
    return True


def reset(url: str = None) -> None:
    """(Re)create the engine + session factory and create tables.
    Tests call this with a temporary SQLite URL."""
    global _ENGINE, _SESSION_FACTORY
    from .models import Base
    _ENGINE = create_engine(url or database_url(), future=True)
    _SESSION_FACTORY = sessionmaker(bind=_ENGINE, expire_on_commit=False,
                                    future=True)
    Base.metadata.create_all(_ENGINE)


def get_engine():
    if _ENGINE is None:
        reset()
    return _ENGINE


def get_session():
    if _SESSION_FACTORY is None:
        reset()
    return _SESSION_FACTORY()


def dispose() -> None:
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _SESSION_FACTORY = None
