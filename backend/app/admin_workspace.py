"""Read-only Admin lists plus safe Admin Catalog upload, preview, and approval workflow."""
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
import re
from typing import Literal
from uuid import UUID, uuid4
import zipfile

from fastapi import APIRouter, Depends, Query, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, ValidationError, field_validator
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from sqlalchemy import case, delete, or_, select, text
from sqlalchemy.orm import undefer
from starlette.requests import ClientDisconnect

from app.admin_users import require_admin_mutation
from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import page_rows
from app.blog_schemas import Pagination, StrictInput
from app.comments import CommentResponse, comment_dto
from app.config import CatalogSettings
from app.inventory import catalog_png
from app.media import image_response, validate_image
from app.models import (
    AdminAuditLog,
    AssetItem,
    CasePoolItem,
    Comment,
    MediaUpload,
    Post,
    Profile,
    SubscriptionOrder,
    User,
    UserEquipment,
    UserInventory,
)
from app.permissions import require_role
from app.security import AuthError
from app.vault_runtime import schema_ready

router = APIRouter(prefix='/api/v1/admin', tags=['Admin'])
ReviewStatus = Literal['pending', 'approved', 'rejected', 'unknown']
AssetKind = Literal['avatar', 'frame', 'icon', 'effect', 'background']
RarityCode = Literal['D', 'C', 'B', 'A', 'S']

FILENAME_PATTERN = re.compile(r'^([DCBAS])_(\d{6})_(\d+)\.(jpg|png)$', re.IGNORECASE)
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_SINGLE_IMAGE_BYTES = 5 * 1024 * 1024
MAX_ZIP_FILES = 50


class AdminComment(CommentResponse):
    status: Literal['visible', 'hidden', 'deleted']


class AdminCommentPage(BaseModel):
    items: list[AdminComment]
    pagination: Pagination


class AdminAsset(BaseModel):
    id: UUID
    slug: str
    display_name: str | None = Field(default=None, exclude_if=lambda value: value is None)
    effect_key: str | None = Field(default=None, exclude_if=lambda value: value is None)
    kind: AssetKind
    rarity: RarityCode
    active: bool
    review_status: ReviewStatus
    filename: str | None = None


class AdminAssetPage(BaseModel):
    items: list[AdminAsset]
    pagination: Pagination


class AdminAssetPatch(StrictInput):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    rarity: RarityCode | None = None
    action: Literal['approve', 'reject', 'archive'] | None = None

    @field_validator('display_name')
    @classmethod
    def nonblank_display_name(cls, value):
        if value is not None and (not value.strip() or '\x00' in value):
            raise ValueError('Display name must not be blank.')
        return value.strip() if isinstance(value, str) else value


class AdminAssetUploadResponse(BaseModel):
    uploaded_count: int
    items: list[AdminAsset]


class AdminOrder(BaseModel):
    id: UUID
    order_code: str
    tier: Literal['plus', 'prime']
    provider: str
    amount_vnd: int
    amount_vnd_formatted: str | None = None
    status: Literal['pending', 'success', 'failed', 'cancelled', 'expired']
    provider_txn_id: str | None = None
    created_at: datetime
    owner_username: str | None = None
    completed_at: datetime | None = None
    amount_usd_cents: int | None = None
    currency: str = 'USD'


class AdminOrderPage(BaseModel):
    items: list[AdminOrder]
    pagination: Pagination


def _admin_asset_dto(asset: AssetItem, *, include_display: bool = True) -> AdminAsset:
    rights = asset.source_rights if isinstance(asset.source_rights, dict) else {}
    rev = rights.get('review_status', 'unknown')
    if rev not in ('pending', 'approved', 'rejected'):
        rev = 'unknown'
    dname = getattr(asset, 'display_name', None) if include_display else None
    ekey = getattr(asset, 'effect_key', None) if include_display else None

    fn = rights.get('uploaded_filename') or rights.get('canonical_filename')
    if not fn:
        ext = 'png' if asset.kind == 'background' or asset.media_key.endswith('.png') else 'jpg'
        if asset.kind == 'background':
            fn = f"{asset.rarity}_background_{asset.effect_key or 'violet_base'}.{ext}"
        else:
            fn = f"{asset.rarity}_{asset.slug.replace('-', '_')}.{ext}"

    return AdminAsset(
        id=asset.id,
        slug=asset.slug,
        display_name=dname,
        effect_key=ekey,
        kind=asset.kind,
        rarity=asset.rarity,
        active=bool(asset.active),
        review_status=rev,
        filename=fn,
    )


