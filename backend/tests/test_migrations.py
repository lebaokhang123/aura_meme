"""PostgreSQL-only migration tests; never reset development or unknown test data."""
import os
from pathlib import Path
import re
from uuid import uuid4
from datetime import datetime, timedelta, timezone

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, inspect, text
from sqlalchemy.exc import IntegrityError

from app.config import Settings, load_settings
from app.db import create_db_engine
from app.models import Base
from schema_guard import assert_auxiliary_objects


ROOT = Path(__file__).resolve().parents[1]
P0_TABLES = {
    "users", "roles", "user_roles", "profiles", "auth_sessions", "categories",
    "media_uploads", "posts", "comments", "contact_messages", "admin_audit_logs",
}
AURA_TABLES = P0_TABLES | {"post_reactions", "post_bookmarks", "reward_policy_versions", "user_progress", "aura_ledger"}
TABLES = AURA_TABLES | {"comment_reactions", "wallets", "wallet_transactions", "daily_checkins", "asset_items", "user_inventory", "user_equipment", "case_definitions", "case_loot_tables", "case_loot_rarities", "case_pool_items", "case_opens", "inventory_grants"}
REVISION = "0010_social_reactions"


def config():
    return Config(str(ROOT / "alembic.ini"))


def migrate(engine, direction, revision):
    cfg = config()
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        getattr(command, direction)(cfg, revision)


def development_inventory(engine):
    with engine.connect() as connection:
        objects = connection.execute(text(
            "SELECT c.oid, n.nspname, c.relname, c.relkind, c.relfilenode "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema' "
            "ORDER BY n.nspname,c.relname"
        )).all()
        counts = {}
        for table in inspect(connection).get_table_names():
            quoted = connection.dialect.identifier_preparer.quote(table)
            counts[table] = connection.execute(text(f'SELECT count(*) FROM {quoted}')).scalar_one()
        return objects, counts


@pytest.mark.integration
def test_interactions_revision_preserves_p0_objects(migrated):
    p0 = P0_TABLES
    def inventory():
        with migrated.connect() as connection:
            assert all(connection.scalar(text(f'SELECT count(*) FROM "{name}"')) == 0 for name in TABLES)
            return connection.execute(text("SELECT oid,relname,relfilenode FROM pg_class WHERE relnamespace='public'::regnamespace AND relname=ANY(:names) ORDER BY relname"), {"names": sorted(p0)}).all()
    before = inventory()
    migrate(migrated, "downgrade", "0001_p0")
    with migrated.connect() as connection:
        assert set(inspect(connection).get_table_names()) == p0 | {"alembic_version"}
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001_p0"
    migrate(migrated, "upgrade", "head")
    migrate(migrated, "upgrade", "head")
    assert inventory() == before


@pytest.mark.integration
def test_draft_revision_preserves_existing_tables_and_guards(migrated):
    old = P0_TABLES | {"post_reactions", "post_bookmarks"}
    def inventory():
        with migrated.connect() as connection:
            return connection.execute(text("SELECT c.oid,c.relname,c.relfilenode FROM pg_class c LEFT JOIN pg_index i ON i.indexrelid=c.oid WHERE c.relnamespace='public'::regnamespace AND (c.relname=ANY(:names) OR i.indrelid IN (SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace AND relname=ANY(:names))) ORDER BY c.relname"), {"names": sorted(old)}).all()
    with migrated.connect() as connection:
        assert all(connection.scalar(text(f'SELECT count(*) FROM "{name}"')) == 0 for name in TABLES)
    before = inventory()
    migrate(migrated, "downgrade", "0002_interactions")
    with migrated.connect() as connection:
        assert set(inspect(connection).get_table_names()) == old | {"alembic_version"}
        assert connection.scalar(text("SELECT count(*) FROM pg_proc WHERE pronamespace='public'::regnamespace")) == 0
    migrate(migrated, "upgrade", "head")
    migrate(migrated, "upgrade", "head")
    assert inventory() == before
    with migrated.connect() as connection:
        assert_auxiliary_objects(connection)


