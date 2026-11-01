import pytest
from pydantic import ValidationError

from app.config import ConfigurationError, Settings, load_settings


URL = "postgresql+psycopg://test:secret-marker@127.0.0.1:5432/test"


def test_reads_dotenv_and_environment_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_CONNECT_TIMEOUT", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(f"DATABASE_URL={URL}\nDB_CONNECT_TIMEOUT=3\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.database_url.get_secret_value() == URL
    assert settings.db_connect_timeout == 3
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "2")
    assert Settings(_env_file=env_file).db_connect_timeout == 2
    assert "secret-marker" not in repr(settings) + settings.model_dump_json()


def test_missing_required_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        load_settings(env_file=None)


@pytest.mark.parametrize("url", [
    "", "secret-marker", "sqlite:///secret-marker", "postgresql://test:secret-marker@localhost/test",
    "postgresql+psycopg://test:secret-marker@/test",
    "postgresql+psycopg://test:secret-marker@localhost",
    "postgresql+psycopg://localhost/test",
    "postgresql+psycopg://test:secret-marker@localhost:bad/test",
])
def test_invalid_urls_are_rejected_without_exposing_input(url):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=url)
    assert "secret-marker" not in str(error.value)


@pytest.mark.parametrize("timeout", [0, 31, "secret-marker"])
def test_invalid_timeout_is_rejected(timeout):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=URL, db_connect_timeout=timeout)
    assert "secret-marker" not in str(error.value)


def test_public_configuration_error_redacts_other_environment_values(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "secret-marker")
    with pytest.raises(ConfigurationError) as error:
        load_settings(env_file=None)
    assert "DB_CONNECT_TIMEOUT" in str(error.value)
    assert "secret-marker" not in str(error.value)
