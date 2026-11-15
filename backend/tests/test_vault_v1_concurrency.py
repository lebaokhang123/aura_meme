"""Explicit opt-in Vault races on fresh port 55435; retain all synthetic DB/media evidence."""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import tempfile
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.main import app
from app.models import AuraLedger, Base, CaseOpen, InventoryGrant, Role, UserInventory, UserProgress, UserRole, Wallet, WalletTransaction
from app.vault_v1_policy import EFFECT_KEYS
from schema_guard import assert_auxiliary_objects
from test_aura_v1_concurrency import ORIGIN, csrf, mutation, race
from vault_test_rights import synthetic_rights

PASSWORD = 'Synthetic retained Vault fixture password!'


def vault_target(value, token):
    try:
        target, run = make_url(value), UUID(token)
        safe = (target.drivername == 'postgresql+psycopg' and target.host in {'127.0.0.1','localhost','::1'}
            and target.port == 55435 and target.database == 'aurameme_e2e' and target.username == 'aurameme_e2e_app'
            and bool(target.password) and not target.query and run.version == 4 and str(run) == token)
    except (ArgumentError, ValueError, TypeError, AttributeError):
        safe = False
    if not safe:
        pytest.fail('Vault races require exact dedicated loopback E2E role/database at port 55435 and a fresh UUID4 run token', pytrace=False)
    return target, run


@pytest.mark.parametrize('port,database,role,host,query,token', [
    (55434,'aurameme_e2e','aurameme_e2e_app','127.0.0.1','',str(uuid4())),
    (5432,'aurameme_test','aurameme_test','127.0.0.1','',str(uuid4())),
    (55435,'aurameme_demo','aurameme_e2e_app','127.0.0.1','',str(uuid4())),
    (55435,'aurameme_e2e','postgres','127.0.0.1','',str(uuid4())),
    (55435,'aurameme_e2e','aurameme_e2e_app','remote.invalid','',str(uuid4())),
    (55435,'aurameme_e2e','aurameme_e2e_app','127.0.0.1','?options=unsafe',str(uuid4())),
    (55435,'aurameme_e2e','aurameme_e2e_app','127.0.0.1','','reused-run'),
])
def test_vault_race_guard_rejects_wrong_targets(port,database,role,host,query,token):
    value=f'postgresql+psycopg://{role}:synthetic@{host}:{port}/{database}{query}'
    with pytest.raises(pytest.fail.Exception, match='dedicated loopback'):
        vault_target(value,token)


def manifest_package(root):
    """Generate original test bytes and keep their exact reviewed manifest outside Git."""
    from app.catalog import read_manifest
    package, catalog = root/'package', root/'catalog'
    package.mkdir(); catalog.mkdir(); (root/'uploads').mkdir()
    items=[]
    for number,(kind,rarity) in enumerate((kind,rarity) for kind in ('avatar','background') for rarity in 'DCBAS'):
        identity=uuid4()
        source=package/(identity.hex+'.png')
        Image.new('RGBA',(8,8),(20+number*17,70,140,255)).save(source)
        data=source.read_bytes(); digest=sha256(data).hexdigest()
        (catalog/(digest+'.png')).write_bytes(data)
        rights=synthetic_rights(digest)
        items.append({'id':str(identity),'slug':'vault-race-'+identity.hex,'kind':kind,'collection':'retained-synthetic',
            'rarity':rarity,'file':source.name,'sha256':digest,'mime':'image/png','name_vi':'Synthetic '+kind+' '+rarity,
            'name_review_status':'approved','byte_size':len(data),'width':8,'height':8,
            'effect_key':EFFECT_KEYS['DCBAS'.index(rarity)] if kind=='background' else None,
            'source_rights':{key:value for key,value in rights.items() if key not in {'sha256','mime'}}})
    path=package/'manifest.json'
    path.write_text(json.dumps({'version':1,'items':items},sort_keys=True),encoding='utf-8')
    return read_manifest(path),sha256(path.read_bytes()).hexdigest(),catalog


