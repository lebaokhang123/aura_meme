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
    assert 'Demo migrations allow only current or upgrade to 0010_social_reactions' in result.stderr


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
    assert 'Demo migrations allow only current or upgrade to 0010_social_reactions' in result.stderr


@pytest.mark.parametrize('revision,allow_previous,accepted', [
    ('0010_social_reactions', False, True),
    ('0009_vault_open', False, False),
    ('0009_vault_open', True, True),
    ('unknown', True, False),
])
def test_demo_schema_pins_current_head_and_previous_only_for_upgrade(monkeypatch, revision, allow_previous, accepted):
    from unittest.mock import Mock
    import alembic.autogenerate
    import alembic.migration
    import sqlalchemy
    from app.models import Base
    connection = Mock()
    connection.scalar.return_value = revision
    inspector = Mock()
    tables = set(Base.metadata.tables) | {'alembic_version'}
    if revision == '0009_vault_open':
        tables.remove('comment_reactions')
    inspector.get_table_names.return_value = tables
    kinds = ('like', 'laugh', 'fire') if revision == '0009_vault_open' else ('like', 'love', 'laugh', 'fire', 'sad', 'angry')
    inspector.get_check_constraints.return_value = [{'name': 'ck_post_reactions_reaction_type',
        'sqltext': "reaction_type = ANY (ARRAY[" + ', '.join("'"+kind+"'::text" for kind in kinds) + '])'}]
    monkeypatch.setattr(sqlalchemy, 'inspect', lambda _: inspector)
    monkeypatch.setattr(alembic.migration.MigrationContext, 'configure', lambda *a, **k: object())
    compared = []
    monkeypatch.setattr(alembic.autogenerate, 'compare_metadata', lambda _, metadata: compared.append(set(metadata.tables)) or [])
    if accepted:
        demo.reviewed_demo_schema(connection, allow_previous=allow_previous)
        assert compared == [tables - {'alembic_version'}]
        assert 'comment_reactions' in Base.metadata.tables
        inspector.get_check_constraints.return_value = [{'name': 'ck_post_reactions_reaction_type', 'sqltext': 'true'}]
        with pytest.raises(ConfigurationError):
            demo.reviewed_demo_schema(connection, allow_previous=allow_previous)
    else:
        with pytest.raises(ConfigurationError):
            demo.reviewed_demo_schema(connection, allow_previous=allow_previous)
        assert not compared


def test_demo_schema_refuses_drift_even_at_reviewed_revision(monkeypatch):
    from unittest.mock import Mock
    import alembic.autogenerate
    import alembic.migration
    import sqlalchemy
    from app.models import Base
    connection = Mock(); connection.scalar.return_value = '0010_social_reactions'
    inspector = Mock(); inspector.get_table_names.return_value = set(Base.metadata.tables) | {'alembic_version'}
    inspector.get_check_constraints.return_value = [{'name': 'ck_post_reactions_reaction_type', 'sqltext': "reaction_type = ANY (ARRAY['like'::text, 'love'::text, 'laugh'::text, 'fire'::text, 'sad'::text, 'angry'::text])"}]
    monkeypatch.setattr(sqlalchemy, 'inspect', lambda _: inspector)
    monkeypatch.setattr(alembic.migration.MigrationContext, 'configure', lambda *a, **k: object())
    monkeypatch.setattr(alembic.autogenerate, 'compare_metadata', lambda *a: ['unexpected column'])
    with pytest.raises(ConfigurationError):
        demo.reviewed_demo_schema(connection)
