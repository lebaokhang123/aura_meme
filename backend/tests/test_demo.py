"""Local demo boundaries; no public bootstrap route or default account."""
import os
from pathlib import Path
from uuid import uuid4

import pytest

from app import demo
from app.config import ConfigurationError


@pytest.mark.parametrize('url', [
    'postgresql+psycopg://aurameme_demo:p@127.0.0.1:5432/aurameme_dev',
    'postgresql+psycopg://postgres:p@127.0.0.1:5432/aurameme_demo',
    'postgresql+psycopg://aurameme_demo:p@example.com:5432/aurameme_demo',
    'postgresql+psycopg://aurameme_demo:p@127.0.0.1:5433/aurameme_demo',
    'postgresql+psycopg://aurameme_demo:p@127.0.0.1:5432/aurameme_demo?options=bad',
    'CANARY_SECRET',
])
def test_demo_url_rejects_other_targets_without_values(url):
    with pytest.raises(ConfigurationError) as error:
        demo.validate_demo_url(url)
    assert url not in str(error.value) and 'CANARY_SECRET' not in str(error.value)


def test_missing_demo_config_never_falls_back_to_development(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, 'DEMO_ROOT', tmp_path)
    with pytest.raises(ConfigurationError):
        demo.demo_environment()


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, 'DEMO_ROOT', tmp_path)
    values = dict(DATABASE_URL='postgresql+psycopg://aurameme_demo:local@127.0.0.1:5432/aurameme_demo',
        DB_CONNECT_TIMEOUT='5', AUTH_SIGNING_KEY='Synthetic-key-for-unit-tests-only-123456789',
        AUTH_ENVIRONMENT='development', AUTH_ALLOWED_ORIGINS='["http://localhost:5173"]',
        MEDIA_STORAGE_ROOT=str(tmp_path/'media'), CATALOG_STORAGE_ROOT=str(tmp_path/'catalog'))
    from dotenv import set_key
    for key, value in values.items():
        set_key(tmp_path/'.env', key, value)
    return tmp_path, values


def test_demo_config_is_complete_and_overrides_process(config, monkeypatch):
    _, values = config
    monkeypatch.setenv('DATABASE_URL', 'CANARY_SECRET')
    monkeypatch.setenv('TEST_DATABASE_URL', 'CANARY_SECRET')
    monkeypatch.setenv('AUTH_SIGNING_KEY', 'CANARY_SECRET')
    monkeypatch.setenv('AUTH_UNKNOWN', 'CANARY_SECRET')
    monkeypatch.setenv('DB_CONNECT_TIMEOUT', 'CANARY_SECRET')
    with monkeypatch.context() as scoped:
        scoped.setattr(os, 'environ', os.environ.copy())
        demo.activate_demo()
        assert all(os.environ[k] == v for k, v in values.items())
        assert 'TEST_DATABASE_URL' not in os.environ and 'AUTH_UNKNOWN' not in os.environ


@pytest.mark.parametrize('key,value', [
    ('AUTH_SIGNING_KEY', 'CANARY_SECRET'), ('AUTH_ENVIRONMENT', 'production'),
    ('AUTH_ALLOWED_ORIGINS', '["http://localhost:8000"]'),
    ('MEDIA_STORAGE_ROOT', 'C:/shared/media'), ('CATALOG_STORAGE_ROOT', 'C:/shared/catalog'),
])
def test_demo_config_rejects_incomplete_or_shared_configuration(config, key, value):
    from dotenv import set_key
    path, _ = config
    set_key(path/'.env', key, value)
    with pytest.raises(ConfigurationError) as error:
        demo.demo_environment()
    assert 'CANARY_SECRET' not in str(error.value)