def parse_and_validate_meme_filename(filename: str) -> tuple[RarityCode, str, str, str]:
    """Validate filename standard <Rank>_<ddmmyy>_<stt>.<ext> (e.g., S_231126_01.jpg).

    Returns (rank, ddmmyy, stt, ext_lower).
    Raises AuthError(422) with a clear message naming the invalid file if invalid.
    """
    base_name = PurePosixPath(filename.replace('\\', '/')).name
    if not base_name or base_name != filename.replace('\\', '/').split('/')[-1]:
        raise AuthError(422, 'INVALID_FILENAME_FORMAT', f'Tên file không hợp lệ: {filename}. Quy chuẩn: <Rank>_<ddmmyy>_<stt>.jpg|.png (ví dụ: S_231126_01.jpg).')

    lower_name = base_name.lower()
    if lower_name.endswith('.gif') or lower_name.endswith('.svg') or lower_name.endswith('.webp') or lower_name.endswith('.exe'):
        raise AuthError(422, 'UNSUPPORTED_FILE_TYPE', f'Định dạng file không được phép ({base_name}). Chỉ chấp nhận file ảnh tĩnh .jpg, .png hoặc .zip chứa .jpg/.png.')

    m = FILENAME_PATTERN.fullmatch(base_name)
    if not m:
        raise AuthError(
            422,
            'INVALID_FILENAME_FORMAT',
            f'File "{base_name}" sai quy chuẩn đặt tên. Yêu cầu: <Rank>_<ddmmyy>_<stt>.jpg|.png (Rank thuộc D,C,B,A,S; ví dụ: S_231126_01.jpg).',
        )
    rank_raw, ddmmyy, stt, ext_raw = m.group(1).upper(), m.group(2), m.group(3), m.group(4).lower()
    try:
        datetime.strptime(ddmmyy, '%d%m%y')
    except ValueError:
        raise AuthError(
            422,
            'INVALID_FILENAME_DATE',
            f'File "{base_name}" có ngày tháng "{ddmmyy}" không hợp lệ theo định dạng ddmmyy (ví dụ: 231126 cho ngày 23/11/2026).',
        ) from None

    if not stt.isdigit() or int(stt) < 1 or len(stt) > 6:
        raise AuthError(
            422,
            'INVALID_FILENAME_SEQUENCE',
            f'File "{base_name}" có số thứ tự "{stt}" không hợp lệ (ví dụ: 01, 02).',
        )
    return rank_raw, ddmmyy, stt, ext_raw


def _validate_static_meme_bytes(filename: str, data: bytes, ext_lower: str) -> tuple[str, str]:
    """Validate magic bytes, Pillow decode, single frame, and SHA-256 hash."""
    if not 0 < len(data) <= MAX_SINGLE_IMAGE_BYTES:
        raise AuthError(422, 'VALIDATION_ERROR', f'File "{filename}" vượt quá dung lượng tối đa 5MB hoặc rỗng.')
    expected_mime = 'image/jpeg' if ext_lower == 'jpg' else 'image/png'
    # Check magic bytes strictly against extension (no disguised GIF/WebP/EXE)
    if ext_lower == 'jpg' and not data.startswith(b'\xff\xd8\xff'):
        raise AuthError(422, 'VALIDATION_ERROR', f'File "{filename}" có phần mở rộng .jpg nhưng nội dung thực tế không phải ảnh JPEG.')
    if ext_lower == 'png' and not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise AuthError(422, 'VALIDATION_ERROR', f'File "{filename}" có phần mở rộng .png nhưng nội dung thực tế không phải ảnh PNG.')
    try:
        validate_image(data, expected_mime)
        with Image.open(BytesIO(data)) as img:
            if getattr(img, 'n_frames', 1) != 1:
                raise AuthError(422, 'VALIDATION_ERROR', f'File "{filename}" là ảnh động. Bảo Khố chỉ chấp nhận ảnh tĩnh .jpg hoặc .png.')
            img.load()
    except AuthError:
        raise
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        raise AuthError(422, 'VALIDATION_ERROR', f'File "{filename}" bị lỗi cấu trúc ảnh hoặc vượt giới hạn điểm ảnh.') from None
    return sha256(data).hexdigest(), expected_mime


