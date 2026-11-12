"""User media is delivered through current visibility checks, never a static root."""
from io import BytesIO
import os
from uuid import UUID, uuid4

import pytest
from PIL import Image, PngImagePlugin
from sqlalchemy import select

from app.models import AuthSession, Category, MediaUpload, Post, Profile, User
from test_auth import ORIGIN, auth, csrf, login, migrated, register
from test_media import media, picture, upload


def test_normalization_removes_metadata_and_preserves_animation():
    from app.media import normalize_image
    source = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('private-location', 'secret-coordinate')
    Image.new('RGB', (8, 6), 'red').save(source, format='PNG', pnginfo=metadata)
    data, mime = normalize_image(source.getvalue(), 'image/png')
    assert mime == 'image/png' and b'secret-coordinate' not in data
    with Image.open(BytesIO(data)) as image:
        assert image.size == (8, 6) and not image.info
    source = BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = 'secret-coordinate'
    Image.new('RGB', (8, 6), 'red').save(source, format='JPEG', exif=exif)
    data, _ = normalize_image(source.getvalue(), 'image/jpeg')
    with Image.open(BytesIO(data)) as image:
        assert image.size == (6, 8) and not image.getexif() and b'secret-coordinate' not in data
    animated = BytesIO()
    frames = [Image.new('RGBA', (8, 6), color) for color in ('red', 'blue', 'green')]
    frames[0].save(animated, format='GIF', save_all=True, append_images=frames[1:],
                   duration=[40, 80, 120], loop=2, comment=b'secret-coordinate')
    data, mime = normalize_image(animated.getvalue(), 'image/gif')
    assert mime == 'image/gif' and b'secret-coordinate' not in data
    with Image.open(BytesIO(data)) as image:
        assert image.n_frames == 3 and image.info['loop'] == 2
        durations = []
        for index in range(3):
            image.seek(index)
            durations.append(image.info['duration'])
        assert durations == [40, 80, 120]
    data, mime = normalize_image(animated.getvalue(), 'image/gif', still=True)
    with Image.open(BytesIO(data)) as image:
        assert mime == 'image/png' and getattr(image, 'n_frames', 1) == 1 and not image.info


def test_normalized_output_is_bounded(monkeypatch):
    from app import media as implementation
    monkeypatch.setattr(implementation, 'MAX_DELIVERY_BYTES', 8)
    with pytest.raises(ValueError, match='delivery budget'):
        implementation.normalize_image(picture(), 'image/png')


def test_post_and_comment_author_serializers_use_relative_media_paths():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from app.blog import post_dto
    from app.comments import comment_dto
    now, user_id, media_id, post_id, category_id = datetime.now(timezone.utc), uuid4(), uuid4(), uuid4(), uuid4()
    user = SimpleNamespace(id=user_id, username='writer', created_at=now)
    profile = SimpleNamespace(display_name='Writer', bio=None, avatar_media_id=media_id)
    category = SimpleNamespace(id=category_id, slug='pictures', name='Pictures', status='active')
    post = SimpleNamespace(id=post_id, title='Picture', content='', media_id=media_id, status='published', created_at=now, updated_at=now)
    comment = SimpleNamespace(id=uuid4(), post_id=post_id, body='A comment', created_at=now)
    path = '/api/v1/media/' + str(media_id)
    assert post_dto(post, user, profile, category).model_dump()['media_url'] == path
    assert post_dto(post, user, profile, category).author.avatar_url == path
    assert comment_dto(comment, user, profile).author.avatar_url == path


def test_public_profile_cover_contract_does_not_expand_author_dtos():
    from app.main import app
    contract = app.openapi()
    response = contract['paths']['/api/v1/users/{username}']['get']['responses']['200']['content']['application/json']['schema']
    assert response['$ref'].endswith('/PublicProfile')
    assert 'cover_url' in contract['components']['schemas']['PublicProfile']['properties']
    assert 'cover_url' not in contract['components']['schemas']['UserPublic']['properties']


