"""Explicit local demo configuration and first-admin bootstrap, never an HTTP API."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from dotenv import dotenv_values
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import AuthSettings, CatalogSettings, ConfigurationError, MediaSettings, Settings
from app.db import create_db_engine
from app.models import AdminAuditLog, Role, User, UserRole

DEMO_ROOT = Path(__file__).resolve().parents[1] / 'demo.local'
FIELDS = {'DATABASE_URL', 'DB_CONNECT_TIMEOUT', 'AUTH_SIGNING_KEY', 'AUTH_ENVIRONMENT',
          'AUTH_ALLOWED_ORIGINS', 'MEDIA_STORAGE_ROOT', 'CATALOG_STORAGE_ROOT'}


def validate_demo_url(value):
    try:
        settings = Settings(_env_file=None, database_url=value, db_connect_timeout=5)
        url = make_url(settings.database_url.get_secret_value())
        if (url.database != 'aurameme_demo' or url.username != 'aurameme_demo'
                or url.host not in {'localhost', '127.0.0.1', '::1'}
                or url.port != 5432 or url.query or not url.password):
            raise ValueError
        return settings
    except Exception:
        raise ConfigurationError('Demo requires its dedicated local database and role on port 5432.') from None


def demo_environment(root=None):
    root=DEMO_ROOT if root is None else Path(root)
    try:
        if not root.is_absolute() or ".." in root.parts:raise ValueError
        if root.is_symlink() or root.is_junction() or (root/'.env').is_symlink():
            raise ValueError
        values = dict(dotenv_values(root/'.env', interpolate=False))
        if set(values) != FIELDS or any(not v for v in values.values()):
            raise ValueError
        validate_demo_url(values['DATABASE_URL'])
        Settings(_env_file=None, database_url=values['DATABASE_URL'], db_connect_timeout=values['DB_CONNECT_TIMEOUT'])
        auth = AuthSettings(_env_file=None, auth_signing_key=values['AUTH_SIGNING_KEY'],
            auth_environment=values['AUTH_ENVIRONMENT'], auth_allowed_origins=json.loads(values['AUTH_ALLOWED_ORIGINS']))
        if auth.auth_environment != 'development' or auth.auth_allowed_origins != ['http://localhost:5173']:
            raise ValueError
        for field, cls, folder in [('MEDIA_STORAGE_ROOT', MediaSettings, 'media'),
                                   ('CATALOG_STORAGE_ROOT', CatalogSettings, 'catalog')]:
            path = Path(values[field])
            cls(_env_file=None, **{field.lower(): path})
            if path != root/folder or path.is_symlink() or (path.exists() and path.is_junction()):
                raise ValueError
        return values
    except Exception:
        raise ConfigurationError('Invalid demo.local/.env; require complete dedicated demo configuration.') from None


def activate_demo(root=None):
    values = demo_environment(root)
    # Avoid mixing a partial demo environment with development/test/E2E overrides.
    for key in list(os.environ):
        if key.startswith('AUTH_') or key.endswith('DATABASE_URL') or key in FIELDS:
            del os.environ[key]
    os.environ.update(values)


def demo_connection(connection):
    if connection.dialect.name != 'postgresql':
        raise ConfigurationError('Demo requires PostgreSQL.')
    validate_demo_url(connection.engine.url.render_as_string(hide_password=False))
    if tuple(connection.execute(text('SELECT current_database(),current_user,current_schema()')).one()) != (
            'aurameme_demo', 'aurameme_demo', 'public'):
        raise ConfigurationError('Demo database identity, role or schema mismatch.')
    if connection.scalar(text('SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname=current_user')):
        raise ConfigurationError('Demo role must not have administrative privileges.')


def bootstrap_admin(db, user_id, ask=input):
    # Serialize first-admin creation, including the case where no ADMIN role exists yet.
    db.execute(text('LOCK TABLE roles, user_roles IN SHARE ROW EXCLUSIVE MODE'))
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None or user.status != 'active':
        raise ConfigurationError('Choose an existing active account registered through the website.')
    roles = list(db.scalars(select(Role.code).join(UserRole).where(UserRole.user_id == user.id).order_by(Role.code)))
    admins = db.scalar(select(UserRole.user_id).join(Role).where(Role.code == 'ADMIN').limit(1))
    if admins is not None:
        if 'ADMIN' in roles:
            return 'Already ADMIN; no change.'
        raise ConfigurationError('An administrator already exists; use the normal Admin interface.')
    if roles != ['USER']:
        raise ConfigurationError('Bootstrap requires an account with only the USER role.')
    confirmation = f'aurameme_demo {user.username}'
    print(f'Local bootstrap: {user.username} ({user.id}) on aurameme_demo. No password change.')
    if ask('Type exactly "' + confirmation + '" to grant ADMIN: ') != confirmation:
        raise ConfigurationError('Confirmation did not match; no change.')
    now = datetime.now(timezone.utc)
    role = db.scalar(select(Role).where(Role.code == 'ADMIN'))
    if role is None:
        role = Role(id=uuid4(), code='ADMIN', description='Administrator role')
        db.add(role)
        db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id, granted_at=now))
    db.add(AdminAuditLog(id=uuid4(), actor_id=user.id, action='demo.bootstrap_admin', target_type='user',
        target_id=str(user.id), before_json={'status': 'active', 'roles': ['USER']},
        after_json={'status': 'active', 'roles': ['ADMIN', 'USER'], 'source': 'local_owner_confirmation'}, created_at=now))
    db.flush()
    return 'ADMIN granted with audit. Log out and log in again.'


def main(argv=None, ask=input):
    parser = argparse.ArgumentParser(description='Owner-controlled first Admin on isolated local demo only.')
    parser.add_argument('command', choices=['bootstrap-admin'])
    parser.parse_args(argv)
    engine = None
    try:
        user_id = UUID(ask('Registered demo account UUID (see /api/v1/users/me): ').strip())
        values = demo_environment()
        engine = create_db_engine(validate_demo_url(values['DATABASE_URL']))
        # Do not hold table locks while the Owner reads and types a confirmation.
        with engine.connect() as connection:
            connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            demo_connection(connection)
            username = connection.scalar(select(User.username).where(User.id == user_id, User.status == 'active'))
            if username is None:
                raise ConfigurationError('Choose an existing active account registered through the website.')
        confirmation = ask(f'Type exactly "aurameme_demo {username}" to grant ADMIN to {user_id}: ')
        with Session(engine) as db, db.begin():
            db.execute(text("SET LOCAL lock_timeout='5s'"))
            demo_connection(db.connection())
            if db.scalar(text('SELECT version_num FROM alembic_version')) != '0009_vault_open':
                raise ConfigurationError('Demo requires revision 0009_vault_open.')
            message = bootstrap_admin(db, user_id, lambda prompt: confirmation)
        print(message)
        return 0
    except (ValueError, EOFError, KeyboardInterrupt):
        print('Cancelled or invalid account UUID; no change.')
        return 1
    except ConfigurationError as error:
        print(str(error))
        return 1
    except Exception:
        print('Demo bootstrap failed; transaction rolled back. Check local database/configuration.')
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
