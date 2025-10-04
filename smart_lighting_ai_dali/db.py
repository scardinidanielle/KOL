from __future__ import annotations

import contextlib
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    declarative_base,
    scoped_session,
    sessionmaker,
)

from .config import get_settings


settings = get_settings()
engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False}
    if settings.db_url.startswith("sqlite")
    else {},
)
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextlib.contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["Base", "engine", "SessionLocal", "get_db", "session_scope"]