@pytest.mark.integration
def test_wallet_revision_roundtrip_preserves_existing_schema(migrated):
    old = AURA_TABLES
    def inventory():
        with migrated.connect() as connection:
            return connection.execute(text("SELECT oid,relname,relfilenode FROM pg_class WHERE relnamespace='public'::regnamespace AND relname=ANY(:names) ORDER BY relname"), {"names":sorted(old)}).all()
    with migrated.connect() as connection:
        assert all(connection.scalar(text(f'SELECT count(*) FROM "{name}"')) == 0 for name in TABLES)
    before=inventory()
    migrate(migrated, "downgrade", "0003_aura_draft")
    with migrated.connect() as connection:
        assert set(inspect(connection).get_table_names()) == old | {"alembic_version"}
        assert_auxiliary_objects(connection)
    migrate(migrated,"upgrade","head")
    migrate(migrated,"upgrade","head")
    assert inventory()==before


@pytest.fixture(scope="module")
def migrated():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL missing; PostgreSQL migration was NOT TESTED")
    settings = Settings(_env_file=None, database_url=url)
    engine = create_db_engine(settings)
    dev = create_db_engine(load_settings())
    before = development_inventory(dev)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT current_database()")).scalar_one() == "aurameme_test"
            tables = set(inspect(connection).get_table_names())
            assert tables in [set(), {"alembic_version"}, TABLES | {"alembic_version"}], "Unknown schema; refusing destructive test"
            assert not inspect(connection).get_view_names(), "Unknown views; refusing migration test"
            assert not inspect(connection).get_materialized_view_names(), "Unknown materialized views"
            assert not inspect(connection).get_sequence_names(), "Unknown sequences"
            if tables == TABLES | {"alembic_version"}:
                assert_auxiliary_objects(connection)
            else:
                assert connection.scalar(text("SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal")) == 0
                assert connection.scalar(text("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public'")) == 0
            assert connection.execute(text(
                "SELECT count(*) FROM pg_policies WHERE schemaname='public'"
            )).scalar_one() == 0, "Unknown row policies"
            for name in tables - {"alembic_version"}:
                assert connection.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one() == 0, "Existing data; refusing downgrade"
        migrate(engine, "upgrade", "head")
        with engine.connect() as connection:
            assert set(inspect(connection).get_table_names()) == TABLES | {"alembic_version"}
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            assert compare_metadata(MigrationContext.configure(connection, opts={"compare_server_default": True}), Base.metadata) == []
            for name in TABLES:
                assert {item["name"] for item in inspect(connection).get_check_constraints(name)} == {
                    item.name for item in Base.metadata.tables[name].constraints if isinstance(item, CheckConstraint)
                }, "Unknown or missing CHECK; refusing downgrade"
        migrate(engine, "upgrade", "head")
        migrate(engine, "downgrade", "base")
        with engine.connect() as connection:
            assert set(inspect(connection).get_table_names()) <= {"alembic_version"}
            assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 0
        migrate(engine, "upgrade", "head")
        yield engine
    finally:
        try:
            assert development_inventory(dev) == before, "Development inventory changed"
        finally:
            engine.dispose()
            dev.dispose()


