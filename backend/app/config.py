from pathlib import Path

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class ConfigurationError(RuntimeError):
    """Invalid backend configuration, safe to display without its values."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: SecretStr
    db_connect_timeout: int = Field(default=5, ge=1, le=30)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "postgresql+psycopg"
                and bool(url.host and url.username and url.database)
                and (url.port is None or 1 <= url.port <= 65535)
            )
        except (ArgumentError, ValueError):
            valid = False
        if not valid:
            raise ValueError(
                "Use postgresql+psycopg://user[:password]@host[:port]/database"
            ) from None
        return value


def load_settings(env_file: Path | None = ENV_FILE) -> Settings:
    try:
        return Settings(_env_file=env_file)
    except ValidationError as error:
        fields = sorted({str(item["loc"][0]).upper() for item in error.errors()})
        raise ConfigurationError(
            "Invalid backend configuration: " + ", ".join(fields)
            + ". Set DATABASE_URL to postgresql+psycopg://user[:password]@host[:port]/database"
            + " and DB_CONNECT_TIMEOUT to an integer from 1 to 30 in backend/.env or environment."
        ) from None
    except OSError:
        raise ConfigurationError("Cannot read backend/.env; check file access.") from None
