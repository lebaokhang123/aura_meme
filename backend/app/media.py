"""Private image uploads and authorized, bounded, metadata-free display."""
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from io import BytesIO
import logging
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from sqlalchemy.exc import DBAPIError
from sqlalchemy import or_, select
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from app.auth import CSRF_HEADER, ERRORS, current_session, session_cookie
from app.auth_schemas import ErrorResponse
from app.config import MediaSettings
from app.models import AuthSession, MediaUpload, Post, Profile, User
from app.permissions import AuthenticatedAccount, require_account_csrf, require_authenticated_user
from app.security import AuthError, TOKEN, digest
from app.storage import LocalObject, read_private_object


MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_OVERHEAD = 64 * 1024
MAX_REQUEST_BYTES = MAX_FILE_BYTES + MAX_OVERHEAD
MAX_PIXELS = 12_000_000
MAX_FRAMES = 60
MAX_TOTAL_PIXELS = 40_000_000
MAX_DELIVERY_BYTES = 80 * 1024 * 1024
FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"),
           "WEBP": ("image/webp", "webp"), "GIF": ("image/gif", "gif")}
logger = logging.getLogger(__name__)
router = APIRouter()


def media_url(ident):
    return '/api/v1/media/' + str(ident) if ident is not None else None


class ImageOutput(BytesIO):
    def write(self, data):
        # The decoded pixel budget bounds normalized output; stop before an oversized allocation.
        if self.tell() + len(data) > MAX_DELIVERY_BYTES:
            raise ValueError('Normalized image exceeds delivery budget.')
        return super().write(data)


def normalize_image(payload, mime, *, still=False):
    validate_image(payload, mime)
    with Image.open(BytesIO(payload)) as image, ExitStack() as frames_to_close:
        frames, durations = [], []
        for index in range(1 if still else getattr(image, 'n_frames', 1)):
            image.seek(index)
            with ImageOps.exif_transpose(image).convert('RGBA') as decoded:
                frame = Image.frombytes('RGBA', decoded.size, decoded.tobytes())
            frames_to_close.callback(frame.close)
            frames.append(frame)
            durations.append(min(655350, max(10, int(image.info.get('duration', 100)))))
        output = ImageOutput()
        if len(frames) == 1:
            frames[0].save(output, format='PNG')
            return output.getvalue(), 'image/png'
        # shortcut: GIF quantizes animated PNG/WebP colors; use APNG if full-color animation is required.
        frames[0].save(output, format='GIF', save_all=True, append_images=frames[1:],
                       duration=durations, loop=min(65535, max(0, int(image.info.get('loop', 0)))),
                       disposal=2, optimize=False)
        return output.getvalue(), 'image/gif'


def invalid(message="Invalid image upload."):
    return AuthError(422, "VALIDATION_ERROR", message)


def validate_image(payload: bytes, declared_mime: str) -> str:
    if not 0 < len(payload) <= MAX_FILE_BYTES:
        raise invalid("Image must contain 1 byte to 5 MiB.")
    signature = None
    for fmt, matched in [("JPEG", payload.startswith(b"\xff\xd8\xff")),
                         ("PNG", payload.startswith(b"\x89PNG\r\n\x1a\n")),
                         ("GIF", payload[:6] in {b"GIF87a", b"GIF89a"}),
                         ("WEBP", payload[:4] == b"RIFF" and payload[8:12] == b"WEBP")]:
        if matched:
            signature = fmt
    if signature is None or FORMATS[signature][0] != declared_mime:
        raise invalid("Image MIME and signature must agree.")
    if ((signature == "JPEG" and not payload.endswith(b"\xff\xd9"))
            or (signature == "GIF" and not payload.endswith(b";"))
            or (signature == "PNG" and not payload.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"))
            or (signature == "WEBP" and int.from_bytes(payload[4:8], "little") + 8 != len(payload))):
        raise invalid("Image container is truncated or has trailing bytes.")
    try:
        # Check dimensions before verify/load: these may allocate or inspect all frames.
        with Image.open(BytesIO(payload), formats=list(FORMATS)) as image:
            if image.format != signature or image.width * image.height > MAX_PIXELS:
                raise invalid("Image format or frame dimensions exceed policy.")
            image.verify()
        total = 0
        with Image.open(BytesIO(payload), formats=list(FORMATS)) as image:
            for index in range(MAX_FRAMES + 1):
                try:
                    image.seek(index)
                except EOFError:
                    break
                pixels = image.width * image.height
                total += pixels
                if index >= MAX_FRAMES or pixels > MAX_PIXELS or total > MAX_TOTAL_PIXELS:
                    raise invalid("Image exceeds frame or pixel budget.")
                image.load()
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError):
        raise invalid("Image is corrupt or exceeds decoding limits.") from None
    return FORMATS[signature][1]


