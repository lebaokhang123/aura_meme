"""Negative Security Tests for Vault Owner Private Demo Rights.

Verifies strict fail-closed constraints:
1. Unset/zero flag -> private demo rights rejected.
2. Production environment -> rejected even if flag=1.
3. Foreign DB -> rejected even if flag=1.
4. Remote host DB -> rejected even if flag=1.
5. Proof wrong or missing fields -> rejected.
6. SHA256 mismatch -> rejected.
7. Unapproved status -> rejected.
8. Valid private demo on valid demo/clone environment -> accepted.
9. Standard MIT and original rights remain unaffected and valid.
"""
import os
import pytest
from app.catalog_rights import reviewed_source_rights, _owner_private_demo_enabled

VALID_SHA = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
EVIDENCE_SHA = 'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb'

VALID_PRIVATE_DEMO_RIGHTS = {
    'review_status': 'approved',
    'source': 'Owner-collected internet memes; original source and author unverified',
    'author': 'Unidentified original meme creators',
    'license': 'LicenseRef-Owner-Private-Demo-Only',
    'attribution': 'Private demo only; Unidentified original meme creators; no rights verification',
    'sha256': VALID_SHA,
    'proof': {
        'basis': 'owner_private_demo',
        'source': 'Owner-collected internet memes; original source and author unverified',
        'license_id': 'LicenseRef-Owner-Private-Demo-Only',
        'license_url': f'aurameme://private-demo/owner-statement/{EVIDENCE_SHA}',
        'copyright_notice': 'Unidentified original meme creators; no rights verification',
        'artifact_sha256': VALID_SHA,
        'evidence_sha256': EVIDENCE_SHA,
    }
}

VALID_MIT_RIGHTS = {
    'review_status': 'approved',
    'source': 'https://github.com/example/repo',
    'author': 'Author Name',
    'license': 'MIT',
    'attribution': 'Copyright 2026 Author Name under MIT',
    'sha256': VALID_SHA,
    'proof': {
        'basis': 'licensed',
        'source': 'https://github.com/example/repo',
        'license_id': 'MIT',
        'license_url': 'https://opensource.org/licenses/MIT',
        'copyright_notice': 'Author Name',
        'artifact_sha256': VALID_SHA,
        'evidence_sha256': EVIDENCE_SHA,
    }
}


@pytest.fixture(autouse=True)
def restore_env():
    old = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(old)


def test_no_flag_rejects_private_demo():
    os.environ.pop('AURAMEME_OWNER_MEME_DEMO', None)
    os.environ['AUTH_ENVIRONMENT'] = 'development'
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://aurameme_demo:pass@127.0.0.1:5432/aurameme_demo'
    assert not _owner_private_demo_enabled()
    assert not reviewed_source_rights(VALID_PRIVATE_DEMO_RIGHTS)


def test_production_rejects_private_demo():
    os.environ['AURAMEME_OWNER_MEME_DEMO'] = '1'
    os.environ['AUTH_ENVIRONMENT'] = 'production'
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://aurameme_demo:pass@127.0.0.1:5432/aurameme_demo'
    assert not _owner_private_demo_enabled()
    assert not reviewed_source_rights(VALID_PRIVATE_DEMO_RIGHTS)


def test_foreign_db_rejects_private_demo():
    os.environ['AURAMEME_OWNER_MEME_DEMO'] = '1'
    os.environ['AUTH_ENVIRONMENT'] = 'development'
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://user:pass@127.0.0.1:5432/production_database'
    assert not _owner_private_demo_enabled()
    assert not reviewed_source_rights(VALID_PRIVATE_DEMO_RIGHTS)


def test_remote_host_rejects_private_demo():
    os.environ['AURAMEME_OWNER_MEME_DEMO'] = '1'
    os.environ['AUTH_ENVIRONMENT'] = 'development'
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://aurameme_demo:pass@db.external-cloud.com:5432/aurameme_demo'
    assert not _owner_private_demo_enabled()
    assert not reviewed_source_rights(VALID_PRIVATE_DEMO_RIGHTS)


def test_malformed_proof_rejects_private_demo():
    os.environ['AURAMEME_OWNER_MEME_DEMO'] = '1'
    os.environ['AUTH_ENVIRONMENT'] = 'development'
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://aurameme_demo:pass@127.0.0.1:5432/aurameme_demo'

    # Missing evidence_sha256
    bad = dict(VALID_PRIVATE_DEMO_RIGHTS)
    bad['proof'] = dict(bad['proof'])
    del bad['proof']['evidence_sha256']
    assert not reviewed_source_rights(bad)

    # Wrong basis
    bad = dict(VALID_PRIVATE_DEMO_RIGHTS)
    bad['proof'] = dict(bad['proof'], basis='random_basis')
    assert not reviewed_source_rights(bad)


def test_sha_mismatch_rejects_private_demo():
    os.environ['AURAMEME_OWNER_MEME_DEMO'] = '1'
    os.environ['AUTH_ENVIRONMENT'] = 'development'
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://aurameme_demo:pass@127.0.0.1:5432/aurameme_demo'

    bad = dict(VALID_PRIVATE_DEMO_RIGHTS)
    bad['proof'] = dict(bad['proof'], artifact_sha256='0' * 64)
    assert not reviewed_source_rights(bad)


def test_unapproved_status_rejects_private_demo():
    os.environ['AURAMEME_OWNER_MEME_DEMO'] = '1'
    os.environ['AUTH_ENVIRONMENT'] = 'development'
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://aurameme_demo:pass@127.0.0.1:5432/aurameme_demo'

    bad = dict(VALID_PRIVATE_DEMO_RIGHTS, review_status='pending')
    assert not reviewed_source_rights(bad)


def test_valid_private_demo_on_valid_environment():
    os.environ['AURAMEME_OWNER_MEME_DEMO'] = '1'
    os.environ['AUTH_ENVIRONMENT'] = 'development'
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://aurameme_demo:pass@127.0.0.1:5432/aurameme_demo'
    assert _owner_private_demo_enabled()
    assert reviewed_source_rights(VALID_PRIVATE_DEMO_RIGHTS)


def test_mit_licensed_rights_always_valid_independent_of_demo_flag():
    os.environ.pop('AURAMEME_OWNER_MEME_DEMO', None)
    os.environ['AUTH_ENVIRONMENT'] = 'production'
    assert reviewed_source_rights(VALID_MIT_RIGHTS)