@pytest.mark.parametrize('attack', ['key', 'hardlink', 'root_link', 'ancestor_link', 'directory'] + ([] if os.name == 'nt' else ['symlink']))
def test_private_read_rejects_links_and_non_server_keys(tmp_path, attack):
    from app.storage import read_private_object
    root = tmp_path / 'private'
    root.mkdir(mode=0o700)
    key = uuid4().hex + '.png'
    source = tmp_path / 'outside.png'
    source.write_bytes(picture())
    target = root / key
    if attack == 'key':
        key = '../outside.png'
    elif attack == 'directory':
        target.mkdir()
    elif attack == 'hardlink':
        os.link(source, target)
    elif attack in {'root_link', 'ancestor_link'}:
        root.rmdir()
        if os.name == 'nt':
            import subprocess
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(root), str(tmp_path)], capture_output=True)
            assert result.returncode == 0
        else:
            root.symlink_to(tmp_path, target_is_directory=True)
    else:
        target.symlink_to(source)
    try:
        with pytest.raises((OSError, ValueError)):
            read_private_object(root / 'nested' if attack == 'ancestor_link' else root, key, 5 * 1024 * 1024)
    finally:
        if attack in {'root_link', 'ancestor_link'}:
            root.rmdir() if os.name == 'nt' else root.unlink()


def test_private_reader_pins_regular_object_and_enforces_size(tmp_path, monkeypatch):
    from app import storage
    root = tmp_path / 'private'
    payload = picture()
    saved = storage.LocalObject(root, 'png', payload)
    saved.close()
    if os.name == 'nt':
        original = storage.windows_handle

        def pinned(path, *, directory, read=False):
            handle = original(path, directory=directory, read=read)
            if read:
                with pytest.raises(OSError):
                    path.write_bytes(b'replacement')
                with pytest.raises(OSError):
                    path.unlink()
            return handle

        monkeypatch.setattr(storage, 'windows_handle', pinned)
    assert storage.read_private_object(root, saved.key, len(payload)) == payload
    with pytest.raises(OSError):
        storage.read_private_object(root, saved.key, len(payload) - 1)


@pytest.mark.integration
def test_uploaded_image_owner_preview_public_post_and_hidden_revocation(media):
    client, connection, root = media
    uploaded = upload(client)
    ident = UUID(uploaded.json()['id'])
    path = '/api/v1/media/' + str(ident)
    assert uploaded.json()['url'] == path
    owner = connection.execute(select(MediaUpload.owner_id).where(MediaUpload.id == ident)).scalar_one()
    assert client.get(path).status_code == 200
    assert client.get(path + '?still=true').status_code == 200
    cookies = dict(client.cookies)
    client.cookies.clear()
    denied = client.get(path)
    assert denied.status_code == 404 and str(root) not in denied.text and 'object_key' not in denied.text
    assert client.get(path + '?still=true').status_code == 404
    now = client.app.state.auth.now()
    category = uuid4()
    post = uuid4()
    connection.execute(Category.__table__.insert().values(id=category, slug='display', name='Display', status='active', created_at=now, updated_at=now))
    connection.execute(Post.__table__.insert().values(id=post, author_id=owner, category_id=category, title='Visible', content='', media_id=ident, status='published', created_at=now, updated_at=now))
    response = client.get(path)
    assert response.status_code == 200 and response.headers['content-type'] == 'image/png'
    assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
    assert 'sandbox' in response.headers['content-security-policy']
    assert client.get('/api/v1/posts/' + str(post)).json()['media_url'] == path
    for table, values, predicate in [
        (Post, {'status': 'hidden'}, Post.id == post),
        (Category, {'status': 'hidden'}, Category.id == category),
        (User, {'status': 'locked'}, User.id == owner),
        (MediaUpload, {'status': 'rejected'}, MediaUpload.id == ident),
    ]:
        with connection.begin_nested() as transaction:
            connection.execute(table.__table__.update().where(predicate).values(**values))
            assert client.get(path).status_code == 404
            transaction.rollback()
    connection.execute(Post.__table__.update().where(Post.id == post).values(status='draft'))
    assert client.get(path).status_code == 404
    client.cookies.update(cookies)
    assert client.get(path).status_code == 200


