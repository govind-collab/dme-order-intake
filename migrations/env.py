"""Alembic environment that runs migrations against the app's database.

Owns how Alembic connects: on the connection the app hands over at startup, or on a new one
built from DATABASE_URL when Alembic runs from the command line. It never configures logging,
so it cannot silence the app's loggers.
"""

from alembic import context
from sqlalchemy import Connection, create_engine

from app.config import settings
from app.models import Base


def run_migrations(connection: Connection) -> None:
    """Run the pending migrations on the connection in one transaction.

    Batch mode on SQLite lets later migrations alter tables, which SQLite cannot do in place.
    """
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


app_connection = context.config.attributes.get("connection")
if app_connection is not None:
    run_migrations(app_connection)
else:
    with create_engine(settings.database_url).connect() as cli_connection:
        run_migrations(cli_connection)