async def receive_image(request: Request):
    content_type = request.headers.get("content-type", "")
    if len(content_type) > 1024:
        raise invalid("Multipart Content-Type too large.")
    kind, options = parse_options_header(content_type)
    boundary = options.get(b"boundary", b"")
    if kind != b"multipart/form-data" or not 1 <= len(boundary) <= 200 or any(c < 33 or c > 126 for c in boundary):
        raise invalid("Expected multipart/form-data with one file field.")
    payload, field, value = bytearray(), bytearray(), bytearray()
    headers = {}
    parts, header_bytes, total = 0, 0, 0
    finished = False
    mime = ""

    def on_part_begin():
        nonlocal parts
        parts += 1
        if parts > 1:
            raise invalid("Exactly one file field is permitted.")

    def header_data(target, data, start, end):
        nonlocal header_bytes
        header_bytes += end - start
        if header_bytes > 8192:
            raise invalid("Multipart headers too large.")
        target.extend(data[start:end])

    def on_header_end():
        name = bytes(field).lower()
        if name in headers or len(headers) >= 8:
            raise invalid("Invalid multipart headers.")
        headers[name] = bytes(value)
        field.clear()
        value.clear()

    def on_headers_finished():
        nonlocal mime
        disposition, attributes = parse_options_header(headers.get(b"content-disposition", b""))
        if (disposition != b"form-data" or attributes.get(b"name") != b"file"
                or not attributes.get(b"filename") or b"content-transfer-encoding" in headers):
            raise invalid("Exactly one file field is required.")
        mime = headers.get(b"content-type", b"").decode("ascii", errors="replace")
        if mime not in {item[0] for item in FORMATS.values()}:
            raise invalid("Unsupported declared image MIME.")

    def on_part_data(data, start, end):
        if len(payload) + end - start > MAX_FILE_BYTES:
            raise invalid("Image exceeds 5 MiB.")
        payload.extend(data[start:end])

    def on_end():
        nonlocal finished
        finished = True

    parser = MultipartParser(boundary, {"on_part_begin": on_part_begin,
        "on_header_field": lambda data, start, end: header_data(field, data, start, end),
        "on_header_value": lambda data, start, end: header_data(value, data, start, end),
        "on_header_end": on_header_end, "on_headers_finished": on_headers_finished,
        "on_part_data": on_part_data, "on_end": on_end})
    try:
        async for chunk in request.stream():
            for offset in range(0, len(chunk), 65536):
                piece = chunk[offset:offset + 65536]
                total += len(piece)
                parser.write(piece)
                if total - len(payload) > MAX_OVERHEAD:
                    raise invalid("Multipart overhead too large.")
        parser.finalize()
    except (MultipartParseError, ClientDisconnect):
        raise invalid("Incomplete or malformed multipart body.") from None
    if not finished or parts != 1:
        raise invalid("Incomplete multipart upload.")
    return bytes(payload), mime


@dataclass
class UploadTransaction:
    account: AuthenticatedAccount
    saved: LocalObject | None = None


def upload_transaction(request: Request, response: Response, raw=Depends(session_cookie)):
    operation = None
    committing = False
    try:
        with contextmanager(require_authenticated_user)(request, response, raw) as account:
            require_account_csrf(request, account)
            operation = UploadTransaction(account)
            yield operation
            committing = True
    except BaseException as error:
        if operation is not None and operation.saved is not None:
            sqlstate = getattr(getattr(error, "orig", None), "sqlstate", None)
            if committing and isinstance(error, DBAPIError) and (sqlstate is None or sqlstate.startswith("08")):
                # A lost COMMIT acknowledgement may mean the ready row already exists.
                logger.error("media_commit_uncertain object_key=%s reconcile_required", operation.saved.key)
            else:
                try:
                    operation.saved.discard()
                except OSError:
                    logger.error("media_cleanup_failed object_key=%s reconcile_required", operation.saved.key)
        raise
    finally:
        if operation is not None and operation.saved is not None:
            operation.saved.close()


