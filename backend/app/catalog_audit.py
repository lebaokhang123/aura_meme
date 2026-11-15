"""Build a private, review-only catalog package; never import, approve or publish it."""
import argparse
from collections import defaultdict
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re
import unicodedata
from uuid import NAMESPACE_URL, uuid5

from PIL import Image, UnidentifiedImageError

from app.catalog_rights import reviewed_source_rights

RARITIES = 'DCBAS'
EXTENSIONS = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}
MAX_SOURCE_BYTES = 64 * 1024 * 1024


def checked_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
        raise ValueError('Links and junctions are forbidden.')
    return path


def bounded_bytes(path):
    checked_path(path)
    stat = path.stat()
    if not path.is_file() or stat.st_nlink != 1 or stat.st_size > MAX_SOURCE_BYTES:
        raise ValueError('Source must be a regular, unlinked file of at most 64 MiB.')
    with path.open('rb') as stream:
        data = stream.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError('Source grew beyond the byte limit.')
    return data


def image_metadata(data):
    metadata = {'mime': 'application/octet-stream', 'width': None, 'height': None}
    try:
        with Image.open(BytesIO(data)) as image:
            metadata.update(mime=Image.MIME.get(image.format, 'application/octet-stream'),
                            width=image.width, height=image.height)
            supported = (metadata['mime'] in EXTENSIONS and 0 < len(data) <= 5 * 1024 * 1024
                         and image.width * image.height <= 12_000_000 and getattr(image, 'n_frames', 1) == 1)
            if not supported:
                return metadata, False
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
        return metadata, True
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return metadata, False


def slugify(name):
    ascii_name = unicodedata.normalize('NFKD', name.replace('đ', 'd').replace('Đ', 'D')).encode('ascii', 'ignore').decode().lower()
    return re.sub('[^a-z0-9]+', '-', ascii_name).strip('-')[:65].rstrip('-') or 'cho-dat-ten'


def write_bytes_once(path, data):
    checked_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if bounded_bytes(path) != data:
            raise ValueError('Conflicting destination bytes; never overwrite.')
    else:
        with path.open('xb') as stream:
            stream.write(data)


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key.')
        result[key] = value
    return result


def build_package(source, package, names=None):
    """Names are optional SHA256 -> visually reviewed proposals; existing owner edits win."""
    source, package = checked_path(source).resolve(), checked_path(package).resolve()
    if source == package or source in package.parents or package in source.parents:
        raise ValueError('Source and private package must be separate trees.')
    if not any(part.endswith('.local') for part in package.parts):
        raise ValueError('Review package must remain inside an ignored .local directory.')
    catalog_path = package / 'catalog.json'
    previous = json.loads(bounded_bytes(catalog_path).decode('utf-8'), object_pairs_hook=unique_keys) if catalog_path.exists() else {'items': []}
    old = {}
    preserved = []
    for item in previous['items']:
        if item['kind'] != 'avatar':
            preserved.append(item)
            continue
        digest = item['sha256']
        if digest in old:
            raise ValueError('Duplicate previous content identity.')
        old[digest] = item
    inventory, groups = [], defaultdict(list)
    for path in sorted(source.rglob('*')):
        checked_path(path)
        if path.is_dir():
            continue
        data = bounded_bytes(path)
        relative = path.relative_to(source).as_posix()
        rarity = path.relative_to(source).parts[0]
        metadata, supported = image_metadata(data)
        row = {'source': relative, 'rarity': rarity if rarity in tuple(RARITIES) else None,
               'sha256': sha256(data).hexdigest(), 'byte_size': len(data), **metadata,
               'status': 'supported' if supported and rarity in tuple(RARITIES) else 'unsupported',
               'item_id': None, 'file': None}
        inventory.append(row)
        groups[row['sha256']].append((row, path))
    items = []
    for digest, entries in sorted(groups.items()):
        row = entries[0][0]
        conflict = len({entry['rarity'] for entry, _ in entries}) > 1
        supported = row['status'] == 'supported' and not conflict
        if supported:
            name = (names or {}).get(digest, 'Chờ đặt tên')
            saved = old.get(digest)
            if saved:
                name = saved['name_vi']
            slug = slugify(name) + '-' + digest[:16]
            filename = 'assets/' + slug + EXTENSIONS[row['mime']]
            identity = str(uuid5(NAMESPACE_URL, 'aurameme:catalog:sha256:' + digest))
            item = {'id': identity, 'slug': slug, 'name_vi': name, 'name_review_status': 'pending',
                    'kind': 'avatar', 'collection': 'vault-v1', 'rarity': row['rarity'],
                    'file': filename, 'sha256': digest, 'mime': row['mime'],
                    'byte_size': row['byte_size'], 'width': row['width'], 'height': row['height'],
                    'source_files': sorted(entry['source'] for entry, _ in entries),
                    'source_rights': {'source': 'Owner-provided local files; provenance unverified',
                                      'author': 'Unknown — Owner review required', 'license': 'Unverified',
                                      'attribution': 'Pending Owner review; private use only', 'review_status': 'pending'}}
            if saved:
                for field in ('id', 'kind', 'collection', 'rarity', 'sha256', 'mime', 'byte_size', 'width', 'height'):
                    if saved[field] != item[field]:
                        raise ValueError('Existing catalog metadata conflicts with source bytes.')
                # Owner may revise names without renaming existing byte copies or identities.
                for field in ('slug', 'file', 'name_review_status', 'source_rights'):
                    item[field] = saved[field]
                if item['name_review_status'] not in {'pending', 'approved', 'rejected'} or item['source_rights']['review_status'] not in {'pending', 'approved', 'rejected'}:
                    raise ValueError('Invalid owner review state.')
            if not reviewed_source_rights(item["source_rights"] | {"sha256":digest}):
                item["source_rights"]["review_status"] = "pending"
            items.append(item)
            filename = item['file']
            relative_file = Path(filename)
            if relative_file.is_absolute() or '..' in relative_file.parts or '\\' in filename or ':' in filename:
                raise ValueError('Catalog destination must stay inside the private package.')
        else:
            filename = 'unsupported/' + digest + '.bin'
            identity = None
        write_bytes_once(package / filename, bounded_bytes(entries[0][1]))
        for entry, _ in entries:
            entry.update(file=filename, item_id=identity)
            if conflict:
                entry['status'] = 'cross-rarity-conflict'
            elif supported and len(entries) > 1:
                entry['status'] = 'duplicate'
    if set(old) - {item['sha256'] for item in items}:
        raise ValueError('Previously reviewed assets vanished or became unsupported; review source changes first.')
    preserved_ids = {item['id'] for item in preserved}
    inventory.extend(row for row in previous.get('inventory', []) if row.get('item_id') in preserved_ids)
    manifest = {'version': previous.get('version', 1), 'items': items + preserved, 'inventory': inventory}
    package.mkdir(parents=True, exist_ok=True)
    checked_path(catalog_path)
    catalog_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_review(package, manifest)
    return manifest


