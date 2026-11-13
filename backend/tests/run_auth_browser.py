"""Real Auth browser on pre-existing, empty aurameme_e2e only; never migrate/reset."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from app.config import Settings
from app.db import create_db_engine
from app.models import Base,User,Role
from run_browser import inventory


def main():
    config=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'e2e.local/.env'
    values={k:v for k,v in dotenv_values(config).items() if v is not None}
    url=make_url(values.get('DATABASE_URL',''))
    assert url.database=='aurameme_e2e' and url.username=='aurameme_e2e_app' and url.host in {'127.0.0.1','localhost'} and not url.query
    engine=create_db_engine(Settings(_env_file=None,database_url=values['DATABASE_URL']))
    with engine.connect() as connection:
        connection.exec_driver_sql('SET TRANSACTION READ ONLY')
        assert connection.scalar(text('SELECT current_user'))=='aurameme_e2e_app'
        assert not any(connection.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one())
        assert not any(inventory(connection).values()),'Existing E2E rows: refuse tests/cleanup'
        objects=connection.execute(text("SELECT oid,relname,relfilenode FROM pg_class WHERE relnamespace='public'::regnamespace ORDER BY relname")).all()
    for port in (8001,4187):
        with socket.socket() as probe:probe.bind(('127.0.0.1',port))
    prefix='auth_'+secrets.token_hex(6)
    api=None
    try:
        with tempfile.TemporaryDirectory(prefix='aurameme-auth-e2e-') as private:
            environment=os.environ|values|{
                'AUTH_ENVIRONMENT':'development','AUTH_ALLOWED_ORIGINS':json.dumps(['http://localhost:4187']),
                'MEDIA_STORAGE_ROOT':private,'AURAMEME_API_TARGET':'http://127.0.0.1:8001','AURA_AUTH_E2E_PREFIX':prefix,
            }
            api=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001'],cwd=ROOT,env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(100):
                if api.poll() is not None:raise RuntimeError('Owned E2E API failed')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=1) as response:assert response.status==200
                    break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('Owned E2E API timeout')
            result=subprocess.run(['npx.cmd' if os.name=='nt' else 'npx','playwright','test','--config=../.github/playwright.auth-real.config.mjs','--forbid-only'],cwd=ROOT.parent/'frontend',env=environment).returncode
            api.terminate();api.wait(timeout=10);api=None
    finally:
        if api is not None and api.poll() is None:api.terminate();api.wait(timeout=10)
        with engine.begin() as connection:
            counts=inventory(connection)
            rows=connection.execute(select(User.id,User.username,User.email)).all()
            assert all(r.username==prefix and r.email==prefix+'@example.com' for r in rows),'Unknown user: refuse cleanup'
            ids=[r.id for r in rows]
            role_rows=connection.execute(select(Role.id,Role.code)).all()
            assert all(r.code=='USER' for r in role_rows),'Unknown role: refuse cleanup'
            for name,count in counts.items():
                assert not count or name in {'users','profiles','roles','user_roles','auth_sessions'},'Unexpected data: refuse cleanup'
            for name in ('auth_sessions','user_roles','profiles'):
                table=Base.metadata.tables[name]
                assert all(ident in ids for ident in connection.scalars(select(table.c.user_id)))
                connection.execute(table.delete().where(table.c.user_id.in_(ids)))
            connection.execute(User.__table__.delete().where(User.id.in_(ids)))
            connection.execute(Role.__table__.delete().where(Role.id.in_([r.id for r in role_rows])))
            assert not any(inventory(connection).values())
            assert connection.execute(text("SELECT oid,relname,relfilenode FROM pg_class WHERE relnamespace='public'::regnamespace ORDER BY relname")).all()==objects
        engine.dispose()
        print('E2E cleanup PASS: 29 empty tables; revision/schema unchanged; no DROP/reset.')
    return result


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print('Auth E2E refused/failed ('+type(error).__name__+'); no reset attempted.',file=sys.stderr)
        if isinstance(error,OSError):print('OS error:',error.errno,Path(error.filename).name if error.filename else 'process operation',file=sys.stderr)
        raise SystemExit(1)