@pytest.fixture(scope='module')
def vault_e2e():
    if os.environ.get('VAULT_V1_E2E_OPT_IN')!='1':
        pytest.skip('Retained Vault races require VAULT_V1_E2E_OPT_IN=1; no database accessed')
    target,run=vault_target(os.environ.get('VAULT_V1_E2E_DATABASE_URL',''),os.environ.get('VAULT_V1_E2E_RUN_TOKEN',''))
    tag='vault_v1_race_'+run.hex
    engine=create_engine(target,hide_parameters=True,connect_args={'connect_timeout':3,'application_name':tag,
        'options':'-c statement_timeout=18000 -c lock_timeout=12000'})
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            assert tuple(connection.execute(text('SELECT current_database(),current_user,current_schema()')).one())==('aurameme_e2e','aurameme_e2e_app','public')
            assert not connection.scalar(text('SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname=current_user'))
            assert connection.scalar(text('SELECT inet_server_port()'))==5432  # Verified container mapping: 127.0.0.1:55435 -> container 5432.
            assert not connection.scalar(text('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()')),'Dedicated database already has other sessions'
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0012_aura_v1'
            from app.demo import reviewed_demo_schema
            reviewed_demo_schema(connection); assert_auxiliary_objects(connection)
            assert not connection.scalar(text("SELECT count(*) FROM pg_policies WHERE schemaname='public'"))
            for table in Base.metadata.sorted_tables:
                assert connection.scalar(select(func.count()).select_from(table))==0,'Existing business evidence; refuse without cleanup'
        root=Path(tempfile.mkdtemp(prefix='aurameme-vault-race-'+run.hex+'-'))
        manifest,digest,catalog=manifest_package(root)
        (root/'evidence.json').write_text(json.dumps({'run_token':str(run),'catalog_root':str(catalog),'manifest_sha256':digest}),encoding='utf-8')
        with ExitStack() as stack:
            patch=stack.enter_context(pytest.MonkeyPatch.context())
            for key,value in {'DATABASE_URL':target.render_as_string(hide_password=False),'AUTH_SIGNING_KEY':secrets.token_hex(32),
                'AUTH_ENVIRONMENT':'production','AUTH_ALLOWED_ORIGINS':'["https://testserver"]','VAULT_RUNTIME_ENABLED':'true',
                'CATALOG_STORAGE_ROOT':str(catalog),'MEDIA_STORAGE_ROOT':str(root/'uploads')}.items():
                patch.setenv(key,value)
            stack.enter_context(TestClient(app,base_url=ORIGIN))
            app.state.auth_session_factory=lambda:Session(engine)
            clock=[datetime.now(timezone.utc)]
            app.state.auth.now=lambda:clock[0]
            sequence=0

            def account():
                nonlocal sequence
                sequence+=1
                client=TestClient(app,base_url=ORIGIN,client=('192.0.2.'+str(sequence),50000),raise_server_exceptions=False)
                stack.callback(client.close)
                name='vv1_'+run.hex[:8]+'_'+uuid4().hex[:12]
                body={'username':name,'email':name+'@example.com','password':PASSWORD,'display_name':'Synthetic Vault race'}
                response=mutation(client,'POST','/auth/register',body)
                assert response.status_code==201,response.text
                owner=UUID(response.json()['id'])
                response=mutation(client,'POST','/auth/login',{'email':body['email'],'password':PASSWORD})
                assert response.status_code==200,response.text
                return client,owner

            admin,admin_id=account()
            with Session(engine) as db,db.begin():
                from app.aura_runtime import publish_v1
                from app.catalog_activation import activate_catalog,publish_cases
                role=uuid4(); db.add(Role(id=role,code='ADMIN',description='Fresh Vault race operator')); db.flush()
                db.add(UserRole(user_id=admin_id,role_id=role,granted_at=clock[0])); db.flush()
                publish_v1(db,admin_id,clock[0])
                activate_catalog(db,manifest,digest,digest,clock[0],actor_id=admin_id)
                cases=publish_cases(db,manifest,digest,digest,admin_id,clock[0])
            category=mutation(admin,'POST','/admin/categories',{'name':'Retained Vault race','slug':'vv1-'+run.hex})
            assert category.status_code==201,category.text
            yield SimpleNamespace(engine=engine,tag=tag,account=account,clock=clock,cases=cases,category=category.json()['id'],root=root)
    except SQLAlchemyError:
        pytest.fail('Dedicated Vault database operation failed; connection details suppressed',pytrace=False)
    finally:
        engine.dispose()  # Retain every committed row, immutable receipt, manifest and original fixture image.