def extract_upload_files(upload_filename: str, raw_bytes: bytes) -> list[tuple[str, RarityCode, str, str, str, bytes, str, str]]:
    """Extract and validate a single .jpg/.png or a .zip of .jpg/.png files.

    Returns list of (base_filename, rank, ddmmyy, stt, ext_lower, data, digest_hex, mime).
    """
    if not upload_filename or '\x00' in upload_filename:
        raise AuthError(422, 'VALIDATION_ERROR', 'Thiếu tên file tải lên.')
    if not 0 < len(raw_bytes) <= MAX_UPLOAD_BYTES:
        raise AuthError(422, 'VALIDATION_ERROR', 'Tổng dung lượng tải lên vượt quá giới hạn 15MB.')

    clean_upload_name = PurePosixPath(upload_filename.replace('\\', '/')).name
    if clean_upload_name.lower().endswith('.zip'):
        if not raw_bytes.startswith(b'PK\x03\x04'):
            raise AuthError(422, 'VALIDATION_ERROR', f'File "{clean_upload_name}" không phải gói nén ZIP hợp lệ.')
        results = []
        seen_hashes: set[str] = set()
        seen_names: set[str] = set()
        try:
            with zipfile.ZipFile(BytesIO(raw_bytes)) as zf:
                infos = zf.infolist()
                if not infos:
                    raise AuthError(422, 'VALIDATION_ERROR', 'File ZIP trống, không chứa ảnh Meme nào.')
                total_uncompressed = 0
                for info in infos:
                    name = info.filename
                    if info.is_dir() or name.startswith('__MACOSX/') or PurePosixPath(name).name.startswith('.'):
                        continue
                    if '\\' in name or ':' in name or name.startswith('/') or '..' in PurePosixPath(name).parts:
                        raise AuthError(422, 'ZIP_PATH_TRAVERSAL', f'Phát hiện đường dẫn không an toàn trong file ZIP: "{name}".')
                    base = PurePosixPath(name).name
                    if base.lower().endswith('.zip'):
                        raise AuthError(422, 'NESTED_ZIP_FORBIDDEN', f'Không cho phép chứa file ZIP lồng nhau ("{base}").')
                    if info.file_size <= 0 or info.file_size > MAX_SINGLE_IMAGE_BYTES:
                        raise AuthError(422, 'VALIDATION_ERROR', f'File "{base}" trong ZIP có kích thước không hợp lệ (tối đa 5MB/ảnh).')
                    total_uncompressed += info.file_size
                    if total_uncompressed > MAX_UPLOAD_BYTES * 2:
                        raise AuthError(422, 'VALIDATION_ERROR', 'Tổng dung lượng giải nén của file ZIP vượt quá ngưỡng an toàn.')
                    rank, ddmmyy, stt, ext_lower = parse_and_validate_meme_filename(base)
                    if base.lower() in seen_names:
                        raise AuthError(422, 'DUPLICATE_FILE_IN_BATCH', f'Trùng tên file "{base}" trong cùng gói ZIP.')
                    seen_names.add(base.lower())
                    file_bytes = zf.read(info)
                    digest_hex, mime = _validate_static_meme_bytes(base, file_bytes, ext_lower)
                    if digest_hex in seen_hashes:
                        raise AuthError(409, 'DUPLICATE_IMAGE_HASH', f'File "{base}" có nội dung ảnh trùng lặp với một file khác trong cùng gói ZIP.')
                    seen_hashes.add(digest_hex)
                    results.append((base, rank, ddmmyy, stt, ext_lower, file_bytes, digest_hex, mime))
                    if len(results) > MAX_ZIP_FILES:
                        raise AuthError(422, 'VALIDATION_ERROR', f'Mỗi gói ZIP chỉ được chứa tối đa {MAX_ZIP_FILES} ảnh.')
        except zipfile.BadZipFile:
            raise AuthError(422, 'VALIDATION_ERROR', 'File ZIP bị hỏng hoặc không đúng định dạng.') from None
        if not results:
            raise AuthError(422, 'VALIDATION_ERROR', 'File ZIP không chứa ảnh .jpg hoặc .png hợp lệ nào.')
        return results

    rank, ddmmyy, stt, ext_lower = parse_and_validate_meme_filename(clean_upload_name)
    digest_hex, mime = _validate_static_meme_bytes(clean_upload_name, raw_bytes, ext_lower)
    return [(clean_upload_name, rank, ddmmyy, stt, ext_lower, raw_bytes, digest_hex, mime)]


