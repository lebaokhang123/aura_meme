"""Real image bytes, temporary private storage and real PostgreSQL transactions."""
from io import BytesIO
from uuid import UUID

import pytest
from PIL import Image
from sqlalchemy import select

from app.media import MAX_FILE_BYTES, validate_image
from app.models import MediaUpload
from app.security import AuthError
from test_auth import auth, migrated, register, login, csrf, ORIGIN


def picture(fmt="PNG", size=(16, 12), frames=1):
    output = BytesIO()
    images = [Image.new("RGB", size, (i % 255, 40, 80)) for i in range(frames)]
    options = dict(save_all=True, append_images=images[1:], duration=20, loop=0, optimize=False) if frames > 1 else {}
    images[0].save(output, format=fmt, **options)
    for image in images:
        image.close()
    return output.getvalue()


@pytest.fixture
def media(auth, tmp_path, monkeypatch):
    client, connection = auth
    monkeypatch.setenv("MEDIA_STORAGE_ROOT", str(tmp_path / "uploads"))
    assert register(client).status_code == 201
    assert login(client).status_code == 200
    yield client, connection, tmp_path / "uploads"
    # Only objects inside this test's directory; never development uploads.
    for path in tmp_path.rglob("*"):
        if path.is_file() and not path.is_symlink():
            path.unlink()
    assert not list(tmp_path.rglob("*.*"))


def upload(client, payload=None, mime="image/png", filename="test.png", **kwargs):
    return client.post("/api/v1/media", files={"file": (filename, picture() if payload is None else payload, mime)},
                       headers={"Origin": ORIGIN, "X-CSRF-Token": csrf(client)}, **kwargs)


@pytest.mark.integration
@pytest.mark.parametrize("fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp"), ("GIF", "image/gif")])
def test_real_upload_private_bytes_and_metadata(media, fmt, mime):
    client, connection, root = media
    payload = picture(fmt)
    response = upload(client, payload, mime)
    assert response.status_code == 201, response.text
    dto = response.json()
    assert set(dto) == {"id", "mime", "size_bytes", "status", "url"}
    assert dto | {"id": None} == dict(id=None, mime=mime, size_bytes=len(payload), status="ready", url='/api/v1/media/' + dto['id'])
    row = connection.execute(select(MediaUpload.__table__)).mappings().one()
    assert row["id"] == UUID(dto["id"])
    assert (root / row["object_key"]).read_bytes() == payload
    delivered = client.get(dto['url'])
    assert delivered.status_code == 200 and delivered.headers['content-type'] == 'image/png'


@pytest.mark.parametrize("payload,mime", [(b"", "image/png"), (b"<script>x</script>", "image/png"),
    (b"%PDF-1.7", "image/jpeg"), (b"PK\x03\x04zip", "image/png"), (b"MZexe", "image/gif")])
def test_fake_images_rejected(payload, mime):
    with pytest.raises(AuthError) as error:
        validate_image(payload, mime)
    assert error.value.status == 422


def test_gif_animation_and_limits():
    assert validate_image(picture("GIF", frames=3), "image/gif") == "gif"
    for payload in [picture("GIF", frames=61), picture("PNG", size=(4001, 3000)), b"x" * (MAX_FILE_BYTES + 1)]:
        with pytest.raises(AuthError):
            validate_image(payload, "image/gif" if payload.startswith(b"GIF") else "image/png")


@pytest.mark.parametrize("fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp"), ("GIF", "image/gif")])
def test_mime_mismatch_truncation_and_corruption(fmt, mime):
    payload = picture(fmt)
    for bad, declared in [(payload, "image/svg+xml"), (payload, "image/png" if fmt != "PNG" else "image/jpeg"),
                          (payload[:-8], mime), (payload[:16] + b"broken" + payload[-12:], mime)]:
        with pytest.raises(AuthError):
            validate_image(bad, declared)


def test_gif_cumulative_budget_and_boundary():
    assert validate_image(picture("GIF", frames=60), "image/gif") == "gif"
    with pytest.raises(AuthError):
        validate_image(picture("GIF", size=(2000, 2000), frames=11), "image/gif")
    assert validate_image(picture("PNG", size=(4000, 3000)), "image/png") == "png"


def test_decompression_bomb_header_rejected_without_loading_pixels():
    import struct
    import zlib
    payload = bytearray(picture())
    payload[16:24] = struct.pack(">II", 100_000, 100_000)
    payload[29:33] = struct.pack(">I", zlib.crc32(payload[12:29]))
    with pytest.raises(AuthError):
        validate_image(bytes(payload), "image/png")