def write_review(package, manifest):
    """Static HTML is derived only from canonical JSON, and works via file://."""
    lookup = {item['id']: item for item in manifest['items']}
    rows = []
    for entry in manifest['inventory']:
        item = lookup.get(entry['item_id'])
        picture = f'<img loading="lazy" src="{escape(entry["file"], quote=True)}" alt="Ảnh cần duyệt">' if item else 'Không hỗ trợ'
        values = [entry['source'], item['name_vi'] if item else 'Chưa đặt tên', entry['rarity'] or '?',
                  entry['file'], item['name_review_status'] if item else entry['status'],
                  json.dumps(item['source_rights'], ensure_ascii=False) if item else 'Chưa duyệt quyền', entry['status']]
        rows.append('<tr><td>' + picture + '</td>' + ''.join('<td>' + escape(str(value)) + '</td>' for value in values) + '</tr>')
    page = '''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Bảo Khố V1 — Owner Review A</title><style>body{font:16px system-ui;background:#181322;color:#eee;padding:20px}table{border-collapse:collapse;width:100%}th,td{padding:12px;border:1px solid #635972;text-align:left;overflow-wrap:anywhere;max-width:260px}img{width:140px;height:140px;object-fit:contain}a{color:#cab5ff}</style>
<h1>Bảo Khố V1 — Owner Review A</h1><p>PRIVATE · Trạng thái duyệt tên và quyền nằm ở từng hàng. Trang này không tự import hoặc phát hành.</p>
<p>Nguồn canonical: <a href="catalog.json">catalog.json</a>. Sửa tên/quyền tại JSON rồi chạy lại audit để cập nhật trang này.</p>
<table><thead><tr><th>Ảnh gốc</th><th>File gốc</th><th>Tên đề xuất</th><th>Hạng</th><th>File mới</th><th>Duyệt tên</th><th>Quyền sử dụng</th><th>Kiểm kê</th></tr></thead><tbody>'''
    checked_path(package / 'review.html').write_text(page + ''.join(rows) + '</tbody></table></html>\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('package', type=Path)
    args = parser.parse_args()
    manifest = build_package(args.source, args.package)
    print(f"Private review only: {len(manifest['inventory'])} files, {len(manifest['items'])} unique draft images; no database changes.")


if __name__ == '__main__':
    main()