async def _receive_admin_upload_multipart(request: Request) -> tuple[str, bytes]:
    content_type = request.headers.get('content-type', '')
    if len(content_type) > 1024:
        raise AuthError(422, 'VALIDATION_ERROR', 'Multipart Content-Type too large.')
    kind, options = parse_options_header(content_type)
    boundary = options.get(b'boundary', b'')
    if kind != b'multipart/form-data' or not 1 <= len(boundary) <= 200:
        raise AuthError(422, 'VALIDATION_ERROR', 'Expected multipart/form-data with one file field.')

    payload, field, value = bytearray(), bytearray(), bytearray()
    headers: dict[bytes, bytes] = {}
    parts, header_bytes, total = 0, 0, 0
    finished = False
    filename = ''

    def on_part_begin():
        nonlocal parts
        parts += 1
        if parts > 1:
            raise AuthError(422, 'VALIDATION_ERROR', 'Chỉ được gửi 1 trường file trong mỗi lượt tải lên.')

    def header_data(target, data, start, end):
        nonlocal header_bytes
        header_bytes += end - start
        if header_bytes > 8192:
            raise AuthError(422, 'VALIDATION_ERROR', 'Multipart headers too large.')
        target.extend(data[start:end])

    def on_header_end():
        name = bytes(field).lower()
        headers[name] = bytes(value)
        field.clear()
        value.clear()

    def on_headers_finished():
        nonlocal filename
        disposition, attributes = parse_options_header(headers.get(b'content-disposition', b''))
        raw_fn = attributes.get(b'filename', b'')
        if disposition != b'form-data' or attributes.get(b'name') != b'file' or not raw_fn:
            raise AuthError(422, 'VALIDATION_ERROR', 'Thiếu trường file tải lên.')
        filename = raw_fn.decode('utf-8', errors='replace')

    def on_part_data(data, start, end):
        if len(payload) + end - start > MAX_UPLOAD_BYTES:
            raise AuthError(422, 'VALIDATION_ERROR', 'File tải lên vượt quá 15MB.')
        payload.extend(data[start:end])

    def on_end():
        nonlocal finished
        finished = True

    parser = MultipartParser(
        boundary,
        {
            'on_part_begin': on_part_begin,
            'on_header_field': lambda data, start, end: header_data(field, data, start, end),
            'on_header_value': lambda data, start, end: header_data(value, data, start, end),
            'on_header_end': on_header_end,
            'on_headers_finished': on_headers_finished,
            'on_part_data': on_part_data,
            'on_end': on_end,
        },
    )
    try:
        async for chunk in request.stream():
            for offset in range(0, len(chunk), 65536):
                piece = chunk[offset : offset + 65536]
                total += len(piece)
                parser.write(piece)
                if total - len(payload) > 128 * 1024:
                    raise AuthError(422, 'VALIDATION_ERROR', 'Multipart overhead too large.')
        parser.finalize()
    except (MultipartParseError, ClientDisconnect):
        raise AuthError(422, 'VALIDATION_ERROR', 'Dữ liệu multipart tải lên bị gián đoạn hoặc không hợp lệ.') from None
    if not finished or parts != 1:
        raise AuthError(422, 'VALIDATION_ERROR', 'Tải lên chưa hoàn tất.')
    return filename, bytes(payload)


@router.get('/comments', response_model=AdminCommentPage, operation_id='adminListComments', responses={s: ERRORS[s] for s in (401, 403, 422, 429, 500)})
def comments(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    status: Literal['visible', 'hidden', 'deleted'] | None = None,
    post_id: UUID | None = None,
    account=Depends(require_role('ADMIN')),
):
    if search is not None and '\x00' in search:
        raise AuthError(422, 'VALIDATION_ERROR', 'Invalid query text.')
    statement = select(Comment, User, Profile).join(User, User.id == Comment.author_id).join(Profile, Profile.user_id == User.id)
    if search is not None:
        statement = statement.where(Comment.body.icontains(search, autoescape=True))
    if status is not None:
        statement = statement.where(Comment.status == status)
    if post_id is not None:
        statement = statement.where(Comment.post_id == post_id)
    rows, pagination = page_rows(account.db, statement.order_by(Comment.created_at.desc(), Comment.id.desc()), page, page_size)
    return AdminCommentPage(items=[AdminComment(**comment_dto(*row).model_dump(), status=row[0].status) for row in rows], pagination=pagination)


