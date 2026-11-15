"""Shared catalog asset response used by inventory and owned Meme reactions."""
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel


class Asset(BaseModel):
    id: UUID
    slug: str
    kind: Literal['avatar', 'frame', 'icon', 'effect', 'generator', 'background']
    rarity: Literal['D', 'C', 'B', 'A', 'S']
    media_url: AnyHttpUrl | None
    display_name: str = ''
    effect_key: str | None = None
    available: bool = True