def opening(client,case,key,token=None):
    return client.post('/api/v1/vault/cases/'+str(case)+'/open',headers={
        'Origin':ORIGIN,'X-CSRF-Token':token or csrf(client),'Idempotency-Key':key})


def owned_counts(fixture,owner):
    with Session(fixture.engine) as db:
        return tuple(db.scalar(select(func.count()).select_from(model).where(model.user_id==owner))
            for model in (CaseOpen,InventoryGrant,UserInventory,AuraLedger,WalletTransaction,Wallet))


def clone(client):
    copy=TestClient(app,base_url=ORIGIN,client=('192.0.2.220',50000),raise_server_exceptions=False)
    copy.cookies.update(client.cookies)
    return copy


@pytest.mark.integration
def test_parallel_same_key_commits_one_receipt_and_one_grant(vault_e2e):
    client,owner=vault_e2e.account(); token=csrf(client)
    second=clone(client)
    try:
        responses=race(vault_e2e,lambda:opening(client,vault_e2e.cases['avatar'],'retained-same-key-001',token),
            lambda:opening(second,vault_e2e.cases['avatar'],'retained-same-key-001',token))
        assert [response.status_code for response in responses]==[200,200]
        assert len({response.json()['open_id'] for response in responses})==1
        assert sorted(response.json()['already_processed'] for response in responses)==[False,True]
    finally:second.close()
    assert owned_counts(vault_e2e,owner)==(1,1,1,0,0,0)


@pytest.mark.integration
def test_parallel_distinct_keys_serialize_into_backend_cooldown(vault_e2e):
    client,owner=vault_e2e.account(); token=csrf(client)
    second=clone(client)
    try:
        responses=race(vault_e2e,lambda:opening(client,vault_e2e.cases['avatar'],'retained-different-001',token),
            lambda:opening(second,vault_e2e.cases['background'],'retained-different-002',token))
        assert [response.status_code for response in responses]==[200,429]
        assert responses[1].json()['error']['code']=='COOLDOWN'
        assert responses[1].headers['Retry-After']=='2'
    finally:second.close()
    assert owned_counts(vault_e2e,owner)==(1,1,1,0,0,0)


@pytest.mark.integration
def test_tenth_success_requires_five_seconds_from_server_history(vault_e2e):
    client,owner=vault_e2e.account()
    for number in range(10):
        if number:vault_e2e.clock[0]+=timedelta(seconds=2)
        response=opening(client,vault_e2e.cases['avatar' if number%2 else 'background'],f'retained-ten-{number:03}')
        assert response.status_code==200,response.text
    due=datetime.fromisoformat(response.json()['next_open_at'])
    assert due==vault_e2e.clock[0]+timedelta(seconds=5)
    vault_e2e.clock[0]+=timedelta(seconds=2)
    blocked=opening(client,vault_e2e.cases['background'],'retained-after-ten-011')
    assert blocked.status_code==429 and blocked.headers['Retry-After']=='3'
    assert blocked.json()['error']['details']['next_open_at']==due.isoformat().replace('+00:00','Z')
    vault_e2e.clock[0]=due
    assert opening(client,vault_e2e.cases['background'],'retained-after-ten-011').status_code==200
    counts=owned_counts(vault_e2e,owner)
    assert counts[:2]==(11,11) and counts[3:]==(0,0,0)
    with Session(vault_e2e.engine) as db:
        assert db.get(UserProgress,owner).aura_xp_earned==0
        assert db.scalar(select(func.sum(UserInventory.quantity)).where(UserInventory.user_id==owner))==11