@router.get('/assets', response_model=AdminAssetPage, operation_id='adminListAssets', responses={s: ERRORS[s] for s in (401, 403, 422, 429, 500)})
def assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    kind: AssetKind | None = None,
    rarity: RarityCode | None = None,
    active: bool | None = None,
    review_status: ReviewStatus | None = None,
    account=Depends(require_role('ADMIN')),
):
    if search is not None and '\x00' in search:
        raise AuthError(422, 'VALIDATION_ERROR', 'Invalid query text.')
    saved_review = AssetItem.source_rights['review_status'].astext
    reviewed = case((saved_review.in_(['pending', 'approved', 'rejected']), saved_review), else_='unknown')
    has_v1_cols = schema_ready(account.db)
    if has_v1_cols:
        statement = select(
            AssetItem.id,
            AssetItem.slug,
            AssetItem.display_name,
            AssetItem.effect_key,
            AssetItem.kind,
            AssetItem.rarity,
            AssetItem.active,
            reviewed.label('review_status'),
        )
        if search is not None:
            statement = statement.where(
                or_(
                    AssetItem.slug.icontains(search, autoescape=True),
                    AssetItem.display_name.icontains(search, autoescape=True),
                )
            )
    else:
        statement = select(
            AssetItem.id,
            AssetItem.slug,
            AssetItem.kind,
            AssetItem.rarity,
            AssetItem.active,
            reviewed.label('review_status'),
        )
        if search is not None:
            statement = statement.where(AssetItem.slug.icontains(search, autoescape=True))
    if kind is not None:
        statement = statement.where(AssetItem.kind == kind)
    if rarity is not None:
        statement = statement.where(AssetItem.rarity == rarity)
    if active is not None:
        statement = statement.where(AssetItem.active == active)
    if review_status is not None:
        statement = statement.where(reviewed == review_status)
    rows, pagination = page_rows(account.db, statement.order_by(AssetItem.created_at.desc(), AssetItem.slug, AssetItem.id), page, page_size)
    return AdminAssetPage(items=[AdminAsset(**row._mapping) for row in rows], pagination=pagination)


@router.get(
    '/assets/{asset_id}/media',
    response_class=Response,
    operation_id='adminReadAssetImage',
    responses={
        200: {'content': {'image/png': {'schema': {'type': 'string', 'format': 'binary'}}}},
        **{s: ERRORS[s] for s in (401, 403, 422, 429, 500)},
        404: {'model': ErrorResponse},
    },
)
def admin_asset_image(asset_id: UUID, account=Depends(require_role('ADMIN'))):
    asset = account.db.scalar(select(AssetItem).where(AssetItem.id == asset_id).with_for_update(read=True))
    if asset is None or asset.kind == 'background':
        raise AuthError(404, 'NOT_FOUND', 'Asset image not available.')
    try:
        png_bytes = catalog_png(asset)
        return Response(
            png_bytes,
            media_type='image/png',
            headers={
                'Cache-Control': 'no-store',
                'X-Content-Type-Options': 'nosniff',
                'Content-Security-Policy': "default-src 'none'; sandbox",
            },
        )
    except (OSError, ValueError, ValidationError, AuthError):
        raise AuthError(404, 'NOT_FOUND', 'Asset image not available.') from None


