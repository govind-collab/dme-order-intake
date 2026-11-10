"""Database engine and per-request sessions.

Owns the SQLAlchemy engine built from DATABASE_URL (SQLite locally and in tests, Postgres on
Render), the session factory and the DbSession dependency.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# FastAPI runs sync endpoints in a thread pool, so SQLite must allow cross-thread use
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Yield a session for one request and close it afterwards."""
    with SessionLocal() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]
