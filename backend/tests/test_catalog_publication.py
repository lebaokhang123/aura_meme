"""Explicit isolated publication service with synthetic approved catalogs; no real media imported."""
from datetime import timedelta
from uuid import UUID,uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.catalog import CatalogManifest
from app.catalog_activation import activate_catalog,publish_cases
from app.vault_v1_policy import EFFECT_KEYS
from test_auth import auth,migrated,register
from test_catalog_rights import original_rights


def fixture_manifest():
    items=[]
    for kind in ('avatar','background'):
        for index,rarity in enumerate('DCBAS'):
            identity=uuid4()
            items.append({'id':str(identity),'slug':'publication-'+identity.hex,'kind':kind,'collection':'synthetic',
                'rarity':rarity,'file':identity.hex+'.png','sha256':identity.hex*2,'mime':'image/png',
                'name_vi':kind+' '+rarity,'name_review_status':'approved',
                'effect_key':EFFECT_KEYS[index] if kind=='background' else None,
                'source_rights':{key:value for key,value in original_rights(identity.hex*2).items() if key!='sha256'}})
    return CatalogManifest.model_validate({'version':1,'items':items})


@pytest.fixture
def catalog_auth(auth):
    # The auth fixture already verifies the reviewed candidate head.
    return auth


@pytest.mark.integration
def test_explicit_publication_is_idempotent_and_appends_new_immutable_versions(catalog_auth):
    client, c = catalog_auth
    owner=operator(client,c);manifest=fixture_manifest();now=client.app.state.auth.now()
    with Session(bind=c,join_transaction_mode='create_savepoint') as db,db.begin():
        activate_catalog(db,manifest,'a'*64,'a'*64,now,actor_id=owner)
        cases=publish_cases(db,manifest,'a'*64,'a'*64,owner,now)
        before=c.execute(text('SELECT id,odds_version,policy_id,status,created_at,active_from FROM case_loot_tables ORDER BY id')).all()
        assert publish_cases(db,manifest,'a'*64,'a'*64,owner,now+timedelta(seconds=1))==cases
        assert c.execute(text('SELECT id,odds_version,policy_id,status,created_at,active_from FROM case_loot_tables ORDER BY id')).all()==before
        assert c.scalar(text('SELECT count(*) FROM case_loot_tables'))==2
        assert c.scalar(text('SELECT count(*) FROM inventory_grants'))==c.scalar(text('SELECT count(*) FROM user_inventory'))==0
        activate_catalog(db,manifest,'b'*64,'b'*64,now+timedelta(seconds=2),actor_id=owner)
        assert publish_cases(db,manifest,'b'*64,'b'*64,owner,now+timedelta(seconds=2))==cases
        assert c.scalar(text('SELECT count(*) FROM case_loot_tables'))==4
        assert c.scalar(text('SELECT count(*) FROM reward_policy_versions'))==2
        assert c.execute(text('SELECT id,odds_version,policy_id,status,created_at,active_from FROM case_loot_tables WHERE odds_version=1 ORDER BY id')).all()==before
        with pytest.raises(ValueError,match='superseded'),db.begin_nested():
            activate_catalog(db,manifest,'a'*64,'a'*64,now+timedelta(seconds=3),actor_id=owner)
            publish_cases(db,manifest,'a'*64,'a'*64,owner,now+timedelta(seconds=3))
        assert c.scalar(text("SELECT count(*) FROM asset_items WHERE source_rights->>'manifest_sha256'=:digest"),{'digest':'b'*64})==10


@pytest.mark.integration
@pytest.mark.parametrize('failure',['unapproved','missing-rarity','wrong-effect','inactive-owner','wrong-digest','inactive-asset'])
def test_publication_refuses_incomplete_or_unapproved_data_without_partial_cases(catalog_auth,failure):
    client,c=catalog_auth;owner=operator(client,c);manifest=fixture_manifest();now=client.app.state.auth.now()
    with Session(bind=c,join_transaction_mode='create_savepoint') as db,db.begin():
        if failure=='unapproved':manifest.items[0].name_review_status='pending'
        elif failure=='missing-rarity':manifest.items.pop()
        elif failure=='wrong-effect':manifest.items[-1].effect_key='violet-base'
        try:
            with db.begin_nested():
                activate_catalog(db,manifest,'a'*64,'b'*64 if failure=='wrong-digest' else 'a'*64,now,actor_id=owner)
                if failure=='inactive-owner':
                    c.execute(text("UPDATE users SET status='locked' WHERE id=:id"),{'id':owner})
                if failure=='inactive-asset':
                    c.execute(text('UPDATE asset_items SET active=false WHERE id=:id'),{'id':manifest.items[0].id})
                publish_cases(db,manifest,'a'*64,'a'*64,owner,now)
        except ValueError:pass
        else:pytest.fail('Unsafe publication must reject')
        assert c.scalar(text('SELECT count(*) FROM case_definitions'))==0
        assert c.scalar(text('SELECT count(*) FROM case_loot_tables'))==0
        assert c.scalar(text('SELECT count(*) FROM reward_policy_versions'))==0
        assert c.scalar(text('SELECT count(*) FROM asset_items'))==0



def operator(client,connection):
    from app.models import Role,UserRole
    owner=UUID(register(client).json()['id'])
    role=uuid4()
    connection.execute(Role.__table__.insert().values(id=role,code='ADMIN',description='Synthetic publication operator'))
    connection.execute(UserRole.__table__.insert().values(user_id=owner,role_id=role,granted_at=client.app.state.auth.now()))
    return owner


