import sys

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import ConfigurationError, Settings, load_settings


class DatabaseConnectionError(RuntimeError):
    """PostgreSQL probe failure with no driver details or credentials."""


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.db_connect_timeout},
        hide_parameters=True,
        echo=False,
    )


def check_connection(engine: Engine) -> None:
    try:
        with engine.connect() as connection:
            if connection.execute(text("SELECT 1")).scalar_one() != 1:
                raise DatabaseConnectionError("PostgreSQL probe did not return 1.")
    except SQLAlchemyError:
        # Driver errors may include credentials; keep them out of displayed tracebacks.
        raise DatabaseConnectionError(
            "PostgreSQL is unavailable. Check service, network, credentials and database name."
        ) from None


def main() -> int:
    engine = None
    try:
        engine = create_db_engine(load_settings())
        check_connection(engine)
        print("PostgreSQL connection OK (SELECT 1).")
        return 0
    except (ConfigurationError, DatabaseConnectionError) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