@router.post(
    '/assets/upload',
    status_code=201,
    response_model=AdminAssetUploadResponse,
    operation_id='adminUploadAssets',
    responses=ERRORS,
    openapi_extra=CSRF_HEADER,
)
async def admin_upload_assets(request: Request, account=Depends(require_admin_mutation, scope='function')):
    upload_filename, raw_bytes = await _receive_admin_upload_multipart(request)
    extracted = extract_upload_files(upload_filename, raw_bytes)

    db = account.db
    now = request.app.state.auth.now()
    db.execute(text('LOCK TABLE asset_items IN SHARE ROW EXCLUSIVE MODE'))

    # Check duplicate hashes in DB before writing files
    for base_name, _, _, _, _, _, digest_hex, _ in extracted:
        existing_id = db.scalar(select(AssetItem.id).where(AssetItem.source_rights['sha256'].astext == digest_hex))
        if existing_id is not None:
            raise AuthError(409, 'DUPLICATE_IMAGE_HASH', f'Ảnh "{base_name}" đã tồn tại trong danh mục Bảo Khố.')

    root = CatalogSettings().catalog_storage_root
    root.mkdir(parents=True, exist_ok=True)

    created_items: list[AdminAsset] = []
    has_v1 = schema_ready(db)

    for base_name, rank, ddmmyy, stt, ext_lower, file_bytes, digest_hex, mime in extracted:
        storage_filename = f'{digest_hex}.{ext_lower}'
        target_path = root / storage_filename
        if not target_path.exists():
            target_path.write_bytes(file_bytes)

        asset_id = uuid4()
        display_name = f'{ddmmyy}_{stt}'
        base_slug = f'meme-{rank.lower()}-{ddmmyy}-{stt}'.lower()
        slug = base_slug
        if db.scalar(select(AssetItem.id).where(AssetItem.slug == slug)) is not None:
            slug = f'{base_slug}-{str(asset_id)[:8]}'

        evidence_seed = f'admin-upload:{account.user.id}:{asset_id}:{digest_hex}'.encode('utf-8')
        evidence_sha = sha256(evidence_seed).hexdigest()
        rights = {
            'source': 'Owner-collected internet memes; original source and author unverified',
            'author': 'Unidentified original meme creators',
            'license': 'LicenseRef-Owner-Private-Demo-Only',
            'attribution': 'Private demo only; Unidentified original meme creators; no rights verification',
            'review_status': 'pending',
            'name_review_status': 'pending',
            'sha256': digest_hex,
            'mime': mime,
            'uploaded_filename': base_name,
            'uploaded_by': str(account.user.id),
            'proof': {
                'basis': 'owner_private_demo',
                'source': 'Owner-collected internet memes; original source and author unverified',
                'license_id': 'LicenseRef-Owner-Private-Demo-Only',
                'license_url': f'aurameme://private-demo/owner-statement/{evidence_sha}',
                'artifact_sha256': digest_hex,
                'evidence_sha256': evidence_sha,
                'copyright_notice': 'Unidentified original meme creators; no rights verification',
            },
        }

        item = AssetItem(
            id=asset_id,
            slug=slug,
            kind='avatar',
            collection='admin-upload',
            rarity=rank,
            media_key=f'catalog/{storage_filename}',
            display_name=display_name,
            effect_key=None,
            source_rights=rights,
            active=False,
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        db.flush()
        db.add(
            AdminAuditLog(
                id=uuid4(),
                actor_id=account.user.id,
                action='asset.upload',
                target_type='asset',
                target_id=str(item.id),
                before_json=None,
                after_json={
                    'slug': item.slug,
                    'display_name': display_name,
                    'kind': 'avatar',
                    'rarity': rank,
                    'review_status': 'pending',
                    'active': False,
                    'filename': base_name,
                },
                created_at=now,
            )
        )
        db.flush()
        created_items.append(_admin_asset_dto(item, include_display=has_v1))

    return AdminAssetUploadResponse(uploaded_count=len(created_items), items=created_items)


@router.patch(
    '/assets/{asset_id}',
    response_model=AdminAsset,
    operation_id='adminUpdateAsset',
    responses=ERRORS | {404: {'model': ErrorResponse}},
    openapi_extra=CSRF_HEADER,
)
def admin_update_asset(
    asset_id: UUID,
    payload: AdminAssetPatch,
    request: Request,
    account=Depends(require_admin_mutation, scope='function'),
):
    db = account.db
    has_v1 = schema_ready(db)
    stmt = select(AssetItem).where(AssetItem.id == asset_id).with_for_update().execution_options(populate_existing=True)
    if has_v1:
        stmt = stmt.options(undefer(AssetItem.display_name), undefer(AssetItem.effect_key))
    asset = db.scalar(stmt)
    if asset is None:
        raise AuthError(404, 'NOT_FOUND', 'Asset not found.')

    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise AuthError(422, 'VALIDATION_ERROR', 'At least one change is required.')

    now = request.app.state.auth.now()
    rights = dict(asset.source_rights or {})
    old_review = rights.get('review_status', 'unknown')
    before = {
        'display_name': getattr(asset, 'display_name', None) if has_v1 else asset.slug,
        'rarity': asset.rarity,
        'review_status': old_review,
        'active': asset.active,
    }

    if 'display_name' in values and values['display_name'] is not None:
        if has_v1:
            asset.display_name = values['display_name']
        else:
            asset.slug = values['display_name'].lower().replace('_', '-')

    if 'rarity' in values and values['rarity'] is not None and values['rarity'] != asset.rarity:
        if asset.kind == 'background':
            raise AuthError(409, 'CONFLICT', 'Không thể thay đổi hạng của Background hệ thống.')
        new_rarity = values['rarity']
        pool_refs = list(db.scalars(select(CasePoolItem).where(CasePoolItem.asset_id == asset.id).with_for_update()))
        for pool_ref in pool_refs:
            from sqlalchemy import func
            rem_count = db.scalar(
                select(func.count(CasePoolItem.asset_id)).where(
                    CasePoolItem.loot_table_id == pool_ref.loot_table_id,
                    CasePoolItem.rarity == asset.rarity,
                    CasePoolItem.asset_id != asset.id,
                )
            )
            if rem_count == 0:
                raise AuthError(409, 'CONFLICT', f'Không thể đổi hạng: bậc {asset.rarity} trong rương sẽ bị rỗng.')
        for pool_ref in pool_refs:
            db.delete(pool_ref)
        db.flush()
        asset.rarity = new_rarity
        db.flush()
        for pool_ref in pool_refs:
            db.add(
                CasePoolItem(
                    loot_table_id=pool_ref.loot_table_id,
                    asset_id=asset.id,
                    rarity=new_rarity,
                    item_weight=pool_ref.item_weight,
                )
            )

    action = values.get('action')
    audit_action = 'asset.update'
    if action == 'approve':
        if asset.kind == 'background':
            raise AuthError(409, 'CONFLICT', 'Background hệ thống đã được cấu hình cố định.')
        rights['review_status'] = 'approved'
        rights['name_review_status'] = 'approved'
        asset.source_rights = rights
        asset.active = True
        audit_action = 'asset.approve'
    elif action == 'reject':
        if asset.kind == 'background':
            raise AuthError(409, 'CONFLICT', 'Không thể từ chối hoặc xóa Background gốc của hệ thống.')
        rights['review_status'] = 'rejected'
        asset.source_rights = rights
        asset.active = False
        db.execute(delete(UserEquipment).where(UserEquipment.asset_id == asset.id))
        db.execute(delete(CasePoolItem).where(CasePoolItem.asset_id == asset.id))
        audit_action = 'asset.reject'
    elif action == 'archive':
        if asset.kind == 'background':
            raise AuthError(409, 'CONFLICT', '5 Background gốc của hệ thống được bảo vệ và không thể xóa.')
        if asset.collection != 'admin-upload' and old_review == 'approved':
            raise AuthError(409, 'CONFLICT', '70 Meme gốc của Bảo Khố MVP được bảo vệ và không thể xóa.')
        rights['review_status'] = 'rejected'
        asset.source_rights = rights
        asset.active = False
        db.execute(delete(UserEquipment).where(UserEquipment.asset_id == asset.id))
        db.execute(delete(CasePoolItem).where(CasePoolItem.asset_id == asset.id))
        audit_action = 'asset.archive'

    asset.updated_at = now
    db.flush()

    after = {
        'display_name': getattr(asset, 'display_name', None) if has_v1 else asset.slug,
        'rarity': asset.rarity,
        'review_status': asset.source_rights.get('review_status', 'unknown'),
        'active': asset.active,
    }
    db.add(
        AdminAuditLog(
            id=uuid4(),
            actor_id=account.user.id,
            action=audit_action,
            target_type='asset',
            target_id=str(asset.id),
            before_json=before,
            after_json=after,
            created_at=now,
        )
    )
    db.flush()
    return _admin_asset_dto(asset, include_display=has_v1)


@router.get(
    '/posts/{post_id}/media',
    response_class=Response,
    operation_id='adminReadPostImage',
    responses={
        200: {'content': {mime: {'schema': {'type': 'string', 'format': 'binary'}} for mime in ('image/png', 'image/gif')}},
        **{s: ERRORS[s] for s in (401, 403, 422, 429, 500)},
        404: {'model': ErrorResponse},
    },
)
def post_image(post_id: UUID, still: bool = False, account=Depends(require_role('ADMIN'))):
    post = account.db.scalar(select(Post).where(Post.id == post_id).with_for_update(read=True))
    if post is None or post.status == 'deleted' or post.media_id is None:
        raise AuthError(404, 'NOT_FOUND', 'Image not available.')
    # Bind this privileged read to a post; unrelated private uploads remain inaccessible.
    media = account.db.scalar(
        select(MediaUpload)
        .where(MediaUpload.id == post.media_id, MediaUpload.owner_id == post.author_id, MediaUpload.status == 'ready')
        .with_for_update(read=True)
    )
    if media is None:
        raise AuthError(404, 'NOT_FOUND', 'Image not available.')
    return image_response(media, still=still)


@router.get('/orders', response_model=AdminOrderPage, operation_id='adminListOrders', responses={s: ERRORS[s] for s in (401, 403, 422, 429, 500)})
def orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Literal['pending', 'success', 'failed', 'cancelled', 'expired'] | None = None,
    search: str | None = Query(None, max_length=100),
    account=Depends(require_role('ADMIN')),
):
    if search is not None and '\x00' in search:
        raise AuthError(422, 'VALIDATION_ERROR', 'Invalid query text.')
    statement = select(SubscriptionOrder, User.username).join(User, User.id == SubscriptionOrder.user_id)
    if status is not None:
        statement = statement.where(SubscriptionOrder.status == status)
    if search:
        statement = statement.where(SubscriptionOrder.order_code.icontains(search, autoescape=True))
    rows, pagination = page_rows(
        account.db,
        statement.order_by(SubscriptionOrder.created_at.desc(), SubscriptionOrder.id.desc()),
        page,
        page_size,
    )
    try:
        return AdminOrderPage(
            items=[
                AdminOrder(
                    id=o.id,
                    order_code=o.order_code,
                    tier=o.tier,
                    provider=o.provider,
                    amount_vnd=o.amount_vnd,
                    amount_vnd_formatted=f'{o.amount_vnd:,} đ'.replace(',', '.'),
                    amount_usd_cents=o.amount_cents,
                    currency=o.currency,
                    owner_username=username,
                    status=o.status,
                    provider_txn_id=o.provider_txn_id,
                    created_at=o.created_at,
                    completed_at=o.completed_at,
                )
                for o, username in rows
            ],
            pagination=pagination,
        )
    except ValidationError as exc:
        raise AuthError(500, 'INTERNAL_ERROR', 'Invalid transaction data.') from exc


