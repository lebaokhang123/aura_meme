"""V1 rights proof is explicit and byte-bound; an approval flag alone is insufficient."""
import pytest
from app.catalog_rights import reviewed_source_rights
from test_auth import auth,migrated


def original_rights(digest='a'*64):
    source='aurameme://original/synthetic-fixture'
    notice='Copyright AuraMeme synthetic fixtures'
    return {'source':source,'author':'AuraMeme synthetic fixtures','license':'LicenseRef-AuraMeme-Original',
        'attribution':notice+'; generated wholly in tests, never released','review_status':'approved','sha256':digest,
        'proof':{'basis':'original','source':source,'license_id':'LicenseRef-AuraMeme-Original',
            'license_url':source+'/license','artifact_sha256':digest,'evidence_sha256':'b'*64,'copyright_notice':notice}}


def test_original_proof_binds_author_attribution_and_asset_bytes():
    assert reviewed_source_rights(original_rights())


@pytest.mark.parametrize('change',[
    {'review_status':'pending'},{'proof':None},{'license':'Unverified'},{'author':'Unknown'},
    {'sha256':'c'*64},{'attribution':'Owner approved community memes'},
])
def test_approval_flag_cannot_replace_evidence(change):
    rights=original_rights();rights.update(change)
    assert not reviewed_source_rights(rights)


@pytest.mark.parametrize('field,value',[
    ('evidence_sha256','missing'),('source','aurameme://original/different'),('license_id','Unverified'),
    ('license_url','https://unrelated.invalid/license'),('basis','owner-approved'),('copyright_notice','Missing author'),
])
def test_malformed_or_unbound_proof_is_refused(field,value):
    rights=original_rights();rights['proof'][field]=value
    assert not reviewed_source_rights(rights)


def test_licensed_proof_requires_actual_source_and_attribution():
    rights=original_rights()
    rights.update(source='https://lucianlabs.dev/uxui-prompt/#363',author='Seokwoooo',license='MIT',attribution='MIT License; Copyright (c) 2026 Seokwoooo; adapted for AuraMeme')
    rights['proof'].update(basis='licensed',source=rights['source'],license_id='MIT',license_url='https://github.com/Seokwoooo/lucian-uxui-prompt/blob/main/LICENSE',copyright_notice='Copyright (c) 2026 Seokwoooo')
    assert reviewed_source_rights(rights)
    rights['proof']['license_url']='http://unverified.invalid/LICENSE'
    assert not reviewed_source_rights(rights)


def test_legacy_approved_community_flags_remain_blocked():
    assert not reviewed_source_rights({'source':'Owner-provided community memes','author':'Meme community','license':'Unverified',
        'attribution':'Owner approved','review_status':'approved','sha256':'a'*64})


@pytest.mark.integration
def test_sql_proof_guard_matches_python_with_malformed_and_approved_values(auth):
    from sqlalchemy import literal,select
    from sqlalchemy.dialects.postgresql import JSONB
    from app.catalog_rights import reviewed_source_rights_sql
    _,connection=auth
    cases=[original_rights(),{},original_rights()|{'proof':None},original_rights()|{'proof':'invalid'},original_rights()|{'proof':[]},original_rights()|{'sha256':'c'*64},original_rights()|{'review_status':'pending'}]
    for rights in cases:
        actual=connection.scalar(select(reviewed_source_rights_sql(literal(rights,type_=JSONB))))
        assert bool(actual) == bool(reviewed_source_rights(rights))



def test_sql_proof_guard_uses_json_operators_on_bound_expressions():
    from sqlalchemy import literal,select
    from sqlalchemy.dialects.postgresql import JSONB,dialect
    from app.catalog_rights import reviewed_source_rights_sql
    statement=str(select(reviewed_source_rights_sql(literal({},type_=JSONB))).compile(dialect=dialect()))
    assert '::JSONB[' not in statement
    assert ' -> ' in statement and ' ->> ' in statement
