"""Structured publication evidence; approval flags alone never establish media rights."""
import os
import re
from sqlalchemy import Text, and_, case, cast, func, literal, or_, type_coerce
from sqlalchemy.dialects.postgresql import JSONB, array

# AURAMEME_OWNER_PRIVATE_MEME_DEMO_V1
# Owner attestation is NOT creator permission. This flag must never be enabled
# in public deployments. SQL additionally requires the dedicated local demo DB.
DEMO_AUTHOR = 'Unidentified original meme creators'
DEMO_SOURCE = 'Owner-collected internet memes; original source and author unverified'
DEMO_LICENSE = 'LicenseRef-Owner-Private-Demo-Only'
DEMO_PREFIX = 'aurameme://private-demo/owner-statement/'
DEMO_NOTICE = 'Unidentified original meme creators; no rights verification'

def _owner_private_demo_enabled():
    """Fail-closed guard: only permitted on verified local demo or isolated clone test environments."""
    if os.environ.get('AURAMEME_OWNER_MEME_DEMO') not in {'1', 'true'}:
        return False
    auth_env = os.environ.get('AUTH_ENVIRONMENT', '').lower()
    if auth_env not in {'development', 'test', 'local'}:
        return False
    # Never allow on production or staging
    if os.environ.get('ENVIRONMENT', '').lower() in {'production', 'staging'}:
        return False
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('TEST_DATABASE_URL') or ''
    # Database must be dedicated demo or isolated verification clone
    if not any(authorized_db in db_url for authorized_db in ('aurameme_demo', 'aurameme_vault_verify', 'aurameme_test')):
        return False
    # Database host must be strictly loopback
    if not any(h in db_url for h in ('localhost', '127.0.0.1', '::1')):
        return False
    return True

def _owner_private_demo_sql(rights):
    # Only a SELECT against the dedicated demo database (or verified isolated test clone) may see these items.
    source = lambda document, field: type_coerce(document.op('->>')(field), Text)
    proof = type_coerce(rights.op('->')('proof'), JSONB)
    fields = array(sorted(PROOF_FIELDS))
    return and_(
        func.current_database().in_(['aurameme_demo', 'aurameme_vault_verify']),
        func.current_user() == 'aurameme_demo',
        func.jsonb_typeof(rights) == 'object',
        func.jsonb_typeof(rights.op('->')('proof')) == 'object',
        proof.has_all(fields),
        proof.op('-')(fields) == cast(literal('{}'), JSONB),
        source(rights, 'review_status') == 'approved',
        source(rights, 'source') == DEMO_SOURCE,
        source(rights, 'author') == DEMO_AUTHOR,
        source(rights, 'license') == DEMO_LICENSE,
        source(rights, 'attribution').op('~')('^Private demo only;'),
        source(proof, 'basis') == 'owner_private_demo',
        source(proof, 'source') == source(rights, 'source'),
        source(proof, 'license_id') == source(rights, 'license'),
        source(proof, 'license_url') == literal(DEMO_PREFIX) + source(proof, 'evidence_sha256'),
        source(proof, 'copyright_notice') == DEMO_NOTICE,
        source(proof, 'artifact_sha256') == source(rights, 'sha256'),
        source(proof, 'artifact_sha256').op('~')(r'^[a-f0-9]{64}$'),
        source(proof, 'evidence_sha256').op('~')(r'^[a-f0-9]{64}$'),
    )

SHA256 = re.compile(r'^[a-f0-9]{64}$')
HTTPS_REFERENCE = r'https://[A-Za-z0-9.-]+(?::[0-9]+)?(?:[/?#][^\s]*)?'
ORIGINAL_REFERENCE = r'aurameme://original/[^\s]+'
PROOF_FIELDS = {'basis','source','license_id','license_url','artifact_sha256','evidence_sha256','copyright_notice'}


