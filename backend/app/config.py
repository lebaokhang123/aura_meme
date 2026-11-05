from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class ConfigurationError(RuntimeError):
    """Invalid backend configuration, safe to display without its values."""


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore", hide_input_in_errors=True)
    auth_signing_key: SecretStr
    auth_environment: Literal["development", "production"] = "production"
    auth_allowed_origins: list[str] = ["https://localhost:8000"]

    @model_validator(mode="after")
    def check_auth_security(self):
        key = self.auth_signing_key.get_secret_value()
        if len(key.encode()) < 32 or key.startswith("CHANGE_ME"):
            raise ValueError("AUTH_SIGNING_KEY must contain at least 32 random bytes.")
        if not self.auth_allowed_origins:
            raise ValueError("AUTH_ALLOWED_ORIGINS must not be empty.")
        for origin in self.auth_allowed_origins:
            parsed = urlsplit(origin)
            _ = parsed.port  # Validate the optional port as well as the hostname.
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
                    or "*" in origin):
                raise ValueError("AUTH_ALLOWED_ORIGINS must contain exact HTTP(S) origins.")
            if self.auth_environment == "production" and parsed.scheme != "https":
                raise ValueError("Production authentication requires HTTPS origins.")
            if self.auth_environment == "development" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("Development HTTP mode is restricted to loopback origins.")
        return self


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
