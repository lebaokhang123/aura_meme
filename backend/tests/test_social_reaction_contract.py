"""Draft contract and migration checks without opening PostgreSQL."""
from io import StringIO
from pathlib import Path
from unittest.mock import Mock
import importlib.util

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

KINDS=["like","love","laugh","fire","sad","angry"]
ROOT=Path(__file__).resolve().parents[1]

def migration():
    path=ROOT/"alembic/versions/0010_social_reactions.py"
    spec=importlib.util.spec_from_file_location("social_migration",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_six_reaction_contracts_and_session_security():
    from app.main import app
    contract=app.openapi();schemas=contract["components"]["schemas"]
    assert schemas["ReactionInput"]["properties"]["reaction_type"]["enum"]==KINDS
    assert set(schemas["ReactionCounts"]["properties"])==set(KINDS)
    path=contract["paths"]["/api/v1/comments/{comment_id}/reactions"]
    assert set(path)=={"put","delete"}
    for item in path.values():
        assert item["security"]==[{"sessionCookie":[]}]
        assert {"401","403","404","422"}<=set(item["responses"])
    read=contract["paths"]["/api/v1/comments/{comment_id}/interactions"]["get"]
    assert {} in read["security"] and {"sessionCookie":[]} in read["security"]

def test_comment_model_has_owner_key_foreign_keys_indexes_and_six_types():
    from app.models import Base
    table=Base.metadata.tables["comment_reactions"]
    assert [c.name for c in table.primary_key]==["comment_id","user_id"]
    assert {(f.parent.name,f.target_fullname,f.ondelete) for f in table.foreign_keys}=={
        ("comment_id","comments.id","RESTRICT"),("user_id","users.id","RESTRICT")}
    assert {tuple(c.name for c in index.columns) for index in table.indexes}=={
        ("comment_id","reaction_type"),("user_id",)}
    ddl=str(CreateTable(table).compile(dialect=postgresql.dialect()))
    assert all("'"+kind+"'" in ddl for kind in KINDS)

def test_upgrade_draft_sql_expands_only_reaction_constraint_and_adds_comment_table():
    from app.models import Base
    module=migration();output=StringIO()
    module.op=Operations(MigrationContext.configure(dialect_name="postgresql",opts={"as_sql":True,"output_buffer":output,"target_metadata":Base.metadata}))
    module.upgrade();sql=output.getvalue()
    assert module.down_revision=="0009_vault_open" and module.revision=="0010_social_reactions"
    assert "CREATE TABLE comment_reactions" in sql and "ALTER TABLE post_reactions" in sql
    assert "DROP CONSTRAINT ck_post_reactions_reaction_type;" in sql
    assert "ck_post_reactions_ck_" not in sql
    assert all("'"+kind+"'" in sql for kind in KINDS)
    assert not any(word in sql.upper() for word in ("UPDATE ","DELETE FROM","TRUNCATE","DROP TABLE"))

@pytest.mark.parametrize("comments,new_kinds",[(True,False),(False,True)])
def test_downgrade_refuses_any_loss_before_ddl(comments,new_kinds):
    module=migration();connection=Mock()
    connection.scalar.side_effect=[comments,new_kinds]
    module.op=Mock();module.op.get_bind.return_value=connection
    with pytest.raises(RuntimeError,match="Refusing"):module.downgrade()
    module.op.drop_table.assert_not_called();module.op.drop_constraint.assert_not_called()

def test_safe_downgrade_checks_both_sources_under_lock_before_ddl():
    module=migration();connection=Mock();connection.scalar.side_effect=[False,False]
    module.op=Mock();module.op.get_bind.return_value=connection
    module.downgrade()
    assert "ACCESS EXCLUSIVE" in connection.exec_driver_sql.call_args_list[2].args[0]
    assert connection.scalar.call_count==2
    module.op.drop_table.assert_called_once_with("comment_reactions")

@pytest.mark.parametrize("target",["post","comment"])
def test_six_count_sql_compiles_and_dto_positions_match(target):
    from uuid import uuid4
    from app.interactions import get_post_interactions
    from app.comment_reactions import get_comment_interactions
    ident=uuid4();db=Mock()
    row=(ident,1,2,3,4,5,6,7,"love",True) if target=="post" else (ident,1,2,3,4,5,6,"sad")
    def execute(statement):
        sql=str(statement.compile(dialect=postgresql.dialect()))
        assert "active" not in sql  # status values stay bound, never interpolated.
        assert "reaction_type" in sql and "deleted_at IS NULL" in sql
        response=Mock();response.one_or_none.return_value=row;return response
    db.execute.side_effect=execute
    result=(get_post_interactions if target=="post" else get_comment_interactions)(ident,reader=(db,None))
    assert result.reaction_counts.model_dump()==dict(zip(KINDS,range(1,7)))
    assert result.viewer_reaction==("love" if target=="post" else "sad")
    if target=="post":assert result.comments_count==7 and result.bookmarked is True
@pytest.mark.parametrize('e2e,key,url,allowed', [
    (False, 'TEST_DATABASE_URL', 'postgresql+psycopg://aurameme_test:synthetic@127.0.0.1:5432/aurameme_test', True),
    (True, 'E2E_DATABASE_URL', 'postgresql+psycopg://aurameme_e2e_app:synthetic@127.0.0.1:5432/aurameme_e2e', True),
    (True, 'E2E_DATABASE_URL', 'postgresql+psycopg://aurameme_demo:synthetic@127.0.0.1:5432/aurameme_demo', False),
    (True, 'E2E_DATABASE_URL', 'postgresql+psycopg://postgres:synthetic@127.0.0.1:5432/aurameme_e2e', False),
    (True, 'E2E_DATABASE_URL', 'postgresql+psycopg://aurameme_e2e_app:synthetic@example.com:5432/aurameme_e2e', False),
    (True, 'E2E_DATABASE_URL', 'postgresql+psycopg://aurameme_e2e_app:synthetic@127.0.0.1:5432/aurameme_e2e?options=bad', False),
    (True, 'TEST_DATABASE_URL', 'postgresql+psycopg://aurameme_test:synthetic@127.0.0.1:5432/aurameme_test', False),
])
def test_social_browser_explicit_target_guard(tmp_path, e2e, key, url, allowed):
    from run_social_browser import browser_target
    config = tmp_path / '.env'; config.write_text(key+'='+url, encoding='utf-8')
    if allowed:
        assert browser_target(config, e2e)[0] == url
    else:
        with pytest.raises((AssertionError, ValueError)):
            browser_target(config, e2e)
