"""P0 category/post DTOs and strict input allowlists."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator, model_validator
from app.account_schemas import UserPublic


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*")
    @classmethod
    def valid_text(cls, value, info):
        if isinstance(value, str):
            value.encode("utf-8")
            if "\x00" in value or (info.field_name in {"name", "title"} and not value.strip()):
                raise ValueError("Invalid or empty text.")
        return value


class NonemptyPatch(StrictInput):
    model_config = ConfigDict(json_schema_extra={"minProperties": 1})

    @model_validator(mode="after")
    def has_fields(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field.")
        return self


class CategoryInput(StrictInput):
    name: str = Field(min_length=1, max_length=80)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")


class CategoryPatch(NonemptyPatch):
    name: str = Field(default=None, min_length=1, max_length=80)
    status: Literal["active", "hidden"] = None


class PostInput(StrictInput):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(max_length=20000)
    category_id: UUID
    media_id: UUID | None = None
    status: Literal["draft", "published"] = "draft"


class PostPatch(NonemptyPatch):
    title: str = Field(default=None, min_length=1, max_length=160)
    content: str = Field(default=None, max_length=20000)
    category_id: UUID = None
    media_id: UUID | None = None
    status: Literal["draft", "published"] = None


class CategoryResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    status: Literal["active", "hidden"]


class PostResponse(BaseModel):
    id: UUID
    author: UserPublic
    category: CategoryResponse
    title: str
    content: str
    media_url: AnyUrl | None = None
    status: Literal["draft", "published", "hidden", "deleted"]
    created_at: datetime
    updated_at: datetime


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class CategoryPage(BaseModel):
    items: list[CategoryResponse]
    pagination: Pagination


class PostPage(BaseModel):
    items: list[PostResponse]
    pagination: Pagination