@pytest.mark.integration
@pytest.mark.parametrize("case", ["empty", "oversize", "missing", "field", "extra_file", "extra_field", "fake", "bad_mime"])
def test_bad_upload_does_not_write(media, case):
    client, connection, root = media
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf(client)}
    files = [("file", ("test.png", picture(), "image/png"))]
    kwargs = {}
    if case == "empty": files = [("file", ("x.png", b"", "image/png"))]
    if case == "oversize": files = [("file", ("x.png", b"x" * (MAX_FILE_BYTES + 1), "image/png"))]
    if case == "missing": files = []
    if case == "field": files = [("file", (None, "plain field"))]
    if case == "extra_file": files += [("file", ("other.png", picture(), "image/png"))]
    if case == "extra_field": kwargs["data"] = {"owner_id": "forged"}
    if case == "fake": files = [("file", ("real.png", b"<svg>payload</svg>", "image/png"))]
    if case == "bad_mime": files = [("file", ("real.png", picture(), "application/octet-stream"))]
    response = client.post("/api/v1/media", files=files, headers=headers, **kwargs)
    assert response.status_code == 422, response.text
    assert connection.execute(select(MediaUpload.id)).all() == []
    assert not root.exists()


def raw_upload(client, chunks, extra_headers=(), *, authenticated=True):
    """Actual separate ASGI receive events, rather than TestClient's coalesced iterable."""
    from app.main import app
    import json
    headers = [(b"host", b"testserver"), (b"content-type", b"multipart/form-data; boundary=boundary")]
    if authenticated:
        headers += [(b"origin", ORIGIN.encode()), (b"x-csrf-token", csrf(client).encode()),
                    (b"cookie", ("am_session=" + client.cookies.get("am_session")).encode())]
    for name, value in extra_headers:
        headers = [(key, content) for key, content in headers if key != name]
        headers.append((name, value))
    consumed = 0
    sent = []

    async def invoke():
        async def receive():
            nonlocal consumed
            assert consumed < len(chunks), "Unexpected receive beyond request"
            index = consumed
            consumed += 1
            return {"type": "http.request", "body": chunks[index], "more_body": index < len(chunks) - 1}

        async def send(event):
            sent.append(event)

        await app({"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": "POST", "scheme": "https", "path": "/api/v1/media",
            "raw_path": b"/api/v1/media", "root_path": "", "query_string": b"", "headers": headers,
            "client": ("media-tests", 123), "server": ("testserver", 443)}, receive, send)
    client.portal.call(invoke)
    status = next(event["status"] for event in sent if event["type"] == "http.response.start")
    body = b"".join(event.get("body", b"") for event in sent if event["type"] == "http.response.body")
    return status, json.loads(body), consumed


def multipart(payload=None, tail=True):
    return (b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="x.png"\r\n'
            b'Content-Type: image/png\r\n\r\n' + (picture() if payload is None else payload)
            + (b'\r\n--boundary--\r\n' if tail else b''))


@pytest.mark.integration
@pytest.mark.parametrize("case", ["anonymous", "csrf", "origin"])
def test_auth_precedes_body_receive(media, case):
    client, connection, root = media
    headers = [] if case == "anonymous" else [(b"x-csrf-token", b"bad")] if case == "csrf" else [(b"origin", b"https://evil.example")]
    status, body, consumed = raw_upload(client, [multipart()], headers, authenticated=case != "anonymous")
    assert status == (401 if case == "anonymous" else 403)
    assert consumed == 0
    assert not root.exists()


@pytest.mark.integration
@pytest.mark.parametrize("case", ["valid", "chunked", "oversize", "lying_small", "lying_large", "negative", "huge_header", "overhead", "incomplete"])
def test_streaming_boundary_and_multipart_limits(media, case):
    from app.media import MAX_REQUEST_BYTES
    client, connection, root = media
    body = multipart()
    headers = []
    if case == "chunked": headers = [(b"transfer-encoding", b"chunked")]
    if case == "oversize": body = multipart(b"x" * (MAX_REQUEST_BYTES + 100))
    if case == "lying_small": headers = [(b"content-length", b"1")]
    if case == "lying_large": headers = [(b"content-length", str(MAX_REQUEST_BYTES + 1).encode())]
    if case == "negative": headers = [(b"content-length", b"-1")]
    if case == "huge_header": body = body.replace(b'x.png', b'x' * 9000)
    if case == "overhead": body = b" " * (70 * 1024) + body
    if case == "incomplete": body = multipart(tail=False)
    chunks = [body[index:index + 4093] for index in range(0, len(body), 4093)]
    status, dto, consumed = raw_upload(client, chunks, headers)
    assert status == (201 if case in {"valid", "chunked"} else 422), dto
    if status != 201:
        assert not root.exists()
        assert connection.execute(select(MediaUpload.id)).all() == []
    if case == "oversize": assert consumed < len(chunks)


@pytest.mark.integration
def test_filename_ignored_and_server_key_collision(media, monkeypatch):
    from app import storage
    from uuid import uuid4
    client, connection, root = media
    root.mkdir(mode=0o700)
    collision, unique = uuid4(), uuid4()
    old = root / (collision.hex + ".png")
    old.write_bytes(b"pre-existing")
    sequence = iter([collision, unique])
    monkeypatch.setattr(storage, "uuid4", lambda: next(sequence))
    response = upload(client, filename="../../outside.exe")
    assert response.status_code == 201, response.text
    assert old.read_bytes() == b"pre-existing"
    assert (root / (unique.hex + ".png")).read_bytes() == picture()
    assert not (root.parent / "outside.exe").exists()
    monkeypatch.setattr(storage, "uuid4", lambda: collision)
    assert upload(client).status_code == 500
    assert old.read_bytes() == b"pre-existing"
    assert len(connection.execute(select(MediaUpload.id)).all()) == 1


