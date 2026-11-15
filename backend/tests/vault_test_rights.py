"""Explicit provenance for self-created, rollback-only synthetic test assets."""
from hashlib import sha256


def synthetic_rights(digest, **metadata):
    source = 'aurameme://original/synthetic-fixture'
    notice = 'Copyright AuraMeme synthetic fixtures'
    return {'source': source, 'author': 'AuraMeme synthetic fixtures', 'license': 'LicenseRef-AuraMeme-Original',
        'attribution': notice + '; generated in tests, not released', 'review_status': 'approved',
        'sha256': digest, 'mime': 'image/png', 'proof': {'basis': 'original', 'source': source,
            'license_id': 'LicenseRef-AuraMeme-Original', 'license_url': source + '/license',
            'artifact_sha256': digest, 'evidence_sha256': sha256(b'Self-created automated test fixture; not released').hexdigest(),
            'copyright_notice': notice}, **metadata}
