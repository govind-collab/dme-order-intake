"""Database engine, per-request sessions and migrations on start.

Owns the SQLAlchemy engine built from DATABASE_URL (SQLite locally and in tests, Postgres on
Render), the session factory, the DbSession dependency, and bringing the schema up to the
latest Alembic migration.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from alembic import command
from alembic.config import Config
from fastapi import Depends
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

ALEMBIC_INI = Path(__file__).parent.parent / "alembic.ini"
FIRST_REVISION = "0001"

# FastAPI runs sync endpoints in a thread pool, so SQLite must allow cross-thread use
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
# Bound values are patient data, and SQLAlchemy would otherwise print them in error messages,
# which end up in the server log whenever a write fails
engine = create_engine(
    settings.database_url, connect_args=connect_args, pool_pre_ping=True, hide_parameters=True
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Yield a session for one request and close it afterwards."""
    with SessionLocal() as session:
        yield session


def migrate_database() -> None:
    """Bring the database schema up to the latest migration.

    Databases created before migrations existed already have the users and orders tables but
    no alembic_version table. Those are stamped as being on the first migration, which matches
    the tables, instead of creating them again; then every database is upgraded to head. It all
    runs in one transaction, so a failure changes nothing.
    """
    config = Config(str(ALEMBIC_INI))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "alembic_version" not in tables and {"users", "orders"} <= tables:
            command.stamp(config, FIRST_REVISION)
        command.upgrade(config, "head")


DbSession = Annotated[Session, Depends(get_db)]