def test_demo_migration_rejects_downgrade_before_connecting():
    import subprocess, sys
    result = subprocess.run([sys.executable, '-m', 'alembic', '-x', 'target=demo', 'downgrade', 'base'],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Demo migrations allow only current or upgrade to '+demo.DEMO_REVISION in result.stderr


def test_bootstrap_invalid_uuid_never_connects(monkeypatch):
    monkeypatch.setattr(demo, 'create_db_engine', lambda *a: pytest.fail('Unexpected connection'))
    assert demo.main(['bootstrap-admin'], ask=lambda prompt: 'not-a-uuid') == 1


@pytest.mark.parametrize('identity', [
    ('aurameme_dev', 'aurameme_demo', 'public'),
    ('aurameme_demo', 'postgres', 'public'),
    ('aurameme_demo', 'aurameme_demo', 'other'),
])
def test_demo_guard_checks_connected_identity(identity):
    from unittest.mock import Mock
    from sqlalchemy.engine import make_url
    connection = Mock()
    connection.dialect.name = 'postgresql'
    connection.engine.url = make_url('postgresql+psycopg://aurameme_demo:p@127.0.0.1:5432/aurameme_demo')
    connection.execute.return_value.one.return_value = identity
    with pytest.raises(ConfigurationError):
        demo.demo_connection(connection)


def test_demo_guard_refuses_administrative_role():
    from unittest.mock import Mock
    from sqlalchemy.engine import make_url
    connection = Mock()
    connection.dialect.name = 'postgresql'
    connection.engine.url = make_url('postgresql+psycopg://aurameme_demo:p@127.0.0.1:5432/aurameme_demo')
    connection.execute.return_value.one.return_value = ('aurameme_demo', 'aurameme_demo', 'public')
    connection.scalar.return_value = True
    with pytest.raises(ConfigurationError, match='administrative'):
        demo.demo_connection(connection)


@pytest.fixture
def accounts():
    """Synthetic rows live only inside a rolled-back transaction, never a demo seed."""
    from datetime import datetime, timezone
    from sqlalchemy import select, text
    from sqlalchemy.orm import Session
    from app.config import Settings
    from app.db import create_db_engine
    from app.models import Base, User, Role, UserRole
    value = os.environ.get('TEST_DATABASE_URL')
    if not value:
        pytest.skip('Explicit TEST_DATABASE_URL required')
    engine = create_db_engine(Settings(_env_file=None, database_url=value))
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                assert tuple(connection.execute(text('SELECT current_database(),current_schema()')).one()) == ('aurameme_test', 'public')
                assert all(connection.execute(select(text('count(*)')).select_from(table)).scalar_one() == 0 for table in Base.metadata.tables.values())
                with Session(bind=connection, join_transaction_mode='create_savepoint') as db:
                    now = datetime.now(timezone.utc)
                    role = Role(id=uuid4(), code='USER', description='Rollback-only fixture')
                    db.add(role)
                    db.flush()
                    users = []
                    for _ in range(2):
                        ident = uuid4()
                        user = User(id=ident, username='fixture_' + ident.hex[:16], email=ident.hex+'@example.com',
                            password_hash='Not-a-login-hash-rollback-only', status='active', created_at=now, updated_at=now)
                        db.add(user)
                        db.flush()
                        db.add(UserRole(user_id=ident, role_id=role.id, granted_at=now))
                        users.append(user)
                    db.flush()
                    yield db, users
            finally:
                outer.rollback()
            assert all(connection.execute(select(text('count(*)')).select_from(table)).scalar_one() == 0 for table in Base.metadata.tables.values())
    finally:
        engine.dispose()


@pytest.mark.integration
def test_bootstrap_confirm_audit_idempotency_and_second_account_rejection(accounts):
    from sqlalchemy import select, func
    from app.models import AdminAuditLog, Role, UserRole
    db, users = accounts
    assert 'granted' in demo.bootstrap_admin(db, users[0].id, lambda p: 'aurameme_demo '+users[0].username)
    audit = db.scalar(select(AdminAuditLog))
    assert audit.actor_id == users[0].id and audit.target_id == str(users[0].id)
    assert audit.action == 'demo.bootstrap_admin' and audit.before_json['roles'] == ['USER']
    assert audit.after_json['roles'] == ['ADMIN', 'USER']
    assert 'no change' in demo.bootstrap_admin(db, users[0].id, lambda p: pytest.fail('Repeated confirmation'))
    with pytest.raises(ConfigurationError, match='already exists'):
        demo.bootstrap_admin(db, users[1].id, lambda p: pytest.fail('Must refuse second bootstrap'))
    assert db.scalar(select(func.count()).select_from(AdminAuditLog)) == 1
    assert len(db.scalars(select(UserRole).join(Role).where(Role.code == 'ADMIN')).all()) == 1


@pytest.mark.integration
def test_bootstrap_cancel_or_unknown_account_does_not_grant(accounts):
    from sqlalchemy import select
    from app.models import Role, AdminAuditLog
    db, users = accounts
    with pytest.raises(ConfigurationError, match='Confirmation'):
        demo.bootstrap_admin(db, users[0].id, lambda p: 'wrong')
    with pytest.raises(ConfigurationError, match='existing active'):
        demo.bootstrap_admin(db, uuid4(), lambda p: pytest.fail('Unknown account'))
    assert db.scalar(select(Role).where(Role.code == 'ADMIN')) is None
    assert db.scalar(select(AdminAuditLog)) is None


@pytest.mark.integration
def test_bootstrap_audit_failure_rolls_back_grant(accounts, monkeypatch):
    from sqlalchemy import select
    from app.models import Role, AdminAuditLog
    db, users = accounts
    original = db.flush
    calls = 0
    def fail_audit(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('Synthetic audit flush failure')
        return original(*args, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setattr(db, 'flush', fail_audit)
        with pytest.raises(RuntimeError, match='Synthetic audit'):
            demo.bootstrap_admin(db, users[0].id, lambda p: 'aurameme_demo '+users[0].username)
    db.rollback()
    assert db.scalar(select(Role).where(Role.code == 'ADMIN')) is None
    assert db.scalar(select(AdminAuditLog)) is None


@pytest.mark.parametrize('command', [
    ['downgrade', 'base'], ['upgrade', '0001_p0'], ['stamp', '0009_vault_open'],
])
def test_demo_migration_rejects_other_operations(command):
    import subprocess, sys
    result = subprocess.run([sys.executable, '-m', 'alembic', '-x', 'target=demo']+command,
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Demo migrations allow only current or upgrade to '+demo.DEMO_REVISION in result.stderr



def schema_checks(revision):
    kinds = ('like','laugh','fire') if revision == '0009_vault_open' else ('like','love','laugh','fire','sad','angry')
    vault = revision in {'0011_vault_v1','0012_aura_v1',demo.DEMO_REVISION}
    if vault:
        kinds += ('meme',)
    expression = "reaction_type = ANY (ARRAY["+', '.join("'"+kind+"'::text" for kind in kinds)+'])'
    checks = {}
    for table in ('post_reactions','comment_reactions'):
        if table == 'comment_reactions' and revision == '0009_vault_open':
            continue
        checks[table] = {'ck_'+table+'_reaction_type':expression}
        if vault:
            checks[table]['ck_'+table+'_meme_reference'] = "(reaction_type = 'meme'::text) = (meme_asset_id IS NOT NULL)"
    checks['daily_checkins'] = {'ck_daily_checkins_effective_day':"effective_day = ((claimed_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text) - '07:00:00'::interval)::date"}
    if revision in {'0012_aura_v1',demo.DEMO_REVISION}:
        checks['daily_checkins']['ck_daily_checkins_reward_mode'] = "reward_mode = 'legacy'::text AND wallet_transaction_id IS NOT NULL OR reward_mode = 'aura_v1'::text AND wallet_transaction_id IS NULL"
        checks['aura_reward_events'] = {
            'ck_aura_reward_events_kind':"kind = ANY (ARRAY['post'::text, 'reaction'::text, 'comment'::text])",
            'ck_aura_reward_events_comment_binding':"(kind = 'comment'::text) = (comment_id IS NOT NULL)",
            'ck_aura_reward_events_effective_day':"effective_day = ((occurred_at AT TIME ZONE 'Asia/Ho_Chi_Minh'::text) - '07:00:00'::interval)::date",
        }
    return checks


def schema_mocks(monkeypatch,revision):
    from unittest.mock import Mock
    import alembic.autogenerate
    import alembic.migration
    import sqlalchemy
    from app.models import reviewed_metadata
    connection = Mock();connection.scalar.return_value = revision
    inspector = Mock()
    known = revision if revision != 'unknown' else '0012_aura_v1'
    inspector.get_table_names.return_value = set(reviewed_metadata(known).tables)|{'alembic_version'}
    checks = schema_checks(known)
    inspector.get_check_constraints.side_effect = lambda table:[{'name':name,'sqltext':value} for name,value in checks[table].items()]
    monkeypatch.setattr(sqlalchemy,'inspect',lambda _:inspector)
    monkeypatch.setattr(alembic.migration.MigrationContext,'configure',lambda *a,**k:object())
    compared = []
    monkeypatch.setattr(alembic.autogenerate,'compare_metadata',lambda _,metadata:compared.append(metadata) or [])
    monkeypatch.setattr(__import__('alembic.command',fromlist=['upgrade']),'upgrade',lambda *a,**k:pytest.fail('Schema readiness must never migrate'))
    return connection,inspector,checks,compared


@pytest.mark.parametrize('revision,allow_previous,accepted', [
    (demo.DEMO_REVISION,False,True),
    ('0012_aura_v1',False,False),
    ('0012_aura_v1',True,True),
    ('0011_vault_v1',False,False),
    ('0011_vault_v1',True,True),
    ('0010_social_reactions',False,False),
    ('0010_social_reactions',True,True),
    ('0009_vault_open',False,False),
    ('0009_vault_open',True,True),
    ('unknown',True,False),
])
def test_demo_schema_pins_current_head_and_previous_only_for_upgrade(monkeypatch,revision,allow_previous,accepted):
    from app.models import Base,reviewed_metadata
    connection,inspector,checks,compared = schema_mocks(monkeypatch,revision)
    if accepted:
        demo.reviewed_demo_schema(connection,allow_previous=allow_previous)
        assert len(compared) == 1
        metadata = compared[0]
        assert set(metadata.tables) == set(reviewed_metadata(revision).tables)
        assert ('reward_mode' in metadata.tables['daily_checkins'].c) == (revision in {'0012_aura_v1',demo.DEMO_REVISION})
        assert metadata.tables['daily_checkins'].c.wallet_transaction_id.nullable == (revision in {'0012_aura_v1',demo.DEMO_REVISION})
        assert ('runtime_kind' in metadata.tables['case_definitions'].c) == (revision in {'0011_vault_v1','0012_aura_v1',demo.DEMO_REVISION})
        assert 'aura_reward_events' in Base.metadata.tables
        assert 'reward_mode' in Base.metadata.tables['daily_checkins'].c
    else:
        with pytest.raises(ConfigurationError):demo.reviewed_demo_schema(connection,allow_previous=allow_previous)
        assert not compared


@pytest.mark.parametrize('revision',['0009_vault_open','0010_social_reactions','0011_vault_v1','0012_aura_v1'])
def test_demo_schema_refuses_drift_even_at_reviewed_revision(monkeypatch,revision):
    import alembic.autogenerate
    connection,_,_,_ = schema_mocks(monkeypatch,revision)
    monkeypatch.setattr(alembic.autogenerate,'compare_metadata',lambda *a:['unexpected column'])
    with pytest.raises(ConfigurationError,match='schema drift'):
        demo.reviewed_demo_schema(connection,allow_previous=True)


@pytest.mark.parametrize('table',['post_reactions','comment_reactions','daily_checkins','aura_reward_events'])
@pytest.mark.parametrize('tamper',['missing','extra','weakened'])
def test_demo_schema_refuses_missing_extra_or_weakened_checks(monkeypatch,table,tamper):
    connection,_,checks,compared = schema_mocks(monkeypatch,demo.DEMO_REVISION)
    demo.reviewed_demo_schema(connection)
    first = next(iter(checks[table]))
    if tamper == 'missing':checks[table].pop(first)
    elif tamper == 'extra':checks[table]['unreviewed'] = 'true'
    else:checks[table][first] = 'true'
    compared.clear()
    with pytest.raises(ConfigurationError,match='constraint drift'):
        demo.reviewed_demo_schema(connection)
    assert not compared


def test_demo_schema_refuses_unknown_tables_before_comparing(monkeypatch):
    connection,inspector,_,compared = schema_mocks(monkeypatch,demo.DEMO_REVISION)
    inspector.get_table_names.return_value.add('unreviewed')
    with pytest.raises(ConfigurationError,match='Unexpected demo schema tables'):
        demo.reviewed_demo_schema(connection)
    assert not compared


@pytest.mark.parametrize('arguments',[
    ['publish-aura-v1'],
    ['publish-aura-v1','--user','not-a-uuid'],
    ['bootstrap-admin','--user',str(uuid4())],
])
def test_aura_publication_requires_explicit_valid_operator_id_before_connection(monkeypatch,arguments):
    monkeypatch.setattr(demo,'create_db_engine',lambda *a:pytest.fail('Unexpected connection'))
    with pytest.raises(SystemExit) as error:
        demo.main(arguments,ask=lambda _:pytest.fail('Publication must not prompt'))
    assert error.value.code == 2


@pytest.fixture
def publication_cli(monkeypatch):
    from unittest.mock import MagicMock
    engine,db = MagicMock(),MagicMock()
    session = MagicMock();session.__enter__.return_value=db
    monkeypatch.setattr(demo,'demo_environment',lambda:{'DATABASE_URL':'postgresql+psycopg://aurameme_demo:SYNTHETIC_PRIVATE@127.0.0.1:5432/aurameme_demo'})
    monkeypatch.setattr(demo,'create_db_engine',lambda _:engine)
    monkeypatch.setattr(demo,'Session',lambda _:session)
    calls=[]
    monkeypatch.setattr(demo,'activate_demo',lambda:calls.append('environment'))
    monkeypatch.setattr(demo,'demo_connection',lambda _:calls.append('identity'))
    monkeypatch.setattr(demo,'reviewed_demo_schema',lambda _:calls.append('schema'))
    monkeypatch.setattr(demo,'bootstrap_admin',lambda *a:pytest.fail('Publication must not bootstrap/grant roles'))
    return engine,db,calls


def test_aura_publication_runs_existing_snapshot_service_in_guarded_transaction(publication_cli,monkeypatch,capsys):
    from datetime import datetime,timezone
    from unittest.mock import Mock
    import app.aura_runtime
    engine,db,calls=publication_cli
    user_id=uuid4()
    def publish(session,actor,now):
        calls.append('publish')
        assert session is db and actor == user_id
        assert now.tzinfo is not None and abs((datetime.now(timezone.utc)-now).total_seconds())<5
    publish=Mock(side_effect=publish)
    monkeypatch.setattr(app.aura_runtime,'publish_v1',publish)
    assert demo.main(['publish-aura-v1','--user',str(user_id)],ask=lambda _:pytest.fail('Publication must not prompt')) == 0
    assert calls==['environment','identity','schema','publish']
    publish.assert_called_once()
    db.begin.assert_called_once()
    db.begin.return_value.__exit__.assert_called_once_with(None,None,None)
    engine.connect.assert_not_called()
    engine.dispose.assert_called_once()
    output=capsys.readouterr().out
    assert 'Aura V1 policy is ready' in output and 'SYNTHETIC_PRIVATE' not in output


@pytest.mark.parametrize('guard',['identity','schema'])
def test_aura_publication_refuses_guard_failure_before_publishing(publication_cli,monkeypatch,guard,capsys):
    import app.aura_runtime
    engine,db,_=publication_cli
    def refuse(_):raise ConfigurationError('Unreviewed '+guard)
    monkeypatch.setattr(demo,'demo_connection' if guard=='identity' else 'reviewed_demo_schema',refuse)
    monkeypatch.setattr(app.aura_runtime,'publish_v1',lambda *a:pytest.fail('Guard must refuse before publication'))
    assert demo.main(['publish-aura-v1','--user',str(uuid4())],ask=lambda _:pytest.fail('No prompt')) == 1
    assert db.begin.return_value.__exit__.call_args.args[0] is ConfigurationError
    engine.dispose.assert_called_once()
    assert 'SYNTHETIC_PRIVATE' not in capsys.readouterr().out


def test_aura_publication_requires_existing_active_database_admin(publication_cli,capsys):
    engine,db,_=publication_cli
    db.scalar.return_value=None
    assert demo.main(['publish-aura-v1','--user',str(uuid4())],ask=lambda _:pytest.fail('No prompt')) == 1
    db.add.assert_not_called()
    assert db.begin.return_value.__exit__.call_args.args[0] is ValueError
    assert 'SYNTHETIC_PRIVATE' not in capsys.readouterr().out
    engine.dispose.assert_called_once()


def test_aura_publication_failure_rolls_back_and_redacts_private_details(publication_cli,monkeypatch,capsys):
    import app.aura_runtime
    engine,db,_=publication_cli
    def fail(*args):raise RuntimeError('SYNTHETIC_PRIVATE')
    monkeypatch.setattr(app.aura_runtime,'publish_v1',fail)
    assert demo.main(['publish-aura-v1','--user',str(uuid4())],ask=lambda _:pytest.fail('No prompt')) == 1
    assert db.begin.return_value.__exit__.call_args.args[0] is RuntimeError
    output=capsys.readouterr().out
    assert 'transaction rolled back' in output and 'SYNTHETIC_PRIVATE' not in output
    engine.dispose.assert_called_once()


def test_legacy_demo_config_does_not_inherit_vault_issuance(config,monkeypatch):
    with monkeypatch.context() as scoped:
        scoped.setattr(os,'environ',os.environ.copy())
        scoped.setenv('VAULT_RUNTIME_ENABLED','true')
        demo.activate_demo()
        assert os.environ['VAULT_RUNTIME_ENABLED']=='false'

@pytest.mark.parametrize('flag',['true','false'])
def test_demo_vault_flag_requires_explicit_private_config(config,flag):
    from dotenv import set_key
    path,_=config
    set_key(path/'.env','VAULT_RUNTIME_ENABLED',flag)
    assert demo.demo_environment()['VAULT_RUNTIME_ENABLED']==flag

@pytest.mark.parametrize('flag',['TRUE','1','on','','unexpected'])
def test_demo_vault_flag_rejects_ambiguous_values(config,flag):
    from dotenv import set_key
    path,_=config
    set_key(path/'.env','VAULT_RUNTIME_ENABLED',flag)
    with pytest.raises(ConfigurationError):demo.demo_environment()
