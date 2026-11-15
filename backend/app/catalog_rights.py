"""Structured publication evidence; approval flags alone never establish media rights."""
import re
from sqlalchemy import Text, and_, case, cast, func, literal, or_, type_coerce
from sqlalchemy.dialects.postgresql import JSONB, array


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
    return and_(string(rights,'review_status') == 'approved',*strings,
        proof.has_all(array(sorted(PROOF_FIELDS))),proof.op('-')(array(sorted(PROOF_FIELDS))) == empty,
        string(proof,'artifact_sha256').op('~')(r'^[a-f0-9]{64}$'),string(proof,'evidence_sha256').op('~')(r'^[a-f0-9]{64}$'),
        string(proof,'artifact_sha256') == string(rights,'sha256'),string(proof,'source') == string(rights,'source'),
        string(proof,'license_id') == string(rights,'license'),
        func.strpos(string(proof,'copyright_notice'),string(rights,'author'))>0,
        func.strpos(string(rights,'attribution'),string(proof,'copyright_notice'))>0,
        or_(and_(string(proof,'basis') == 'licensed',string(proof,'license_id') == 'MIT',reference('source',HTTPS_REFERENCE),reference('license_url',HTTPS_REFERENCE)),
            and_(string(proof,'basis') == 'original',string(proof,'license_id') == 'LicenseRef-AuraMeme-Original',reference('source',ORIGINAL_REFERENCE),reference('license_url',ORIGINAL_REFERENCE))))
