"""Run real Auth/Blog browsers with exact synthetic fixtures on isolated PostgreSQL."""
from pathlib import Path
import os
import json
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime,timedelta,timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import dotenv_values
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import make_url
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.config import Settings
from app.db import create_db_engine
from app.models import Base,User,Role,Profile,UserRole,Category,Post,Comment,MediaUpload,ContactMessage,AdminAuditLog
from argon2 import PasswordHasher
from PIL import Image
from test_migrations import TABLES, REVISION
from schema_guard import assert_auxiliary_objects


def inventory(connection):
    assert connection.scalar(text('SELECT current_database()')) == 'aurameme_e2e', 'E2E database required'
    assert connection.scalar(text('SELECT current_schema()')) == 'public', 'E2E public schema required'
    inspector = inspect(connection)
    assert set(inspector.get_table_names()) == TABLES | {'alembic_version'}, 'Unexpected E2E tables'
    assert connection.scalar(text('SELECT version_num FROM alembic_version')) == REVISION
    assert not compare_metadata(MigrationContext.configure(connection, opts={'compare_server_default': True}), Base.metadata), 'E2E schema drift'
    assert not inspector.get_view_names() and not inspector.get_materialized_view_names() and not inspector.get_sequence_names()
    assert not connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','information_schema') AND nspname NOT LIKE 'pg_%'"))
    assert_auxiliary_objects(connection)

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
    media_root=ROOT/'e2e.local/media'
    assert not media_root.is_symlink() and not media_root.is_junction()
    assert not media_root.exists() or not list(media_root.iterdir()), 'Existing E2E files; refusing cleanup'
    fixture=ROOT/'e2e.local/fixture.png'
    assert not fixture.exists(), 'Existing fixture file; refusing overwrite'
    category_id=uuid4();role_id=uuid4();admin_role_id=uuid4();now=datetime.now(timezone.utc)
    usernames={prefix,prefix+'_blog',prefix+'_reader',prefix+'_admin',prefix+'_created'}
    environment = os.environ | values | {'AURA_E2E_PREFIX': prefix,'AURA_E2E_IMAGE':str(fixture),'MEDIA_STORAGE_ROOT':str(media_root)}
    api = None
    result = 1
    fixture_created=False
    try:
        with fixture.open('xb') as output:
            fixture_created=True
            Image.new('RGB',(24,24),(120,80,220)).save(output,format='PNG')
        with engine.begin() as connection:
            connection.execute(Category.__table__.insert().values(id=category_id,name='Synthetic E2E channel',slug=prefix.replace('_','-'),status='active',created_at=now,updated_at=now))
            connection.execute(Role.__table__.insert().values(id=role_id,code='USER',description='Synthetic E2E role'))
            connection.execute(Role.__table__.insert().values(id=admin_role_id,code='ADMIN',description='Synthetic E2E Admin role'))
            encoded=PasswordHasher().hash('Synthetic blog password!')
            for suffix in ('_blog','_reader','_admin'):
                ident=uuid4();name=prefix+suffix
                connection.execute(User.__table__.insert().values(id=ident,username=name,email=name+'@example.com',password_hash=encoded,status='active',created_at=now,updated_at=now))
                connection.execute(Profile.__table__.insert().values(user_id=ident,display_name={'_blog':'Synthetic Writer','_reader':'Synthetic Reader','_admin':'Synthetic Admin'}[suffix],updated_at=now))
                connection.execute(UserRole.__table__.insert().values(user_id=ident,role_id=role_id,granted_at=now))
                if suffix=='_admin':connection.execute(UserRole.__table__.insert().values(user_id=ident,role_id=admin_role_id,granted_at=now))
                if suffix=='_blog':
                    connection.execute(Post.__table__.insert(),[dict(id=uuid4(),author_id=ident,category_id=category_id,title=f'Synthetic E2E paging {index:02}',content='Synthetic E2E fixture text',status='published',created_at=now-timedelta(seconds=index+1),updated_at=now) for index in range(21)])
        for flow in ('auth-real','blog-real','admin-real'):
            # Each scenario keeps normal rate limits on a fresh owned API process.
            print('E2E flow: '+flow,flush=True)
            with (ROOT / 'e2e.local/api.log').open('a', encoding='utf-8') as log:
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
                result = subprocess.run(['npm.cmd', 'test', '--', '--config=playwright.e2e.config.ts','--output=test-results/'+flow,'tests/'+flow+'.spec.ts'], cwd=ROOT.parent / 'frontend', env=environment).returncode
                api.terminate();api.wait(timeout=10);api=None
                if result:break
    finally:
        if api is not None and api.poll() is None:
            api.terminate()
            api.wait(timeout=10)
        with engine.begin() as connection:
            inventory(connection)
            users = connection.execute(select(User.id, User.username, User.email)).all()
            assert all(row.username in usernames and row.email in {row.username+'@example.com',row.username+'+updated@example.com'} for row in users), 'Unknown E2E identity; refusing cleanup'
            assert all(tuple(role) in {(role_id,'USER'),(admin_role_id,'ADMIN')} for role in connection.execute(select(Role.id,Role.code))), 'Unknown E2E role; refusing cleanup'
            ids = [row.id for row in users]
            user_ids={row.username:row.id for row in users}
            channels=connection.execute(select(Category.id,Category.slug)).all()
            slugs={prefix.replace('_','-'),prefix.replace('_','-')+'-admin'}
            assert all(row.slug in slugs for row in channels), 'Unknown E2E channel'
            category_ids=[row.id for row in channels]
            posts=connection.execute(select(Post.id,Post.author_id,Post.category_id,Post.title)).all()
            assert all(row.author_id in ids and row.category_id in category_ids and row.title.startswith('Synthetic E2E') for row in posts), 'Unknown E2E post'
            post_ids=[row.id for row in posts]
            comments=connection.execute(select(Comment.author_id,Comment.post_id,Comment.body)).all()
            assert all(row.author_id in ids and row.post_id in post_ids and row.body.startswith('Synthetic E2E') for row in comments), 'Unknown E2E comment'
            contacts=connection.execute(select(ContactMessage.id,ContactMessage.user_id,ContactMessage.name,ContactMessage.email,ContactMessage.body)).all()
            assert all(row.user_id in [None,*ids] and row.name in {'Synthetic E2E Guest','Synthetic E2E Member'} and row.email in {prefix+'_guest@example.com',prefix+'_reader@example.com'} and row.body.startswith('Synthetic E2E') for row in contacts), 'Unknown E2E contact'
            assert all(row.user_id==(user_ids[prefix+'_reader'] if row.email==prefix+'_reader@example.com' else None) for row in contacts), 'Contact session identity mismatch'
            contact_ids=[row.id for row in contacts]
            targets={'user':ids,'post':post_ids,'category':category_ids,'contact':contact_ids}
            assert all(row.actor_id in ids and row.target_type in targets and row.target_id in {str(ident) for ident in targets[row.target_type]} for row in connection.execute(select(AdminAuditLog.actor_id,AdminAuditLog.target_type,AdminAuditLog.target_id))), 'Unknown E2E audit'
            for name in ('post_reactions', 'post_bookmarks'):
                table = Base.metadata.tables[name]
                assert all(row.user_id in ids and row.post_id in post_ids for row in connection.execute(select(table.c.user_id, table.c.post_id))), 'Unknown E2E interaction'
            media=connection.execute(select(MediaUpload.owner_id,MediaUpload.object_key)).all()
            assert all(row.owner_id in ids and re.fullmatch(r'[0-9a-f]{32}\.(?:png|jpg|webp|gif)',row.object_key) for row in media), 'Unknown E2E media'
            keys={row.object_key for row in media}
            files=list(media_root.iterdir()) if media_root.exists() else []
            assert {file.name for file in files}==keys and all(file.is_file() and not file.is_symlink() and not file.is_junction() for file in files), 'Unknown E2E bytes; refusing cleanup'
            manifest=ROOT/('e2e.local/'+prefix+'-cleanup.json')
            with manifest.open('x',encoding='utf-8') as output:json.dump({'users':[str(ident) for ident in ids],'media_keys':sorted(keys)},output)
            connection.execute(AdminAuditLog.__table__.delete().where(AdminAuditLog.actor_id.in_(ids)))
            connection.execute(ContactMessage.__table__.delete().where(ContactMessage.id.in_(contact_ids)))
            connection.execute(Comment.__table__.delete().where(Comment.post_id.in_(post_ids)))
            for name in ('post_reactions', 'post_bookmarks'):
                table = Base.metadata.tables[name]
                connection.execute(table.delete().where(table.c.user_id.in_(ids), table.c.post_id.in_(post_ids)))
            connection.execute(Post.__table__.delete().where(Post.id.in_(post_ids)))
            for name in ('auth_sessions', 'user_roles', 'profiles'):
                table = Base.metadata.tables[name]
                connection.execute(table.delete().where(table.c.user_id.in_(ids)))
            connection.execute(MediaUpload.__table__.delete().where(MediaUpload.owner_id.in_(ids)))
            connection.execute(User.__table__.delete().where(User.id.in_(ids)))
            connection.execute(Role.__table__.delete().where(Role.id.in_([role_id,admin_role_id])))
            connection.execute(Category.__table__.delete().where(Category.id.in_(category_ids)))
            assert not any(inventory(connection).values()), 'E2E cleanup incomplete'
            assert connection.execute(text("SELECT c.oid,c.relname,c.relfilenode FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname")).all() == objects, 'E2E schema objects changed'
        for file in files:file.unlink()
        if fixture_created:fixture.unlink()
        manifest.unlink()
        assert not media_root.exists() or not list(media_root.iterdir()), 'E2E file cleanup incomplete'
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