@router.get(
    '/orders/{order_id}/receipt.pdf',
    response_class=Response,
    operation_id='adminReadOrderReceiptPdf',
    responses={
        200: {'content': {'application/pdf': {'schema': {'type': 'string', 'format': 'binary'}}}},
        404: {'model': ErrorResponse},
        **{s: ERRORS[s] for s in (401, 403, 409, 422, 500)},
    },
)
def admin_read_order_receipt_pdf(
    order_id: UUID,
    download: bool = Query(False),
    format: Literal['pdf', 'png'] = 'pdf',
    account=Depends(require_role('ADMIN')),
):
    db = account.db
    order = db.scalar(select(SubscriptionOrder).where(SubscriptionOrder.id == order_id))
    if order is None:
        raise AuthError(404, 'NOT_FOUND', 'Order not found.')
    if order.status != 'success':
        raise AuthError(409, 'CONFLICT', 'Receipt is only available for successful orders.')

    owner_user = db.scalar(select(User).where(User.id == order.user_id))
    username = owner_user.username if owner_user else 'user'

    from app.receipt_pdf import generate_receipt_pdf_bytes

    order_dict = {
        'id': str(order.id),
        'order_code': order.order_code,
        'tier': order.tier,
        'provider': order.provider,
        'amount_vnd': order.amount_vnd,
        'amount_vnd_formatted': f'{order.amount_vnd:,} đ'.replace(',', '.'),
        'amount_usd_cents': order.amount_cents,
        'currency': order.currency,
        'status': order.status,
        'provider_txn_id': order.provider_txn_id,
        'created_at': order.created_at,
        'completed_at': order.completed_at,
        'duration_days': order.duration_days,
    }

    recent = list(db.scalars(
        select(SubscriptionOrder)
        .where(
            SubscriptionOrder.user_id == order.user_id,
            SubscriptionOrder.status == 'success',
            SubscriptionOrder.id != order.id,
        )
        .order_by(SubscriptionOrder.created_at.desc())
        .limit(10)
    ))
    recent_dicts = [
        {
            'order_code': r.order_code,
            'tier': r.tier,
            'provider': r.provider,
            'amount_vnd': r.amount_vnd,
            'amount_vnd_formatted': f'{r.amount_vnd:,} đ'.replace(',', '.'),
            'amount_usd_cents': r.amount_cents,
            'currency': r.currency,
            'status': r.status,
            'created_at': r.created_at,
            'completed_at': r.completed_at,
        }
        for r in recent
    ]

    pdf_bytes = generate_receipt_pdf_bytes(order_dict, username=username, recent_successful_orders=recent_dicts)
    if not pdf_bytes:
        raise AuthError(500, 'RENDER_ERROR', 'Unable to generate receipt PDF.')

    if format == 'png':
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=180)
        png_bytes = pix.tobytes('png')
        return Response(
            content=png_bytes,
            media_type='image/png',
            headers={
                'Cache-Control': 'no-store, must-revalidate',
                'X-Content-Type-Options': 'nosniff',
            },
        )

    disposition = f'attachment; filename="AuraMeme-Receipt-{order.order_code}.pdf"' if download else 'inline'
    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={
            'Content-Disposition': disposition,
            'Cache-Control': 'no-store, must-revalidate',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'SAMEORIGIN',
        },
    )