@pytest.mark.integration
def test_profile_attachment_and_other_user_cannot_read_private_upload(media):
    client, connection, _ = media
    uploaded = upload(client).json()
    ident, path = UUID(uploaded['id']), uploaded['url']
    owner = connection.execute(select(MediaUpload.owner_id).where(MediaUpload.id == ident)).scalar_one()
    response = client.patch('/api/v1/users/me', json={'avatar_media_id': str(ident), 'cover_media_id': str(ident)},
                            headers={'Origin': ORIGIN, 'X-CSRF-Token': csrf(client)})
    assert response.status_code == 200
    assert response.json()['avatar_url'] == response.json()['cover_url'] == path
    client.cookies.clear()
    assert client.get(path).status_code == 200
    assert client.get('/api/v1/users/alice_auth').json()['avatar_url'] == path
    assert client.get('/api/v1/users/alice_auth').json()['cover_url'] == path
    connection.execute(Profile.__table__.update().where(Profile.user_id == owner).values(avatar_media_id=None))
    profile = client.get('/api/v1/users/alice_auth').json()
    assert profile['avatar_url'] is None and profile['cover_url'] == path
    assert client.get(profile['cover_url']).status_code == 200
    connection.execute(Profile.__table__.update().where(Profile.user_id == owner).values(avatar_media_id=None, cover_media_id=None))
    assert register(client, username='reader_display', email='reader-display@example.com').status_code == 201
    assert login(client, email='reader-display@example.com').status_code == 200
    assert client.get(path).status_code == 404
    assert client.get('/api/v1/media/' + str(uuid4())).status_code == 404


@pytest.mark.integration
def test_delivery_masks_missing_corrupt_or_linked_objects(media):
    client, connection, root = media
    uploaded = upload(client).json()
    key = connection.execute(select(MediaUpload.object_key).where(MediaUpload.id == UUID(uploaded['id']))).scalar_one()
    target = root / key
    original = target.read_bytes()
    target.write_bytes(b'not an image')
    assert client.get(uploaded['url']).status_code == 404
    target.unlink()
    assert client.get(uploaded['url']).status_code == 404
    outside = root.parent / 'outside.png'
    outside.write_bytes(original)
    os.link(outside, target)
    assert client.get(uploaded['url']).status_code == 404


@pytest.mark.integration
def test_gif_http_animation_and_reduced_motion_share_owner_visibility(media):
    client, _, _ = media
    path = upload(client, picture('GIF', frames=3), 'image/gif').json()['url']
    animated = client.get(path)
    assert animated.status_code == 200 and animated.headers['content-type'] == 'image/gif'
    with Image.open(BytesIO(animated.content)) as image:
        assert image.n_frames == 3
    still = client.get(path + '?still=true')
    assert still.status_code == 200 and still.headers['content-type'] == 'image/png'
    with Image.open(BytesIO(still.content)) as image:
        assert getattr(image, 'n_frames', 1) == 1
    client.cookies.clear()
    assert client.get(path).status_code == client.get(path + '?still=true').status_code == 404


@pytest.mark.integration
@pytest.mark.parametrize('problem', ['revoked', 'expired', 'locked', 'invalid_cookie'])
def test_private_preview_masks_invalid_sessions(media, problem):
    from datetime import timedelta
    client, connection, _ = media
    uploaded = upload(client).json()
    now = client.app.state.auth.now()
    if problem == 'revoked':
        connection.execute(AuthSession.__table__.update().values(revoked_at=now))
    elif problem == 'expired':
        client.app.state.auth.now = lambda: now + timedelta(hours=2)
    elif problem == 'locked':
        connection.execute(User.__table__.update().values(status='locked'))
    else:
        client.cookies.clear()
        client.cookies.set('am_session', 'invalid')
    assert client.get(uploaded['url']).status_code == client.get(uploaded['url'] + '?still=true').status_code == 404


@pytest.mark.integration
def test_legal_gif_encoder_overflow_is_masked_and_still_remains_usable(media):
    client, _, _ = media
    output = BytesIO()
    Image.new('RGB', (4, 4), 'red').save(output, format='GIF', duration=655350)
    single = output.getvalue()
    control = single.index(b'!\xf9\x04')
    # Both source delays are legal; Pillow coalesces identical frames beyond GIF's delay field.
    payload = single[:control] + single[control:-1] * 2 + b';'
    uploaded = upload(client, payload, 'image/gif').json()
    assert client.get(uploaded['url']).status_code == 404
    still = client.get(uploaded['url'] + '?still=true')
    assert still.status_code == 200 and still.headers['content-type'] == 'image/png'
