"""Migrations require an explicit isolated test/E2E database; never development."""
import os

from alembic import context
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, load_settings
from app.db import create_db_engine
from app.models import Base

target = context.get_x_argument(as_dictionary=True).get("target", "test")
if target not in {"test", "e2e"}:
    raise RuntimeError("Migration target must be test or e2e; development is forbidden.")
database = "aurameme_" + target
variable = "E2E_DATABASE_URL" if target == "e2e" else "TEST_DATABASE_URL"


def run_with_connection(connection):
    if make_url(load_settings().database_url.get_secret_value()).database == database:
        raise RuntimeError(f"Development DATABASE_URL must remain separate from {database}.")
    if connection.dialect.name != "postgresql":
        raise RuntimeError(f"Migrations require PostgreSQL {database}.")
    if connection.execute(text("SELECT current_database()")).scalar_one() != database:
        raise RuntimeError(f"Migrations are allowed only on {database} for this target.")
    if connection.execute(text("SELECT current_schema()")).scalar_one() != "public":
        raise RuntimeError(f"Migrations require the public schema of {database}.")
    context.configure(connection=connection, target_metadata=Base.metadata,
                      compare_type=True, compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online():
    connection = context.config.attributes.get("connection")
    if connection is not None:
        run_with_connection(connection)
        return
    value = os.environ.get(variable)
    if not value:
        raise RuntimeError(f"Set {variable} explicitly; migrations never default to development.")
    try:
        settings = Settings(_env_file=None, database_url=value)
    except ValidationError:
        raise RuntimeError(f"Invalid {variable}; use a PostgreSQL psycopg URL.") from None
    if make_url(settings.database_url.get_secret_value()).database != database:
        raise RuntimeError(f"{variable} must target {database}.")
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
