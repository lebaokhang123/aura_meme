"""Run real browser Auth against an empty, explicitly provisioned local E2E database."""
from pathlib import Path
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import dotenv_values
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import make_url
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.config import Settings
from app.db import create_db_engine
from app.models import Base, User, Role
from test_migrations import TABLES, REVISION


def inventory(connection):
    assert connection.scalar(text('SELECT current_database()')) == 'aurameme_e2e', 'E2E database required'
    assert connection.scalar(text('SELECT current_schema()')) == 'public', 'E2E public schema required'
    inspector = inspect(connection)
    assert set(inspector.get_table_names()) == TABLES | {'alembic_version'}, 'Unexpected E2E tables'
    assert connection.scalar(text('SELECT version_num FROM alembic_version')) == REVISION
    assert not compare_metadata(MigrationContext.configure(connection, opts={'compare_server_default': True}), Base.metadata), 'E2E schema drift'
    assert not inspector.get_view_names() and not inspector.get_materialized_view_names() and not inspector.get_sequence_names()
    assert not connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','information_schema') AND nspname NOT LIKE 'pg_%'"))
    assert not connection.scalar(text("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public'"))
    assert not connection.scalar(text("SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal"))
    assert not connection.scalar(text("SELECT count(*) FROM pg_policies WHERE schemaname='public'"))
    return {name: connection.scalar(select(text('count(*)')).select_from(Base.metadata.tables[name])) for name in TABLES}


def main():
    values = {key: value for key, value in dotenv_values(ROOT / 'e2e.local/.env').items() if value is not None}
    url = make_url(values.get('DATABASE_URL', ''))
    assert url.database == 'aurameme_e2e' and url.host in {'localhost', '127.0.0.1'}, 'Explicit local E2E URL required'
    engine = create_db_engine(Settings(_env_file=None, database_url=values['DATABASE_URL']))
    with engine.connect() as connection:
        before = inventory(connection)
        assert not any(before.values()), 'Existing E2E data; refusing test or cleanup'
        objects = connection.execute(text("SELECT c.oid,c.relname,c.relfilenode FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname")).all()
    for port in (8001, 4173):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))  # Never reuse an unknown API/frontend process.
    prefix = 'e2e_' + secrets.token_hex(6)
    environment = os.environ | values | {'AURA_E2E_PREFIX': prefix}
    api = None
    result = 1
    try:
        with (ROOT / 'e2e.local/api.log').open('w', encoding='utf-8') as log:
            api = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001'], cwd=ROOT, env=environment, stdout=log, stderr=log)
            for _ in range(100):
                if api.poll() is not None:
                    raise RuntimeError('E2E API failed to start; inspect local api.log')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=1) as response:
                        assert response.status == 200
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('E2E API health timeout')
            result = subprocess.run(['npm.cmd', 'test', '--', '--config=playwright.e2e.config.ts'], cwd=ROOT.parent / 'frontend', env=environment).returncode
    finally:
        if api is not None and api.poll() is None:
            api.terminate()
            api.wait(timeout=10)
        with engine.begin() as connection:
            counts = inventory(connection)
            allowed = {'users', 'profiles', 'auth_sessions', 'user_roles', 'roles'}
            assert all(not count for name, count in counts.items() if name not in allowed), 'Unknown E2E business data; refusing cleanup'
            users = connection.execute(select(User.id, User.username, User.email)).all()
            assert all(row.username == prefix and row.email == prefix + '@example.com' for row in users), 'Unknown E2E identity; refusing cleanup'
            assert set(connection.scalars(select(Role.code))) <= {'USER'}, 'Unknown E2E role; refusing cleanup'
            ids = [row.id for row in users]
            for name in ('auth_sessions', 'user_roles', 'profiles'):
                table = Base.metadata.tables[name]
                connection.execute(table.delete().where(table.c.user_id.in_(ids)))
            connection.execute(User.__table__.delete().where(User.id.in_(ids)))
            connection.execute(Role.__table__.delete().where(Role.code == 'USER'))
            assert not any(inventory(connection).values()), 'E2E cleanup incomplete'
            assert connection.execute(text("SELECT c.oid,c.relname,c.relfilenode FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname")).all() == objects, 'E2E schema objects changed'
        engine.dispose()
        print('E2E fixture cleanup PASS: original schema/revision preserved, zero rows; no DROP/reset.')
    return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        # Driver exceptions may contain connection details; never echo them.
        print('E2E runner failed (' + type(error).__name__ + '); inspect configuration/preflight. No reset attempted.', file=sys.stderr)
        raise SystemExit(1) from None