@pytest.mark.integration
def test_failed_grant_rolls_back_opening_and_same_key_can_retry(vault_e2e,monkeypatch):
    import app.vault_runtime as runtime
    client,owner=vault_e2e.account()
    def reject(*args,**kwargs):raise ValueError('Synthetic grant failure before inventory flush')
    with monkeypatch.context() as patch:
        patch.setattr(runtime,'_grant_item',reject)
        response=opening(client,vault_e2e.cases['avatar'],'retained-failed-grant-001')
        assert response.status_code==503,response.text
    assert owned_counts(vault_e2e,owner)==(0,0,0,0,0,0)
    assert opening(client,vault_e2e.cases['avatar'],'retained-failed-grant-001').status_code==200
    assert owned_counts(vault_e2e,owner)==(1,1,1,0,0,0)


@pytest.mark.integration
def test_duplicate_reward_increments_quantity_without_aura_or_wallet(vault_e2e,monkeypatch):
    import app.vault_runtime as runtime
    from app.vault import draw
    client,owner=vault_e2e.account()
    monkeypatch.setattr(runtime,'draw',lambda pool,randbelow:draw(pool,randbelow=lambda n:0))
    first=opening(client,vault_e2e.cases['avatar'],'retained-duplicate-001')
    assert first.status_code==200,first.text
    vault_e2e.clock[0]+=timedelta(seconds=2)
    second=opening(client,vault_e2e.cases['avatar'],'retained-duplicate-002')
    assert second.status_code==200,second.text
    assert first.json()['reward']['id']==second.json()['reward']['id']
    assert owned_counts(vault_e2e,owner)==(2,2,1,0,0,0)
    with Session(vault_e2e.engine) as db:
        assert db.scalar(select(UserInventory.quantity).where(UserInventory.user_id==owner))==2
        assert db.get(UserProgress,owner).aura_xp_earned==0


@pytest.mark.integration
def test_owned_avatar_and_meme_social_rewards_preserve_aura_reversals(vault_e2e):
    actor,actor_id=vault_e2e.account(); author,author_id=vault_e2e.account()
    response=opening(actor,vault_e2e.cases['avatar'],'retained-owned-avatar-001')
    assert response.status_code==200,response.text
    asset=response.json()['reward']['id']
    assert mutation(actor,'PUT','/inventory/equipment/avatar',{'asset_id':asset}).status_code==200
    assert actor.get('/api/v1/users/me').json()['avatar_url']=='/api/v1/catalog/assets/'+asset
    assert actor.get('/api/v1/catalog/assets/'+asset).status_code==200
    assert mutation(author,'PUT','/inventory/equipment/avatar',{'asset_id':asset}).status_code==404
    post=mutation(author,'POST','/posts',{'content':'Retained Aura social regression','category_id':vault_e2e.category,'status':'published','request_id':str(uuid4())})
    assert post.status_code==201,post.text
    post_id=post.json()['id']; path=f'/posts/{post_id}/reactions'; meme={'reaction_type':'meme','meme_asset_id':asset}
    for body in (meme,meme,{'reaction_type':'like'},meme):
        assert mutation(actor,'PUT',path,body).status_code==200
    with Session(vault_e2e.engine) as db:
        assert db.get(UserProgress,actor_id).aura_xp_earned==1
        assert db.get(UserProgress,author_id).aura_xp_earned==12
    assert mutation(actor,'DELETE',path).status_code==204
    assert mutation(actor,'PUT',path,meme).status_code==200
    with Session(vault_e2e.engine) as db:
        assert db.get(UserProgress,actor_id).aura_xp_earned==0
        assert db.get(UserProgress,author_id).aura_xp_earned==10
        assert db.scalar(select(func.count()).select_from(AuraLedger).where(AuraLedger.source_post_id==UUID(post_id),AuraLedger.event_type=='reversal'))==2
    assert mutation(author,'DELETE','/posts/'+post_id).status_code==204
    with Session(vault_e2e.engine) as db:
        assert db.get(UserProgress,author_id).aura_xp_earned==0
        assert db.scalar(select(UserInventory.quantity).where(UserInventory.user_id==actor_id,UserInventory.asset_id==UUID(asset)))==1
        assert db.scalar(select(func.count()).select_from(WalletTransaction))==0
