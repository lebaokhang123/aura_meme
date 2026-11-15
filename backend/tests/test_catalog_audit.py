"""Private catalog ingestion uses synthetic images and never touches a database."""
from hashlib import sha256
import json
import os

from PIL import Image
import pytest

from app.catalog_audit import build_package


def fixture_source(tmp_path):
    source = tmp_path / 'source'
    (source / 'D').mkdir(parents=True)
    image = source / 'D' / 'original.png'
    Image.new('RGB', (12, 8), (41, 22, 70)).save(image)
    return source, image, tmp_path / 'catalog.local' / 'review'


def test_reimport_preserves_content_identity_owner_edits_and_source(tmp_path):
    source, image, package = fixture_source(tmp_path)
    data = image.read_bytes()
    digest = sha256(data).hexdigest()
    first = build_package(source, package, {digest: 'Mèo Đáng Yêu'})
    item = first['items'][0]
    assert item['slug'] == 'meo-dang-yeu-' + digest[:16]
    assert item['source_rights']['review_status'] == item['name_review_status'] == 'pending'
    assert (package / item['file']).read_bytes() == data
    assert image.read_bytes() == data
    item['name_vi'] = 'Tên Owner sửa'
    item['name_review_status'] = 'approved'
    item['source_rights']['license'] = 'Owner evidence still under review'
    (package / 'catalog.json').write_text(json.dumps(first), encoding='utf-8')
    image.rename(image.with_name('renamed.png'))
    second = build_package(source, package, {digest: 'Do not overwrite'})
    assert second['items'][0]['id'] == item['id']
    assert second['items'][0]['file'] == item['file']
    assert second['items'][0]['name_vi'] == 'Tên Owner sửa'
    assert second['items'][0]['name_review_status'] == 'approved'
    assert second['items'][0]['source_rights'] == item['source_rights']
    assert second['items'][0]['source_files'] == ['D/renamed.png']
    assert 'Tên Owner sửa' in (package / 'review.html').read_text(encoding='utf-8')
    third = build_package(source, package)
    assert third == second


def test_inventory_includes_unsupported_and_dedupes_same_rarity(tmp_path):
    source, image, package = fixture_source(tmp_path)
    (source / 'D' / 'duplicate.png').write_bytes(image.read_bytes())
    (source / 'D' / 'notes.txt').write_bytes(b'not an image')
    manifest = build_package(source, package)
    assert len(manifest['items']) == 1 and len(manifest['inventory']) == 3
    assert sorted(row['status'] for row in manifest['inventory']) == ['duplicate', 'duplicate', 'unsupported']
    unknown = next(row for row in manifest['inventory'] if row['status'] == 'unsupported')
    assert unknown['mime'] == 'application/octet-stream' and unknown['item_id'] is None
    assert (package / unknown['file']).read_bytes() == b'not an image'
    assert manifest['items'][0]['source_files'] == ['D/duplicate.png', 'D/original.png']


def test_cross_rarity_duplicate_never_becomes_catalog_item(tmp_path):
    source, image, package = fixture_source(tmp_path)
    (source / 'S').mkdir()
    (source / 'S' / 'same.png').write_bytes(image.read_bytes())
    manifest = build_package(source, package)
    assert manifest['items'] == []
    assert {row['status'] for row in manifest['inventory']} == {'cross-rarity-conflict'}
    assert all(row['item_id'] is None for row in manifest['inventory'])


def test_conflicting_destination_or_reviewed_metadata_refused(tmp_path):
    source, _, package = fixture_source(tmp_path)
    manifest = build_package(source, package)
    file = package / manifest['items'][0]['file']
    file.write_bytes(b'conflicting content')
    with pytest.raises(ValueError, match='destination'):
        build_package(source, package)
    assert file.read_bytes() == b'conflicting content'
    manifest['items'][0]['rarity'] = 'S'
    (package / 'catalog.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError, match='metadata'):
        build_package(source, package)


def test_private_path_links_and_source_overlap_refused(tmp_path):
    source, image, package = fixture_source(tmp_path)
    with pytest.raises(ValueError, match='ignored'):
        build_package(source, tmp_path / 'public')
    with pytest.raises(ValueError, match='separate'):
        build_package(source, source / 'catalog.local')
    os.link(image, source / 'D' / 'hardlink.png')
    with pytest.raises(ValueError, match='unlinked'):
        build_package(source, package)


def test_animation_and_unclassified_files_are_private_inventory_only(tmp_path):
    source, _, package = fixture_source(tmp_path)
    (source / 'other').mkdir()
    Image.new('RGB', (3, 3)).save(source / 'other' / 'outside.png')
    Image.new('RGB', (3, 3)).save(source / 'D' / 'animated.gif', save_all=True,
                               append_images=[Image.new('RGB', (3, 3), 'red')], duration=10, loop=0)
    manifest = build_package(source, package)
    assert len(manifest['inventory']) == 3
    assert len(manifest['items']) == 1
    assert sum(row['status'] == 'unsupported' for row in manifest['inventory']) == 2


def test_identity_ignores_source_filename_and_keeps_background_entries(tmp_path):
    source, image, package = fixture_source(tmp_path)
    digest = sha256(image.read_bytes()).hexdigest()
    first = build_package(source, package, {digest: 'Ảnh thử'})
    image.rename(image.with_name('000-reordered.png'))
    second = build_package(source, tmp_path / 'second.local', {digest: 'Ảnh thử'})
    for field in ('id', 'slug', 'file', 'sha256'):
        assert first['items'][0][field] == second['items'][0][field]
    background = {'id': 'background-owned-by-separate-workstream', 'kind': 'background',
                  'name_vi': 'Nền tím', 'name_review_status': 'approved', 'source_rights': {}}
    second['items'].append(background)
    background_row = {'item_id': background['id'], 'source': 'procedural/violet-base', 'file': 'assets/background.png', 'rarity': 'D', 'status': 'supported'}
    second['inventory'].append(background_row)
    (tmp_path / 'second.local' / 'catalog.json').write_text(json.dumps(second), encoding='utf-8')
    rerun = build_package(source, tmp_path / 'second.local')
    assert rerun['items'][-1] == background
    assert rerun['inventory'][-1] == background_row


def test_duplicate_prior_json_keys_are_rejected(tmp_path):
    source, _, package = fixture_source(tmp_path)
    package.mkdir(parents=True)
    (package / 'catalog.json').write_text('{"items": [], "items": []}', encoding='utf-8')
    with pytest.raises(ValueError, match='Duplicate JSON'):
        build_package(source, package)



def test_old_approved_flag_without_proof_remains_pending_in_private_review(tmp_path):
    source,_,package=fixture_source(tmp_path)
    manifest=build_package(source,package)
    manifest['items'][0]['source_rights'].update(review_status='approved',author='Meme community',license='Unverified')
    (package/'catalog.json').write_text(json.dumps(manifest),encoding='utf-8')
    updated=build_package(source,package)
    assert updated['items'][0]['source_rights']['review_status']=='pending'
