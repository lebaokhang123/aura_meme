"""Free Vault V1 policy; no RNG seeds, economics or user-controlled policy switches."""
from datetime import timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

WEIGHTS = (6890, 2000, 1000, 100, 10)
EFFECT_KEYS = ('violet-base', 'lucian-363', 'lucian-352-deep-sea', 'lucian-226', 'lucian-330')


class FreeVaultPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    type: Literal['free-vault-v1']
    duplicate_mode: Literal['quantity'] = 'quantity'
    catalog_manifest_sha256: Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')] | None = None


def next_open_at(latest, successful_count):
    if successful_count < 0 or (successful_count == 0) != (latest is None):
        raise ValueError('Inconsistent successful opening history.')
    return latest + timedelta(seconds=5 if successful_count % 10 == 0 else 2) if latest else None
