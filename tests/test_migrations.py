"""Tests for the migrations that run when the app starts.

Owns the three database states the app can meet: empty, made by create_all before migrations
existed, and already migrated.
"""

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import select

from app.db import ALEMBIC_INI, SessionLocal, engine, migrate_database
from app.models import Base, Order, User

HEAD = ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_current_head()


def current_revision() -> str | None:
    """Return the revision the database is stamped with, or None if it has none."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def test_empty_database_is_migrated_to_match_the_models(empty_database: None) -> None:
    """Expect the migrations to build tables identical to the models and stamp head."""
    migrate_database()

    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    assert current_revision() == HEAD


def test_tables_made_before_migrations_are_stamped_and_keep_their_rows(
    empty_database: None,
) -> None:
    """Expect pre-migration tables to be stamped, not created again, with their rows intact."""
    # The tables create_all made before migrations existed, as on the first live database
    Base.metadata.create_all(engine, tables=[User.__table__, Order.__table__])
    with SessionLocal() as db:
        db.add(User(email="kept@example.com", password_hash="hash"))
        db.commit()

    migrate_database()

    assert current_revision() == HEAD
    with SessionLocal() as db:
        assert db.scalars(select(User.email)).all() == ["kept@example.com"]


def test_migrating_an_up_to_date_database_changes_nothing(empty_database: None) -> None:
    """Expect a second start on a migrated database to succeed and keep the revision."""
    migrate_database()
    migrate_database()

    assert current_revision() == HEAD
