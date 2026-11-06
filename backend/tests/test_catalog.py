"""Catalog bytes are self-created fixtures; no asset publication or rights approval."""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
from uuid import uuid4

from PIL import Image
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_auth import auth,migrated


@pytest.fixture
def package(tmp_path):
    file=tmp_path/'synthetic.png'
    Image.new('RGB',(8,8),(31,23,67)).save(file)
    item={'id':str(uuid4()),'slug':'synthetic-icon','kind':'icon','collection':'test-only','rarity':'D',
          'file':'synthetic.png','mime':'image/png','sha256':sha256(file.read_bytes()).hexdigest(),
          'source_rights':{'source':'self-created test fixture','author':'automated test','license':'CC0-1.0',
                           'attribution':'Synthetic fixture; not approved for release','review_status':'pending'}}
    manifest={'version':1,'items':[item]}
    path=tmp_path/'catalog.json';path.write_text(json.dumps(manifest),encoding='utf-8')
    return path,manifest


def test_manifest_validates_bytes_without_changing_them(package):
    from app.catalog import read_manifest
    path,body=package;before={p.name:p.read_bytes() for p in path.parent.iterdir()}
    result=read_manifest(path)
    assert result.version == 1 and str(result.items[0].id)==body['items'][0]['id']
    assert {p.name:p.read_bytes() for p in path.parent.iterdir()}==before


@pytest.mark.parametrize('field,value',[
 ('sha256','0'*64),('mime','image/svg+xml'),('file','../synthetic.png'),('file','C:/secret.png'),
 ('kind','generator'),('rarity','SSS'),('slug','Bad slug'),('active',True),('media_url','https://example.test/evil'),
])
def test_rejects_invalid_or_unrequested_fields(package,field,value):
    from app.catalog import read_manifest
    path,body=package;body['items'][0][field]=value;path.write_text(json.dumps(body),encoding='utf-8')
    with pytest.raises(ValueError):read_manifest(path)


@pytest.mark.parametrize('variant',['id','slug','sha256'])
def test_rejects_duplicate_identity_or_bytes(package,variant):
    from app.catalog import read_manifest
    path,body=package;other=deepcopy(body['items'][0])
    if variant!='id':other['id']=str(uuid4())
    if variant!='slug':other['slug']='another-icon'
    body['items'].append(other);path.write_text(json.dumps(body),encoding='utf-8')
    with pytest.raises(ValueError,match='[Dd]uplicate'):read_manifest(path)


@pytest.mark.parametrize('field',['source','author','license','attribution','review_status'])
def test_requires_rights_metadata(package,field):
    from app.catalog import read_manifest
    path,body=package;del body['items'][0]['source_rights'][field];path.write_text(json.dumps(body),encoding='utf-8')
    with pytest.raises(ValueError):read_manifest(path)


def test_declared_image_must_actually_be_supported_image(package):
    from app.catalog import read_manifest
    path,body=package;data=b'<html>not an image</html>';(path.parent/'synthetic.png').write_bytes(data)
    body['items'][0]['sha256']=sha256(data).hexdigest();path.write_text(json.dumps(body),encoding='utf-8')
    with pytest.raises(ValueError):read_manifest(path)


def test_manifest_rejects_duplicate_json_keys(package):
    from app.catalog import read_manifest
    path,_=package;path.write_text('{"version":1,"version":2,"items":[]}',encoding='utf-8')
    with pytest.raises(ValueError):read_manifest(path)


@pytest.mark.integration
def test_import_draft_is_idempotent_inactive_and_never_overwrites(auth,package):
    from app.catalog import read_manifest,import_draft
    _,connection=auth;manifest=read_manifest(package[0]);now=datetime.now(timezone.utc)
    with Session(bind=connection,join_transaction_mode='create_savepoint') as db:
        assert import_draft(db,manifest,now)==1
        assert import_draft(db,manifest,now)==0
        row=db.execute(text('SELECT active,source_rights FROM asset_items')).one()
        assert row.active is False and row.source_rights['review_status']=='pending'
        assert row.source_rights['sha256']==manifest.items[0].sha256
        changed=manifest.model_copy(deep=True);changed.items[0].rarity='C'
        with pytest.raises(ValueError,match='[Cc]onflict'):import_draft(db,changed,now)
        assert db.scalar(text('SELECT rarity FROM asset_items'))=='D'


@pytest.mark.integration
def test_new_version_preserves_existing_identity_and_rejects_cross_manifest_hash_duplicate(auth,package):
    from app.catalog import read_manifest,import_draft
    _,connection=auth;m=read_manifest(package[0]);now=datetime.now(timezone.utc)
    with Session(bind=connection,join_transaction_mode='create_savepoint') as db:
        import_draft(db,m,now)
        newer=m.model_copy(deep=True);newer.version=2
        assert import_draft(db,newer,now)==0
        other=newer.model_copy(deep=True);other.items[0].id=uuid4();other.items[0].slug='other'
        with pytest.raises(ValueError,match='[Dd]uplicate'):import_draft(db,other,now)
        assert db.scalar(text('SELECT count(*) FROM asset_items'))==1


@pytest.mark.integration
def test_import_insert_failure_is_atomic(auth,package):
    from app.catalog import read_manifest,import_draft
    from sqlalchemy.exc import IntegrityError
    _,connection=auth
    path,body=package
    Image.new('RGB',(8,8),(4,5,6)).save(path.parent/'other.png')
    second=deepcopy(body['items'][0]);second.update(id=str(uuid4()),slug='reject-me',file='other.png',sha256=sha256((path.parent/'other.png').read_bytes()).hexdigest())
    body['items'].append(second);path.write_text(json.dumps(body),encoding='utf-8')
    m=read_manifest(path);now=datetime.now(timezone.utc)
    # A real PostgreSQL trigger rejects insertion, not an in-memory DB mock.
    connection.exec_driver_sql("CREATE FUNCTION catalog_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.slug='reject-me' THEN RAISE EXCEPTION 'fixture failure' USING ERRCODE='23514'; END IF; RETURN NEW; END $$")
    connection.exec_driver_sql('CREATE TRIGGER catalog_fail BEFORE INSERT ON asset_items FOR EACH ROW EXECUTE FUNCTION catalog_fail()')
    with Session(bind=connection,join_transaction_mode='create_savepoint') as db:
        with pytest.raises(IntegrityError):import_draft(db,m,now)
        assert db.scalar(text('SELECT count(*) FROM asset_items'))==0


@pytest.mark.integration
@pytest.mark.parametrize('statement',[
    "UPDATE asset_items SET active=true",
    "UPDATE asset_items SET source_rights='[]'::jsonb",
    "UPDATE asset_items SET kind='sound'",
    "UPDATE asset_items SET rarity='SSS'",
    "UPDATE asset_items SET slug=''",
])
def test_database_rejects_invalid_catalog(auth,package,statement):
    from app.catalog import read_manifest,import_draft
    from sqlalchemy.exc import IntegrityError
    _,connection=auth
    with Session(bind=connection,join_transaction_mode='create_savepoint') as db:
        import_draft(db,read_manifest(package[0]),datetime.now(timezone.utc))
        with pytest.raises(IntegrityError),db.begin_nested():db.execute(text(statement))
        assert db.scalar(text('SELECT count(*) FROM asset_items'))==1


def test_hardlinked_catalog_bytes_are_rejected(package):
    import os
    from app.catalog import read_manifest
    path,_=package
    os.link(path.parent/'synthetic.png',path.parent/'linked.png')
    with pytest.raises(ValueError):read_manifest(path)