@pytest.mark.integration
def test_schema_matches_dbml_and_metadata(migrated):
    dbml = (ROOT.parent / "docs/design/03-database.dbml").read_text(encoding="utf-8")
    blocks = dict(re.findall(r"^Table (\w+) \{(.*?)^\}", dbml, re.M | re.S))
    types = {"uuid": "UUID", "text": "TEXT", "timestamptz": "TIMESTAMP WITH TIME ZONE",
             "integer": "INTEGER", "date": "DATE", "smallint": "SMALLINT", "boolean": "BOOLEAN", "bigint": "BIGINT", "jsonb": "JSONB"}
    with migrated.connect() as connection:
        inspector = inspect(connection)
        assert set(Base.metadata.tables) == TABLES
        for name in TABLES:
            expected = {}
            pk, unique = [], set()
            for column, kind, attributes in re.findall(r"^  (\w+) (\w+)(?: \[([^\n]*)\])?\s*$", blocks[name], re.M):
                expected[column] = (types[kind], not ("not null" in attributes or "pk" in attributes))
                if "pk" in attributes:
                    pk.append(column)
                if "unique" in attributes:
                    unique.add((column,))
            for columns, attributes in re.findall(r"^    \(([^)]+)\) \[([^]]+)\]", blocks[name], re.M):
                columns = tuple(part.strip() for part in columns.split(","))
                if "pk" in attributes:
                    pk = list(columns)
                if "unique" in attributes:
                    unique.add(columns)
            actual = {c["name"]: (str(c["type"].compile(dialect=connection.dialect)), c["nullable"])
                      for c in inspector.get_columns(name)}
            assert actual == expected, name
            assert inspector.get_pk_constraint(name)["constrained_columns"] == pk
            assert {tuple(c["column_names"]) for c in inspector.get_unique_constraints(name)} == unique
            expected_fk = set()
            for source, target in re.findall(
                r"^Ref: (\w+\.(?:\([^)]*\)|\w+)) > (\w+\.(?:\([^)]*\)|\w+)) \[delete: restrict\]", dbml, re.M
            ):
                source_table, source_columns = source.split(".", 1)
                target_table, target_columns = target.split(".", 1)
                if source_table == name:
                    expected_fk.add((tuple(source_columns.strip("()").replace(" ", "").split(",")), target_table,
                                     tuple(target_columns.strip("()").replace(" ", "").split(","))))
            actual_fk = set()
            for fk in inspector.get_foreign_keys(name):
                assert fk["options"]["ondelete"] == "RESTRICT"
                actual_fk.add((tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"])))
            assert actual_fk == expected_fk, name
        assert compare_metadata(MigrationContext.configure(connection, opts={"compare_server_default": True}), Base.metadata) == []
        assert connection.execute(text("SELECT count(*) FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace AND confmatchtype<>'s'")).scalar_one() == 0


@pytest.fixture
def data(migrated):
    connection = migrated.connect()
    transaction = connection.begin()
    now = datetime.now(timezone.utc)
    ids = {name: uuid4() for name in ["user", "other", "role", "media", "category", "post", "comment", "session", "contact", "audit"]}
    values = {"now": now, "later": now + timedelta(hours=1), **ids}
    statements = [
        "INSERT INTO users VALUES (:user,'alice','alice@example.test','test-hash','active',:now,:now,NULL)",
        "INSERT INTO users VALUES (:other,'bob','bob@example.test','test-hash','active',:now,:now,NULL)",
        "INSERT INTO roles VALUES (:role,'USER','User role')",
        "INSERT INTO user_roles VALUES (:user,:role,:now)",
        "INSERT INTO media_uploads VALUES (:media,:user,'test/key','image/png',1,'ready',:now,:now)",
        "INSERT INTO profiles VALUES (:user,'Alice',NULL,NULL,NULL,NULL,:media,NULL,false,:now)",
        "INSERT INTO categories VALUES (:category,'test','Test','active',:now,:now)",
        "INSERT INTO posts VALUES (:post,:user,:category,:media,'Title','','published',:now,:now,NULL)",
        "INSERT INTO comments VALUES (:comment,:post,:user,'Body','visible',:now,:now,NULL)",
        "INSERT INTO auth_sessions VALUES (:session,:user,'token-digest',:now,:later,NULL)",
        "INSERT INTO contact_messages VALUES (:contact,NULL,'Guest','guest@example.test','Subject','Body','new',:now,:now)",
        "INSERT INTO admin_audit_logs VALUES (:audit,:user,'create','post',CAST(:post AS text),NULL,'{}'::jsonb,:now)",
    ]
    try:
        for statement in statements:
            connection.execute(text(statement), values)
        yield connection, values
    finally:
        transaction.rollback()
        connection.close()


@pytest.mark.integration
def test_valid_data_null_media_and_no_cascade(data):
    connection, values = data
    connection.execute(text("UPDATE profiles SET avatar_media_id=NULL,cover_media_id=NULL WHERE user_id=:user"), values)
    connection.execute(text("UPDATE posts SET media_id=NULL,content='Text only' WHERE id=:post"), values)
    with pytest.raises(IntegrityError) as error, connection.begin_nested():
        connection.execute(text("DELETE FROM users WHERE id=:user"), values)
    assert error.value.orig.sqlstate == "23503"


@pytest.mark.integration
def test_downgrade_refuses_nonempty_tables_without_losing_rows(data):
    connection, _ = data
    cfg = config()
    cfg.attributes["connection"] = connection
    with pytest.raises(RuntimeError, match="nonempty"):
        command.downgrade(cfg, "base")
    assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 2
    assert set(inspect(connection).get_table_names()) == TABLES | {"alembic_version"}


@pytest.mark.integration
def test_model_none_is_sql_null_for_audit_snapshots(data):
    connection, values = data
    with pytest.raises(IntegrityError) as error, connection.begin_nested():
        connection.execute(Base.metadata.tables["admin_audit_logs"].insert().values(
            id=uuid4(), actor_id=values["user"], action="create", target_type="post",
            target_id=str(values["post"]), before_json=None, after_json=None, created_at=values["now"],
        ))
    assert error.value.orig.sqlstate == "23514"


@pytest.mark.integration
@pytest.mark.parametrize("statement,state", [
    ("UPDATE users SET username='alice' WHERE id=:other", "23505"),
    ("UPDATE users SET email='alice@example.test' WHERE id=:other", "23505"),
    ("UPDATE users SET id=:user WHERE id=:other", "23505"),
    ("INSERT INTO roles VALUES (:other,'USER','Duplicate')", "23505"),
    ("INSERT INTO user_roles VALUES (:user,:role,:now)", "23505"),
    ("UPDATE users SET username='Bad Name' WHERE id=:user", "23514"),
    ("UPDATE users SET email='UPPER@EXAMPLE.TEST' WHERE id=:user", "23514"),
    ("UPDATE users SET status='unknown' WHERE id=:user", "23514"),
    ("UPDATE users SET status='deleted' WHERE id=:user", "23514"),
    ("UPDATE users SET deleted_at=:now WHERE id=:user", "23514"),
    ("UPDATE users SET username=NULL WHERE id=:user", "23502"),
    ("UPDATE roles SET code='ROOT' WHERE id=:role", "23514"),
    ("UPDATE profiles SET birth_year=1899 WHERE user_id=:user", "23514"),
    ("UPDATE profiles SET user_id=:other WHERE user_id=:user", "23503"),
    ("UPDATE profiles SET cover_media_id=:category WHERE user_id=:user", "23503"),
    ("UPDATE profiles SET avatar_media_id=NULL,cover_media_id=:media,user_id=:other WHERE user_id=:user", "23503"),
    ("UPDATE posts SET author_id=:other WHERE id=:post", "23503"),
    ("UPDATE posts SET category_id=:other WHERE id=:post", "23503"),
    ("UPDATE media_uploads SET size_bytes=0 WHERE id=:media", "23514"),
    ("UPDATE media_uploads SET mime='video/mp4' WHERE id=:media", "23514"),
    ("UPDATE media_uploads SET status='unknown' WHERE id=:media", "23514"),
    ("UPDATE posts SET title='   ' WHERE id=:post", "23514"),
    ("UPDATE posts SET media_id=NULL,content='' WHERE id=:post", "23514"),
    ("UPDATE posts SET status='deleted' WHERE id=:post", "23514"),
    ("UPDATE posts SET status='unknown' WHERE id=:post", "23514"),
    ("UPDATE categories SET slug='' WHERE id=:category", "23514"),
    ("UPDATE categories SET status='unknown' WHERE id=:category", "23514"),
    ("UPDATE comments SET body='' WHERE id=:comment", "23514"),
    ("UPDATE comments SET status='deleted' WHERE id=:comment", "23514"),
    ("UPDATE comments SET status='unknown' WHERE id=:comment", "23514"),
    ("UPDATE comments SET author_id=:category WHERE id=:comment", "23503"),
    ("UPDATE auth_sessions SET expires_at=created_at WHERE id=:session", "23514"),
    ("UPDATE auth_sessions SET revoked_at=created_at - interval '1 second' WHERE id=:session", "23514"),
    ("UPDATE contact_messages SET body='' WHERE id=:contact", "23514"),
    ("UPDATE contact_messages SET status='unknown' WHERE id=:contact", "23514"),
    ("UPDATE admin_audit_logs SET before_json=NULL,after_json=NULL WHERE id=:audit", "23514"),
    ("UPDATE admin_audit_logs SET action=' ' WHERE id=:audit", "23514"),
])
def test_invalid_data_is_rejected(data, statement, state):
    connection, values = data
    with pytest.raises(IntegrityError) as error, connection.begin_nested():
        connection.execute(text(statement), values)
    assert error.value.orig.sqlstate == state


def test_cli_requires_explicit_test_url(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="TEST_DATABASE_URL"):
        command.upgrade(config(), "head")


@pytest.mark.parametrize("value", [None, "postgresql+psycopg://test:secret-marker@127.0.0.1/aurameme_dev",
    "postgresql+psycopg://test:secret-marker@127.0.0.1/aurameme_test"])
def test_e2e_migrations_require_explicit_separate_database(monkeypatch,value):
    from types import SimpleNamespace
    monkeypatch.delenv('E2E_DATABASE_URL',raising=False)
    if value:monkeypatch.setenv('E2E_DATABASE_URL',value)
    cfg=config();cfg.cmd_opts=SimpleNamespace(x=['target=e2e'])
    with pytest.raises(RuntimeError,match='E2E_DATABASE_URL') as error:
        command.upgrade(cfg,'head')
    assert 'secret-marker' not in str(error.value)


def test_unknown_migration_target_is_refused():
    from types import SimpleNamespace
    cfg=config();cfg.cmd_opts=SimpleNamespace(x=['target=development'])
    with pytest.raises(RuntimeError,match='development is forbidden'):
        command.upgrade(cfg,'head')


@pytest.mark.integration
def test_e2e_migrations_refuse_development_connection(migrated):
    from types import SimpleNamespace
    engine=create_db_engine(load_settings())
    try:
        with engine.begin() as connection:
            cfg=config();cfg.cmd_opts=SimpleNamespace(x=['target=e2e']);cfg.attributes['connection']=connection
            with pytest.raises(RuntimeError,match='only on aurameme_e2e'):
                command.upgrade(cfg,'head')
    finally:engine.dispose()


@pytest.mark.parametrize("url,expected", [
    ("sqlite:///secret-marker", "Invalid TEST_DATABASE_URL"),
    ("postgresql+psycopg://test:secret-marker@127.0.0.1/aurameme_dev", "aurameme_test"),
    ("postgresql+psycopg://test:secret-marker@127.0.0.1:1/aurameme_test", "PostgreSQL migration failed"),
])
def test_cli_rejects_bad_or_unavailable_target(monkeypatch, url, expected, caplog):
    monkeypatch.setenv("TEST_DATABASE_URL", url)
    with pytest.raises(RuntimeError, match=expected) as error:
        command.upgrade(config(), "head")
    assert "secret-marker" not in str(error.value) + caplog.text


@pytest.mark.integration
def test_migrations_refuse_development_connection(migrated):
    engine = create_db_engine(load_settings())
    try:
        with pytest.raises(RuntimeError, match="aurameme_test"):
            migrate(engine, "downgrade", "base")
    finally:
        engine.dispose()


@pytest.mark.integration
def test_migrations_refuse_other_search_path(migrated):
    with migrated.begin() as connection:
        connection.execute(text("SET LOCAL search_path = pg_catalog"))
        cfg = config()
        cfg.attributes["connection"] = connection
        with pytest.raises(RuntimeError, match="public schema"):
            command.upgrade(cfg, "head")