class Media(BaseModel):
    id: UUID
    mime: Literal["image/jpeg", "image/png", "image/webp", "image/gif"]
    size_bytes: int = Field(ge=1)
    status: Literal["pending", "ready", "rejected", "deleted"]
    url: str | None = Field(default=None, json_schema_extra={"format": "uri-reference"})


@router.get('/api/v1/media/{media_id}', name='userMedia', operation_id='getMedia', response_class=Response,
            tags=['Media'], responses={200: {'content': {
                mime: {'schema': {'type': 'string', 'format': 'binary'}} for mime in ('image/png', 'image/gif')}},
                **{status: {'model': ErrorResponse} for status in (404, 422, 429, 500)}},
            openapi_extra={'security': [{}, {'sessionCookie': []}]})
def get_media(media_id: UUID, request: Request, still: bool = False, raw=Depends(session_cookie)):
    from app.blog import public_posts
    from app.comments import lock_public_post

    unavailable = AuthError(404, 'NOT_FOUND', 'Image not available.')
    with request.app.state.auth_session_factory() as db, db.begin():
        media = db.get(MediaUpload, media_id)
        if media is None or media.status != 'ready':
            raise unavailable
        owner = False
        # Only lock this media's owner session; unrelated visitors cannot invert user lock order.
        if raw and TOKEN.fullmatch(raw) and db.scalar(select(AuthSession.user_id).where(
                AuthSession.token_hash == digest(raw))) == media.owner_id:
            try:
                owner = current_session(db, request.app.state.auth, raw).user_id == media.owner_id
            except AuthError as error:
                if error.status != 401:
                    raise
        author = db.scalar(select(User).where(User.id == media.owner_id, User.status == 'active')
                           .with_for_update(read=True))
        if author is None:
            raise unavailable
        if not owner:
            profile = db.scalar(select(Profile).where(Profile.user_id == media.owner_id,
                or_(Profile.avatar_media_id == media_id, Profile.cover_media_id == media_id)).with_for_update(read=True))
            if profile is None:
                post_id = db.scalar(public_posts().with_only_columns(Post.id).where(Post.media_id == media_id).limit(1))
                if post_id is None:
                    raise unavailable
                lock_public_post(db, post_id)
                if db.get(Post, post_id).media_id != media_id:
                    raise unavailable
        media = db.scalar(select(MediaUpload).where(MediaUpload.id == media_id, MediaUpload.status == 'ready')
                          .with_for_update(read=True).execution_options(populate_existing=True))
        if media is None:
            raise unavailable
        try:
            payload = read_private_object(MediaSettings().media_storage_root, media.object_key, MAX_FILE_BYTES)
            if len(payload) != media.size_bytes:
                raise ValueError('Private image size changed.')
            data, mime = normalize_image(payload, media.mime, still=still)
        # shortcut: GIF delay coalescing can overflow; use still=true until the encoder supports that case.
        except (OSError, ValueError, OverflowError, ValidationError, AuthError):
            raise unavailable from None
        return Response(data, media_type=mime, headers={'Content-Security-Policy': "default-src 'none'; sandbox"})


@router.post("/api/v1/media", status_code=201, response_model=Media, operation_id="uploadMedia", tags=["Media"],
    responses=ERRORS,
    openapi_extra=CSRF_HEADER | {"requestBody": {"required": True, "content": {
        "multipart/form-data": {"schema": {"type": "object", "required": ["file"],
            "properties": {"file": {"type": "string", "format": "binary"}}}}}}})
async def upload_media(request: Request, operation=Depends(upload_transaction, scope="function")):
    payload, mime = await receive_image(request)
    extension = await run_in_threadpool(validate_image, payload, mime)
    try:
        operation.saved = await run_in_threadpool(LocalObject, MediaSettings().media_storage_root, extension, payload)
    except (OSError, ValidationError):
        raise AuthError(500, "INTERNAL_ERROR", "Private media storage unavailable.") from None
    now = request.app.state.auth.now()
    row = MediaUpload(id=uuid4(), owner_id=operation.account.user.id, object_key=operation.saved.key,
        mime=mime, size_bytes=len(payload), status="ready", created_at=now, updated_at=now)
    operation.account.db.add(row)
    await run_in_threadpool(operation.account.db.flush)
    return Media(id=row.id, mime=mime, size_bytes=len(payload), status="ready", url=media_url(row.id))
