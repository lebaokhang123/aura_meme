"""Prepared contention tests; run only after approved0010 on isolated test DB."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event,text
from app.main import app
from test_auth import auth,migrated,ORIGIN,csrf
from test_blog import mutation
from test_comments import add
from test_comments_concurrency import race_comments,wait_for_lock

@pytest.mark.integration
@pytest.mark.parametrize("second_method",["PUT","DELETE"])
def test_duplicate_comment_reactions_serialize_without_double_count(race_comments,second_method):
    owner,actor,engine,post_id,tag=race_comments
    result=add(owner,post_id);assert result.status_code==201
    ident=UUID(result.json()["id"]);path=f"/comments/{ident}/reactions"
    second=TestClient(app,base_url=ORIGIN);second.cookies.update(actor.cookies)
    token=csrf(actor);locked,release=Event(),Event()
    def pause(conn,cursor,statement,parameters,context,executemany):
        if "FROM comments" in statement and "FOR UPDATE" in statement and not locked.is_set():
            locked.set();assert release.wait(7)
    event.listen(engine,"after_cursor_execute",pause)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(mutation,actor,"PUT",path,{"reaction_type":"love"},token)
            try:
                assert locked.wait(5)
                other=pool.submit(mutation,second,second_method,path,{"reaction_type":"angry"} if second_method=="PUT" else None,token)
                wait_for_lock(engine,tag)
            finally:release.set()
            assert first.result(timeout=15).status_code==200
            assert other.result(timeout=15).status_code==(200 if second_method=="PUT" else 204)
        with engine.connect() as c:
            rows=c.execute(text("SELECT reaction_type FROM comment_reactions WHERE comment_id=:id"),{"id":ident}).scalars().all()
            assert rows==(["angry"] if second_method=="PUT" else [])
    finally:
        release.set();event.remove(engine,"after_cursor_execute",pause);second.close()
        with engine.begin() as c:c.execute(text("DELETE FROM comment_reactions WHERE comment_id=:id"),{"id":ident})