@pytest.mark.integration
@pytest.mark.parametrize("failure", ["fsync", "insert", "cleanup"])
def test_failures_compensate_private_object(media, monkeypatch, caplog, failure):
    from app import storage
    client, connection, root = media
    if failure in {"insert", "cleanup"}:
        connection.exec_driver_sql("CREATE FUNCTION m32_reject_media() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic media rejection'; END $$")
        connection.exec_driver_sql("CREATE TRIGGER m32_reject_media BEFORE INSERT ON media_uploads FOR EACH ROW EXECUTE FUNCTION m32_reject_media()")
    if failure == "fsync":
        monkeypatch.setattr(storage.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("synthetic disk error")))
    if failure == "cleanup":
        monkeypatch.setattr(storage.LocalObject, "discard", lambda self: (_ for _ in ()).throw(OSError("synthetic unlink failure")))
    response = upload(client)
    assert response.status_code == 500, response.text
    assert connection.execute(select(MediaUpload.id)).all() == []
    files = list(root.iterdir()) if root.exists() else []
    assert len(files) == (1 if failure == "cleanup" else 0)
    if failure == "cleanup":
        assert "media_cleanup_failed" in caplog.text and "reconcile_required" in caplog.text
    assert "synthetic" not in response.text and "object_key" not in response.text


@pytest.mark.integration
def test_uploaded_media_integrates_with_posts_and_fk(media):
    from app.models import Category, Post
    from test_blog import mutation
    from uuid import uuid4
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    client, connection, root = media
    now = client.app.state.auth.now()
    category = uuid4()
    connection.execute(Category.__table__.insert().values(id=category, slug="upload-cat", name="Upload", status="active", created_at=now, updated_at=now))
    media_id = upload(client).json()["id"]
    payload = dict(title="Real image", content="", category_id=str(category), media_id=media_id)
    created = mutation(client, "POST", "/posts", payload)
    assert created.status_code == 201, created.text
    assert mutation(client, "PATCH", "/posts/" + created.json()["id"], {"media_id": media_id}).status_code == 200
    connection.execute(MediaUpload.__table__.update().values(status="pending"))
    assert mutation(client, "POST", "/posts", payload).status_code == 422
    connection.execute(MediaUpload.__table__.update().values(status="ready"))
    assert mutation(client, "POST", "/auth/logout").status_code == 204
    second = register(client, username="other_media", email="other-media@example.com")
    assert second.status_code == 201
    assert login(client, email="other-media@example.com").status_code == 200
    assert mutation(client, "POST", "/posts", payload).status_code == 422
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(Post.__table__.update().where(Post.id == UUID(created.json()["id"])).values(author_id=UUID(second.json()["id"])))


@pytest.mark.parametrize("kind", ["root_reparse", "ancestor_junction", "object_hardlink"])
def test_storage_reparse_and_collision_safety(tmp_path, monkeypatch, kind):
    import os
    import subprocess
    from app.storage import LocalObject
    from app import storage
    from uuid import uuid4
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    sentinel = outside / "sentinel.png"
    sentinel.write_bytes(b"preserve")
    root = tmp_path / "uploads"
    if kind != "object_hardlink":
        if os.name == "nt":
            # Fixed literal paths supplied as argv; no recursive deletion or cross-shell enumeration.
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(root), str(outside)], capture_output=True)
            assert result.returncode == 0
        else:
            root.symlink_to(outside, target_is_directory=True)
        try:
            with pytest.raises(OSError):
                LocalObject(root / "nested" if kind == "ancestor_junction" else root, "png", picture())
        finally:
            if os.name == "nt": os.rmdir(root)
            else: root.unlink()
        assert sorted(file.name for file in outside.iterdir()) == ["sentinel.png"]
    else:
        root.mkdir(mode=0o700)
        collision = uuid4()
        # Hard links require no Windows developer-mode privilege and must never be overwritten either.
        os.link(sentinel, root / (collision.hex + ".png"))
        monkeypatch.setattr(storage, "uuid4", lambda: collision)
        with pytest.raises(OSError): LocalObject(root, "png", picture())
        (root / (collision.hex + ".png")).unlink()
    assert sentinel.read_bytes() == b"preserve"


@pytest.mark.parametrize("root", ["relative/path", "/static/uploads", "C:/", "C:/private/../uploads"])
def test_storage_configuration_rejects_unsafe_roots(root):
    from app.config import MediaSettings
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        MediaSettings(_env_file=None, media_storage_root=root)


@pytest.mark.integration
def test_media_reuses_rate_limiter_without_receiving_body(media):
    client, connection, root = media
    statuses = [raw_upload(client, [b"must-not-parse"], authenticated=False)[0] for _ in range(61)]
    assert statuses[:60] == [401] * 60 and statuses[-1] == 429
    assert not root.exists()
