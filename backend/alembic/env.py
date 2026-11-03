"""M1.4 is deliberately restricted to the dedicated PostgreSQL test database."""
import os

from alembic import context
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, load_settings
from app.db import create_db_engine
from app.models import Base


def run_with_connection(connection):
    if make_url(load_settings().database_url.get_secret_value()).database == "aurameme_test":
        raise RuntimeError("Development DATABASE_URL must remain separate from aurameme_test.")
    if connection.dialect.name != "postgresql":
        raise RuntimeError("M1.4 requires PostgreSQL aurameme_test.")
    if connection.execute(text("SELECT current_database()")).scalar_one() != "aurameme_test":
        raise RuntimeError("M1.4 migrations are allowed only on aurameme_test.")
    if connection.execute(text("SELECT current_schema()")).scalar_one() != "public":
        raise RuntimeError("M1.4 requires the public schema of aurameme_test.")
    context.configure(connection=connection, target_metadata=Base.metadata,
                      compare_type=True, compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online():
    connection = context.config.attributes.get("connection")
    if connection is not None:
        run_with_connection(connection)
        return
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        raise RuntimeError("Set TEST_DATABASE_URL explicitly; M1.4 never defaults to development.")
    try:
        settings = Settings(_env_file=None, database_url=value)
    except ValidationError:
        raise RuntimeError("Invalid TEST_DATABASE_URL; use a PostgreSQL psycopg URL.") from None
    if make_url(settings.database_url.get_secret_value()).database != "aurameme_test":
        raise RuntimeError("TEST_DATABASE_URL must target aurameme_test.")
    engine = create_db_engine(settings)
    try:
        with engine.begin() as connection:
            run_with_connection(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("M1.4 requires an online connection to aurameme_test; offline SQL is disabled.")
try:
    run_online()
except SQLAlchemyError:
    raise RuntimeError("PostgreSQL migration failed; check availability and schema on aurameme_test.") from None
