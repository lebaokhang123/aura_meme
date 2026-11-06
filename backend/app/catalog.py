"""Validate local manifest packages and import inactive drafts on the isolated test DB only."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal
from uuid import UUID

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import or_, select, text

from app.aura import simulation_only
from app.models import AssetItem

Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class Rights(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    source: Nonempty
    author: Nonempty
    license: Nonempty
    attribution: Nonempty
    review_status: Literal['pending', 'rejected']


class CatalogItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    slug: str = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=100)
    kind: Literal['avatar', 'frame', 'icon', 'effect']
    collection: Nonempty
    rarity: Literal['D', 'C', 'B', 'A', 'S']
    file: str = Field(min_length=1, max_length=240)
    mime: Literal['image/png', 'image/jpeg', 'image/webp']
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_rights: Rights


class CatalogManifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(strict=True, ge=1)
    items: list[CatalogItem] = Field(min_length=1, max_length=1000)


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key in catalog.')
        result[key] = value
    return result


def read_manifest(path):
    path = Path(path)
    if path.is_symlink() or path.is_junction() or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Catalog must be a bounded regular local JSON file.')
    manifest = CatalogManifest.model_validate(json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_keys))
    for field in ('id', 'slug', 'sha256'):
        if len({getattr(item, field) for item in manifest.items}) != len(manifest.items):
            raise ValueError('Duplicate catalog identity or content hash.')
    root = path.parent.resolve()
    for item in manifest.items:
        relative = PurePosixPath(item.file)
        if relative.is_absolute() or '\\' in item.file or ':' in item.file or any(p in {'..', '.'} for p in item.file.split('/')):
            raise ValueError('Catalog file must stay inside its package.')
        file = root.joinpath(*relative.parts)
        if any(p.is_symlink() or p.is_junction() for p in [file, *file.parents] if p == root or root in p.parents):
            raise ValueError('Catalog file links are forbidden.')
        if not file.is_file() or file.stat().st_nlink != 1 or not file.resolve().is_relative_to(root) or not 0 < file.stat().st_size <= 5 * 1024 * 1024:
            raise ValueError('Catalog image is missing, outside package or oversized.')
        data = file.read_bytes()
        if len(data) > 5 * 1024 * 1024 or sha256(data).hexdigest() != item.sha256:
            raise ValueError('Catalog content checksum mismatch.')
        try:
            with Image.open(BytesIO(data)) as image:
                if Image.MIME.get(image.format) != item.mime or image.width * image.height > 12_000_000 or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('Catalog image MIME, dimensions or animation is unsupported.')
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise ValueError('Catalog file is not a supported image.') from error
    return manifest


def import_draft(db, manifest, now):
    now = simulation_only(db, now)
    manifest = CatalogManifest.model_validate(manifest.model_dump())
    digest = sha256(manifest.model_dump_json().encode()).hexdigest()
    added = 0
    with db.begin_nested():
        # Serialize imports before checking IDs/slugs/content hashes across manifests.
        db.execute(text('LOCK TABLE asset_items IN SHARE ROW EXCLUSIVE MODE'))
        for item in manifest.items:
            rights = item.source_rights.model_dump() | {'sha256': item.sha256, 'mime': item.mime}
            key = 'catalog/' + item.sha256 + {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[item.mime]
            existing = db.scalar(select(AssetItem).where(or_(AssetItem.id == item.id, AssetItem.slug == item.slug)).execution_options(populate_existing=True))
            if existing is not None:
                saved = {k: v for k, v in existing.source_rights.items() if k not in {'catalog_version', 'manifest_sha256'}}
                if ((existing.id, existing.slug, existing.kind, existing.collection, existing.rarity, existing.media_key) !=
                    (item.id, item.slug, item.kind, item.collection, item.rarity, key) or saved != rights):
                    raise ValueError('Conflicting existing catalog identity; never overwrite.')
                continue
            if db.scalar(select(AssetItem.id).where(AssetItem.source_rights['sha256'].astext == item.sha256)) is not None:
                raise ValueError('Duplicate content hash across catalog manifests.')
            db.add(AssetItem(id=item.id, slug=item.slug, kind=item.kind, collection=item.collection, rarity=item.rarity,
                media_key=key, source_rights=rights | {'catalog_version': manifest.version, 'manifest_sha256': digest},
                active=False, created_at=now, updated_at=now))
            db.flush()
            added += 1
    return added


def main():
    parser = argparse.ArgumentParser(description='Validate catalog package; never activate assets or publish bytes.')
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        manifest = read_manifest(args.manifest)
    except (ValueError, OSError):
        parser.exit(1, 'Catalog validation failed; inspect local package metadata and bytes.\n')
    print(f'Catalog v{manifest.version}: {len(manifest.items)} draft assets validated; no database/files changed.')


if __name__ == '__main__':
    main()