def reviewed_source_rights(rights):
    if not isinstance(rights,dict) or rights.get('review_status') != 'approved':
        return False
    if any(not isinstance(rights.get(field),str) or not rights[field].strip() for field in ('source','author','license','attribution')):
        return False
    proof = rights.get('proof')
    if not isinstance(proof,dict) or set(proof) != PROOF_FIELDS or any(not isinstance(value,str) or not value.strip() for value in proof.values()):
        return False
    if (not SHA256.fullmatch(proof['artifact_sha256']) or not SHA256.fullmatch(proof['evidence_sha256'])
            or proof['artifact_sha256'] != rights.get('sha256') or proof['source'] != rights['source']
            or proof['license_id'] != rights['license'] or rights['author'] not in proof['copyright_notice']
            or proof['copyright_notice'] not in rights['attribution']):
        return False
    if proof['basis'] == 'licensed':
        return proof['license_id'] == 'MIT' and all(re.fullmatch(HTTPS_REFERENCE,value) for value in (proof['source'],proof['license_url']))
    if proof['basis'] == 'original':
        return proof['license_id'] == 'LicenseRef-AuraMeme-Original' and all(re.fullmatch(ORIGINAL_REFERENCE,value) for value in (proof['source'],proof['license_url']))
    if proof['basis'] == 'author_permission':
        # Explicit author permission only; never mislabel collected memes as MIT/original.
        # HTTPS may point to posted permission terms. A private permission record
        # may use aurameme://permission/<evidence sha256>, stored separately by Owner.
        return (proof['license_id'] == 'LicenseRef-Author-Permission'
                and rights['author'] != 'Unknown — Owner review required'
                and re.fullmatch(HTTPS_REFERENCE, proof['source']) is not None
                and (re.fullmatch(HTTPS_REFERENCE, proof['license_url']) is not None
                     or proof['license_url'] == 'aurameme://permission/' + proof['evidence_sha256']))
    if proof['basis'] == 'owner_private_demo':
        # review_status=approved here means Owner approved ONLY private demo use.
        # No claim about the original author's permission is made.
        return (_owner_private_demo_enabled()
                and rights['source'] == DEMO_SOURCE
                and rights['author'] == DEMO_AUTHOR
                and proof['license_id'] == DEMO_LICENSE
                and proof['license_url'] == DEMO_PREFIX + proof['evidence_sha256']
                and proof['copyright_notice'] == DEMO_NOTICE
                and rights['attribution'].startswith('Private demo only;'))
    return False


def reviewed_source_rights_sql(rights):
    """The same proof guard before SQL pagination/counts; malformed proof is fail-closed."""
    def entry(document,key):
        return document.op('->')(key)

    def string(document,key):
        return type_coerce(document.op('->>')(key),Text)

    empty = cast(literal('{}'),JSONB)
    supplied_proof = entry(rights,'proof')
    proof = case((func.jsonb_typeof(supplied_proof) == 'object',supplied_proof),else_=empty)
    strings = [and_(func.jsonb_typeof(entry(rights,field)) == 'string',string(rights,field).op('~')(r'\S'))
        for field in ('source','author','license','attribution')]
    strings += [and_(func.jsonb_typeof(entry(proof,field)) == 'string',string(proof,field).op('~')(r'\S')) for field in PROOF_FIELDS]
    reference = lambda field,pattern:string(proof,field).op('~')('^'+pattern+'$')
    base = and_(string(rights,'review_status') == 'approved',*strings,
        proof.has_all(array(sorted(PROOF_FIELDS))),proof.op('-')(array(sorted(PROOF_FIELDS))) == empty,
        string(proof,'artifact_sha256').op('~')(r'^[a-f0-9]{64}$'),string(proof,'evidence_sha256').op('~')(r'^[a-f0-9]{64}$'),
        string(proof,'artifact_sha256') == string(rights,'sha256'),string(proof,'source') == string(rights,'source'),
        string(proof,'license_id') == string(rights,'license'),
        func.strpos(string(proof,'copyright_notice'),string(rights,'author'))>0,
        func.strpos(string(rights,'attribution'),string(proof,'copyright_notice'))>0,
        or_(and_(string(proof,'basis') == 'licensed',string(proof,'license_id') == 'MIT',reference('source',HTTPS_REFERENCE),reference('license_url',HTTPS_REFERENCE)),
            and_(string(proof,'basis') == 'original',string(proof,'license_id') == 'LicenseRef-AuraMeme-Original',reference('source',ORIGINAL_REFERENCE),reference('license_url',ORIGINAL_REFERENCE)),
            and_(string(proof,'basis') == 'author_permission',
                 string(proof,'license_id') == 'LicenseRef-Author-Permission',
                 string(rights,'author') != 'Unknown — Owner review required',
                 reference('source',HTTPS_REFERENCE),
                 or_(reference('license_url',HTTPS_REFERENCE),
                     string(proof,'license_url') == (literal('aurameme://permission/') + string(proof,'evidence_sha256'))))))

    if not _owner_private_demo_enabled():
        return base
    return or_(base, _owner_private_demo_sql(rights))
