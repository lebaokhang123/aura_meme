"""Auth request/response allowlists from the M0.5 contract."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator


class LoginInput(BaseModel):
    email: EmailStr
    password: SecretStr

    @field_validator("password")
    @classmethod
    def valid_password_encoding(cls, value):
        try:
            value.get_secret_value().encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Password must be valid Unicode.") from None
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class RegisterInput(LoginInput):
    password: SecretStr = Field(json_schema_extra={"minLength": 12, "maxLength": 128})
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("password")
    @classmethod
    def password_length(cls, value):
        if not 12 <= len(value.get_secret_value()) <= 128:
            raise ValueError("Password must contain 12 to 128 characters.")
        return value

    @field_validator("display_name")
    @classmethod
    def nonempty_name(cls, value):
        if not value.strip():
            raise ValueError("Display name must not be blank.")
        return value


class UserPrivate(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    display_name: str
    roles: list[Literal["USER", "ADMIN"]]
    status: Literal["active", "locked", "deleted"]


class CsrfResponse(BaseModel):
    csrf_token: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
