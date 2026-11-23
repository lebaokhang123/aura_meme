"""Public identity and private account field allowlists."""
from datetime import datetime
from typing import Literal
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
    # Server-authorized special cosmetic title only; omitted for standard accounts.
    title: str | None = Field(default=None, exclude_if=lambda value: value is None)


class UserPublic(BaseModel):
    id: UUID
    username: str
    display_name: str
    created_at: datetime
    bio: str | None = None
    avatar_url: str | None = Field(default=None, json_schema_extra={"format": "uri-reference"})
    level: StrictInt | None = Field(default=None, ge=1, le=100, exclude_if=lambda value: value is None)
    # Derived only from the validated public level with the reviewed Aura V1 mapping; never client input.
    realm: str | None = Field(default=None, exclude_if=lambda value: value is None)
    title: str | None = Field(default=None, exclude_if=lambda value: value is None)
    membership_tier: Literal["free", "plus", "prime"] = "free"
    # Internal server-verified flag (from DB Role.code == "ADMIN"); never serialized to public JSON.
    is_admin_title: bool = Field(default=False, exclude=True)

    @model_validator(mode="after")
    def public_identity(self):
        from app.aura_v1 import public_title_for_user
        self.realm, self.title = public_title_for_user(self.level, is_admin=bool(self.is_admin_title))
        return self


class PublicProfile(UserPublic):
    equipped_background_effect: str | None = Field(default=None, exclude_if=lambda value: value is None)



class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"minProperties": 1})
    # Omission is allowed; explicit null still fails the non-nullable string type.
    display_name: str = Field(default=None, min_length=1, max_length=25)
    bio: str | None = Field(default=None, max_length=100)
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
        if value is not None:
            stripped = value.strip()
            if not stripped:
                raise ValueError("Tên hiển thị không được để trống hoặc chỉ có khoảng trắng.")
            if len(stripped) > 25:
                raise ValueError("Tên hiển thị không được vượt quá 25 ký tự.")
            return stripped
        return value

    @field_validator("bio")
    @classmethod
    def valid_bio(cls, value):
        if value is not None:
            stripped = value.strip()
            if len(stripped) > 100:
                raise ValueError("Tiểu sử không được vượt quá 100 ký tự.")
            return stripped or None
        return value

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