def test_complete_background_subset_can_publish_without_unverified_avatars():
    from app.catalog_activation import approved_manifest
    manifest=fixture_manifest()
    manifest.items=[item for item in manifest.items if item.kind=='background']
    assert approved_manifest(manifest,'a'*64,'a'*64) is manifest
    manifest.items.pop()
    with pytest.raises(ValueError,match='five-rarity'):
        approved_manifest(manifest,'a'*64,'a'*64)


def test_legacy_approved_flags_do_not_authorize_unverified_avatar_bytes():
    from app.catalog_activation import approved_manifest
    manifest=fixture_manifest()
    manifest.items[0].source_rights.proof=None
    manifest.items[0].source_rights.author='Meme community, original authors unknown'
    manifest.items[0].source_rights.license='Unverified'
    with pytest.raises(ValueError,match='rights'):
        approved_manifest(manifest,'a'*64,'a'*64)


@pytest.mark.parametrize('value', ['g'*64,'A'*64,'not-a-digest'])
def test_explicit_approval_is_lowercase_sha256_not_arbitrary_equal_text(value):
    from app.catalog_activation import approved_manifest
    with pytest.raises(ValueError,match='approval'):
        approved_manifest(fixture_manifest(),value,value)


def test_operator_guard_refuses_nonadmin_before_any_catalog_changes(monkeypatch):
    from unittest.mock import Mock
    from sqlalchemy.engine import make_url
    import app.demo
    from app.catalog_activation import activation_guard
    db=Mock()
    db.connection.return_value.engine.url=make_url('postgresql+psycopg://aurameme_test:synthetic@127.0.0.1:5432/aurameme_test')
    db.execute.return_value.one.return_value=('aurameme_test','aurameme_test','public')
    db.scalar.side_effect=[False,None]
    monkeypatch.setattr(app.demo,'reviewed_demo_schema',lambda _:None)
    with pytest.raises(ValueError,match='ADMIN'):
        activation_guard(db,uuid4())
    db.add.assert_not_called()


def test_activation_requires_explicit_operator_before_loading_manifest(monkeypatch):
    import app.catalog_activation as activation
    monkeypatch.setattr(activation,'read_manifest',lambda _:pytest.fail('Missing actor must fail before reading assets'))
    with pytest.raises(SystemExit) as error:
        activation.main(['missing.json','--approved-manifest-sha256','a'*64,'--activate-isolated-catalog'])
    assert error.value.code==2


def test_demo_target_requires_explicit_validated_demo_mode():
    from app.catalog_activation import validate_target
    value='postgresql+psycopg://aurameme_demo:synthetic@127.0.0.1:5432/aurameme_demo'
    with pytest.raises(ValueError):validate_target(value)
    assert validate_target(value,allow_demo=True)=='aurameme_demo'
    with pytest.raises(ValueError):validate_target(value.replace('5432','55434'),allow_demo=True)


@pytest.mark.parametrize('change',['empty','duplicate'])
def test_mutated_manifest_identity_cannot_bypass_activation_review(change):
    from app.catalog_activation import approved_manifest
    manifest=fixture_manifest()
    if change=='empty':manifest.items=[]
    else:manifest.items.append(manifest.items[0])
    with pytest.raises(ValueError):approved_manifest(manifest,'a'*64,'a'*64)



def test_operator_cli_failure_does_not_log_private_driver_details(monkeypatch,capsys):
    import app.catalog_activation as activation
    def refuse(_):raise RuntimeError('PRIVATE_DRIVER_SECRET')
    monkeypatch.setattr(activation,'read_manifest',refuse)
    with pytest.raises(SystemExit) as error:
        activation.main(['manifest.json','--approved-manifest-sha256','a'*64,'--activate-isolated-catalog','--policy-owner',str(uuid4())])
    assert error.value.code==1
    output=capsys.readouterr()
    assert 'PRIVATE_DRIVER_SECRET' not in output.out+output.err



def test_activation_locks_cases_in_reader_order_before_asset_mutation(monkeypatch):
    from unittest.mock import Mock
    from sqlalchemy.engine import make_url
    import app.demo
    from app.catalog_activation import activate_catalog
    db=Mock();actor=uuid4();events=[]
    db.connection.return_value.engine.url=make_url('postgresql+psycopg://aurameme_test:synthetic@127.0.0.1:5432/aurameme_test')
    def execute(statement,*args):
        sql=str(statement)
        if 'LOCK TABLE asset_items' in sql:events.append('assets')
        result=Mock();result.one.return_value=('aurameme_test','aurameme_test','public')
        return result
    db.execute.side_effect=execute
    db.scalar.side_effect=[False,Mock()]+[None]*10
    def cases(statement):
        sql=str(statement)
        assert 'FOR UPDATE' in sql
        assert 'ORDER BY case_definitions.slug !=' in sql
        assert 'case_definitions.runtime_kind, case_definitions.id' in sql
        events.append('cases')
        return []
    db.scalars.side_effect=cases
    monkeypatch.setattr(app.demo,'reviewed_demo_schema',lambda _:None)
    manifest=fixture_manifest();manifest.items=[item for item in manifest.items if item.kind=='background']
    from datetime import datetime,timezone
    activate_catalog(db,manifest,'a'*64,'a'*64,datetime.now(timezone.utc),actor_id=actor)
    assert events==['cases','assets']
