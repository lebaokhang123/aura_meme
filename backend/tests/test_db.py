import os
import socket
import traceback
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.db import DatabaseConnectionError, check_connection, create_db_engine, main


def test_unavailable_database_fails_safely_and_returns_connection(caplog):
    # Reserve a local port without listening so no database can answer this probe.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
        settings = Settings(
            _env_file=None,
            database_url=f"postgresql+psycopg://test:secret-marker@127.0.0.1:{port}/test",
            db_connect_timeout=1,
        )
        engine = create_db_engine(settings)
        try:
            with pytest.raises(DatabaseConnectionError) as error:
                check_connection(engine)
            assert "PostgreSQL" in str(error.value)
            assert "secret-marker" not in "".join(traceback.format_exception(error.value)) + caplog.text
            assert engine.pool.checkedout() == 0
        finally:
            engine.dispose()


@pytest.mark.parametrize("failure_at", ["connect", "query"])
def test_driver_error_containing_credentials_is_not_printed(failure_at, caplog):
    engine = MagicMock()
    target = (
        engine.connect
        if failure_at == "connect"
        else engine.connect.return_value.__enter__.return_value.execute
    )
    target.side_effect = OperationalError("SELECT 1", {}, Exception("secret-marker"))
    with pytest.raises(DatabaseConnectionError) as error:
        check_connection(engine)
    assert "secret-marker" not in "".join(traceback.format_exception(error.value)) + caplog.text


def test_probe_cli_returns_failure_for_bad_config(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "sqlite://secret-marker")
    assert main() == 1
    output = capsys.readouterr()
    assert "DATABASE_URL" in output.err
    assert "secret-marker" not in output.out + output.err


@pytest.mark.integration
def test_real_postgresql_select_one():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured; real PostgreSQL was not tested")
    engine = create_db_engine(Settings(_env_file=None, database_url=url))
    try:
        check_connection(engine)
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()
