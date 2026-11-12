"""Explicit isolated targets; demo is pinned upgrade-only, development forbidden."""
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
if target not in {"test", "e2e", "demo"}:
    raise RuntimeError("Migration target must be test, e2e or demo; development is forbidden.")

if target == 'demo':
    options = context.config.cmd_opts
    operation = getattr(options, 'cmd', (None,))[0]
    if (getattr(operation, '__name__', '') not in {'current', 'upgrade'}
            or (operation.__name__ == 'upgrade' and getattr(options, 'revision', None) not in {'head', '0009_vault_open'})):
        raise RuntimeError('Demo migrations allow only current or upgrade to 0009_vault_open.')
    from alembic.script import ScriptDirectory
    if ScriptDirectory.from_config(context.config).get_current_head() != '0009_vault_open':
        raise RuntimeError('Demo requires reviewed migration head 0009_vault_open.')
database = "aurameme_" + target
variable = {"test": "TEST_DATABASE_URL", "e2e": "E2E_DATABASE_URL", "demo": "DEMO_DATABASE_URL"}[target]


def run_with_connection(connection):
    if make_url(load_settings().database_url.get_secret_value()).database == database:
        raise RuntimeError(f"Development DATABASE_URL must remain separate from {database}.")
    if connection.dialect.name != "postgresql":
        raise RuntimeError(f"Migrations require PostgreSQL {database}.")
    if connection.execute(text("SELECT current_database()")).scalar_one() != database:
        raise RuntimeError(f"Migrations are allowed only on {database} for this target.")
    if connection.execute(text("SELECT current_schema()")).scalar_one() != "public":
        raise RuntimeError(f"Migrations require the public schema of {database}.")
    if target == 'demo':
        from app.demo import demo_connection
        from sqlalchemy import inspect
        demo_connection(connection)
        inspector = inspect(connection)
        if (inspector.get_view_names() or inspector.get_materialized_view_names() or inspector.get_sequence_names()
                or connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','information_schema') AND nspname NOT LIKE 'pg_%'"))):
            raise RuntimeError('Unexpected demo schema objects; stop for review.')
        tables = set(inspect(connection).get_table_names())
        if tables:
            if (tables != set(Base.metadata.tables) | {'alembic_version'}
                    or connection.scalar(text('SELECT version_num FROM alembic_version')) != '0009_vault_open'):
                raise RuntimeError('Existing demo schema must be at reviewed head; stop for review.')
            from alembic.autogenerate import compare_metadata
            from alembic.migration import MigrationContext
            if compare_metadata(MigrationContext.configure(connection, opts={'compare_server_default': True}), Base.metadata):
                raise RuntimeError('Demo schema drift; stop for review.')
        elif connection.scalar(text("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public'")):
            raise RuntimeError('Unexpected functions in empty demo; stop for review.')
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
    if target == 'demo':
        from app.demo import validate_demo_url
        validate_demo_url(value)
    engine = create_db_engine(settings)
    try:
        with engine.begin() as connection:
            run_with_connection(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Migrations require online identity checks; offline SQL is disabled.")
try:
    run_online()
except SQLAlchemyError:
    raise RuntimeError(f"PostgreSQL migration failed; check availability and schema on {database}.") from None
