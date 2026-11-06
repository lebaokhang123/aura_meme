"""Owned inventory/equipment and bounded, normalized delivery of approved catalog images."""
from contextlib import ExitStack
from hashlib import sha256
from io import BytesIO
import os
import re
import stat
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from PIL import Image, ImageOps
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError
from sqlalchemy import and_, select

from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import page_rows
from app.blog_schemas import Pagination
from app.config import CatalogSettings, MediaSettings
from app.media import validate_image
from app.models import AssetItem, UserEquipment, UserInventory
from app.permissions import require_account_csrf, require_authenticated_user
from app.security import AuthError
from app.storage import close_handle, windows_handle

router = APIRouter(prefix='/api/v1', tags=['Vault'])
Slot = Literal['avatar', 'frame', 'icon', 'effect']


class Asset(BaseModel):
    id: UUID
    slug: str
    kind: Literal['avatar', 'frame', 'icon', 'effect', 'generator']
    rarity: Literal['D', 'C', 'B', 'A', 'S']
    media_url: AnyHttpUrl


class InventoryItem(BaseModel):
    asset: Asset
    quantity: int = Field(ge=0)
    equipped: bool


class InventoryPage(BaseModel):
    items: list[InventoryItem]
    pagination: Pagination


class EquipmentInput(BaseModel):
    asset_id: UUID | None


class EquipmentResult(BaseModel):
    slot_kind: Slot
    asset_id: UUID | None


def ready_asset(asset):
    return asset is not None and asset.active and asset.source_rights.get('review_status') == 'approved'


def asset_dto(asset, request):
    return Asset(id=asset.id, slug=asset.slug, kind=asset.kind, rarity=asset.rarity,
        media_url=str(request.url_for('catalogAsset', asset_id=asset.id)))


@router.get('/inventory/me', response_model=InventoryPage, operation_id='getInventory', responses=ERRORS)
def inventory(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
              account=Depends(require_authenticated_user, scope='function')):
    query = select(UserInventory, AssetItem, UserEquipment.asset_id).join(AssetItem, AssetItem.id == UserInventory.asset_id).outerjoin(
        UserEquipment, and_(UserEquipment.user_id == UserInventory.user_id, UserEquipment.asset_id == UserInventory.asset_id)).where(
        UserInventory.user_id == account.user.id, UserInventory.quantity > 0, AssetItem.active.is_(True),
        AssetItem.source_rights['review_status'].astext == 'approved').order_by(UserInventory.acquired_at.desc(), AssetItem.id)
    rows, pagination = page_rows(account.db, query, page, page_size)
    return InventoryPage(items=[InventoryItem(asset=asset_dto(asset, request), quantity=item.quantity,
        equipped=equipped is not None) for item, asset, equipped in rows], pagination=pagination)


@router.put('/inventory/equipment/{slot_kind}', response_model=EquipmentResult, operation_id='equipItem',
            responses=ERRORS | {404: {'model': ErrorResponse}, 409: {'model': ErrorResponse}}, openapi_extra=CSRF_HEADER)
def equip(slot_kind: Slot, body: EquipmentInput, request: Request, account=Depends(require_account_csrf)):
    db, owner = account.db, account.user.id  # Auth locks the user, serializing this owner's slot changes.
    if body.asset_id is not None:
        item = db.scalar(select(UserInventory).where(UserInventory.user_id == owner, UserInventory.asset_id == body.asset_id).with_for_update().execution_options(populate_existing=True))
        asset = db.scalar(select(AssetItem).where(AssetItem.id == body.asset_id).with_for_update(read=True).execution_options(populate_existing=True))
        if item is None or item.quantity <= 0 or not ready_asset(asset):
            raise AuthError(404, 'NOT_FOUND', 'Owned active item not found.')
        if asset.kind != slot_kind:
            raise AuthError(409, 'CONFLICT', 'Item does not match this slot.')
    current = db.get(UserEquipment, (owner, slot_kind))
    if body.asset_id is None:
        if current is not None:
            db.delete(current)
    elif current is None:
        db.add(UserEquipment(user_id=owner, slot_kind=slot_kind, asset_id=body.asset_id, equipped_at=request.app.state.auth.now()))
    else:
        current.asset_id, current.equipped_at = body.asset_id, request.app.state.auth.now()
    db.flush()
    return EquipmentResult(slot_kind=slot_kind, asset_id=body.asset_id)


def catalog_png(asset):
    match = re.fullmatch(r'catalog/([a-f0-9]{64})\.(png|jpg|webp)', asset.media_key)
    if not match or match[1] != asset.source_rights.get('sha256'):
        raise ValueError('Unverified catalog key.')
    root = CatalogSettings().catalog_storage_root
    uploads = MediaSettings().media_storage_root
    if root.is_relative_to(uploads) or uploads.is_relative_to(root):
        raise ValueError('Catalog and upload roots must be separate.')
    with ExitStack() as stack:
        for parent in reversed([root, *root.parents]):
            if os.name == 'nt':
                stack.callback(close_handle, windows_handle(parent, directory=True))
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Catalog root links are forbidden.')
        path = root / (match[1] + '.' + match[2])
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Catalog file links are forbidden.')
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as file:
            if os.fstat(file.fileno()).st_nlink != 1:
                raise ValueError('Catalog hard links are forbidden.')
            data = file.read(5 * 1024 * 1024 + 1)
        if sha256(data).hexdigest() != match[1]:
            raise ValueError('Catalog bytes changed.')
        mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'webp': 'image/webp'}[match[2]]
        if mime != asset.source_rights.get('mime'):
            raise ValueError('Catalog MIME changed.')
        validate_image(data, mime)
        with Image.open(BytesIO(data)) as image:
            if getattr(image, 'n_frames', 1) != 1:
                raise ValueError('Animated catalog assets are unsupported.')
            decoded = ImageOps.exif_transpose(image).convert('RGBA')
            clean = Image.frombytes('RGBA', decoded.size, decoded.tobytes())
            out = BytesIO()
            clean.save(out, format='PNG')
            return out.getvalue()


@router.get('/catalog/assets/{asset_id}', operation_id='catalogAsset', name='catalogAsset', response_class=Response,
            responses={200: {'content': {'image/png': {'schema': {'type': 'string', 'format': 'binary'}}}},
                       **{c: {'model': ErrorResponse} for c in (403, 404, 422, 429, 500)}})
def catalog_asset(asset_id: UUID, request: Request):
    with request.app.state.auth_session_factory() as db, db.begin():
        asset = db.scalar(select(AssetItem).where(AssetItem.id == asset_id).with_for_update(read=True))
        if ready_asset(asset):
            try:
                return Response(catalog_png(asset), media_type='image/png', headers={'Content-Security-Policy': "default-src 'none'; sandbox"})
            except (OSError, ValueError, ValidationError, AuthError):
                pass
    raise AuthError(404, 'NOT_FOUND', 'Catalog image not available.')
