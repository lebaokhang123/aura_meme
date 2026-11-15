"""Public identity and private account field allowlists."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictInt, field_validator, model_validator

from app.auth_schemas import LoginInput, RegisterInput, UserPrivate


class AccountPrivate(UserPrivate):
    birth_year: int | None = None
    address: str | None = None
    phone: str | None = None
    bio: str | None = None
    avatar_media_id: UUID | None = None
    cover_media_id: UUID | None = None
    avatar_url: str | None = Field(default=None, json_schema_extra={"format": "uri-reference"})
    cover_url: str | None = Field(default=None, json_schema_extra={"format": "uri-reference"})


class UserPublic(BaseModel):
    id: UUID
    username: str
    display_name: str
    created_at: datetime
    bio: str | None = None
    avatar_url: str | None = Field(default=None, json_schema_extra={"format": "uri-reference"})


class PublicProfile(UserPublic):
    pass


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"minProperties": 1})
    # Omission is allowed; explicit null still fails the non-nullable string type.
    display_name: str = Field(default=None, min_length=1, max_length=80)
    bio: str | None = Field(default=None, max_length=1000)
    birth_year: StrictInt | None = Field(default=None, ge=1900, le=9999)
    address: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    avatar_media_id: UUID | None = None
    cover_media_id: UUID | None = None

    @field_validator("display_name", "bio", "address", "phone")
    @classmethod
    def valid_text(cls, value):
        if value is not None:
            value.encode("utf-8")
            if "\x00" in value:
                raise ValueError("NUL is not valid profile text.")
        return value

    @field_validator("display_name")
    @classmethod
    def nonempty_name(cls, value):
        return RegisterInput.nonempty_name(value)

    @model_validator(mode="after")
    def nonempty_patch(self):
        if "cover_media_id" in self.model_fields_set:
            raise ValueError("Cover changes are no longer supported.")
        if self.avatar_media_id is not None:
            raise ValueError("Choose an owned avatar through inventory equipment.")
        if not self.model_fields_set:
            raise ValueError("Provide at least one profile field.")
        return self


class PasswordChange(BaseModel):
    current_password: SecretStr
    new_password: SecretStr = Field(json_schema_extra={"minLength": 12, "maxLength": 128})

    @field_validator("current_password", "new_password")
    @classmethod
    def valid_encoding(cls, value):
        return LoginInput.valid_password_encoding(value)

    @field_validator("new_password")
    @classmethod
    def valid_length(cls, value):
        return RegisterInput.password_length(value)
