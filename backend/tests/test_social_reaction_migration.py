"""Prepared0010 data-preservation checks; isolated rollback fixture only."""
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from test_auth import auth,migrated
from test_blog import blog,mutation
from test_comments import comments,add

def migrate(connection,direction,revision,monkeypatch):
    config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"));config.attributes["connection"]=connection
    with monkeypatch.context() as env:
        env.setenv("DATABASE_URL","postgresql+psycopg://unused:synthetic@127.0.0.1:1/aurameme_dev")
        getattr(command,direction)(config,revision)

@pytest.mark.integration
def test_upgrade_keeps_legacy_reaction_fields_and_post_objects(comments,monkeypatch):
    client,c,_,post_id,_=comments
    assert mutation(client,"PUT",f"/posts/{post_id}/reactions",{"reaction_type":"like"}).status_code==200
    before=c.execute(text("SELECT * FROM post_reactions")).all()
    objects=c.execute(text("SELECT oid,relfilenode FROM pg_class WHERE oid='public.posts'::regclass")).one()
    with c.begin_nested():
        migrate(c,"downgrade","0009_vault_open",monkeypatch)
        migrate(c,"upgrade","0010_social_reactions",monkeypatch)
        assert c.execute(text("SELECT * FROM post_reactions")).all()==before
        assert c.execute(text("SELECT oid,relfilenode FROM pg_class WHERE oid='public.posts'::regclass")).one()==objects
        assert c.scalar(text("SELECT count(*) FROM comment_reactions"))==0

@pytest.mark.integration
@pytest.mark.parametrize("kind",["comment","new_post"])
def test_downgrade_never_erases_new_reactions(comments,monkeypatch,kind):
    client,c,_,post_id,_=comments
    if kind=="comment":
        comment=add(client,post_id).json()["id"]
        assert mutation(client,"PUT",f"/comments/{comment}/reactions",{"reaction_type":"fire"}).status_code==200
    else:assert mutation(client,"PUT",f"/posts/{post_id}/reactions",{"reaction_type":"love"}).status_code==200
    with c.begin_nested():
        with pytest.raises(RuntimeError,match="Refusing"):
            migrate(c,"downgrade","0009_vault_open",monkeypatch)
    assert c.scalar(text("SELECT version_num FROM alembic_version"))=="0010_social_reactions"
    assert c.scalar(text("SELECT count(*) FROM "+("comment_reactions" if kind=="comment" else "post_reactions")))==1
