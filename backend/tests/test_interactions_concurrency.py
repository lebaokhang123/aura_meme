"""Independent PostgreSQL connections; observed lock contention, exact fixture cleanup."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.main import app
from test_auth import migrated, ORIGIN, csrf
from test_blog import mutation
from test_comments_concurrency import race_comments, wait_for_lock


@pytest.mark.integration
@pytest.mark.parametrize("suffix,table", [("reactions", "post_reactions"), ("bookmark", "post_bookmarks")])
@pytest.mark.parametrize("second_method", ["PUT", "DELETE"])
def test_duplicate_or_remove_requests_are_serialized(race_comments, suffix, table, second_method):
    _, actor, engine, post_id, tag = race_comments
    second = TestClient(app, base_url=ORIGIN)
    second.cookies.update(actor.cookies)
    token = csrf(actor)
    locked, release = Event(), Event()
    def pause(conn, cursor, statement, parameters, context, executemany):
        if "FROM posts" in statement and "FOR SHARE" in statement and not locked.is_set():
            locked.set()
            assert release.wait(7)
    event.listen(engine, "after_cursor_execute", pause)
    path = f"/posts/{post_id}/{suffix}"
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(mutation, actor, "PUT", path, {"reaction_type": "like"}, token)
            try:
                assert locked.wait(5)
                other = pool.submit(mutation, second, second_method, path, {"reaction_type": "fire"}, token)
                wait_for_lock(engine, tag)
            finally:
                release.set()
            assert first.result(timeout=15).status_code == (200 if suffix == "reactions" else 204)
            assert other.result(timeout=15).status_code == (200 if suffix == "reactions" and second_method == "PUT" else 204)
        with engine.connect() as connection:
            assert connection.scalar(text(f"SELECT count(*) FROM {table} WHERE post_id=:id"), {"id": post_id}) == (1 if second_method == "PUT" else 0)
            if suffix == "reactions" and second_method == "PUT":
                assert connection.scalar(text("SELECT reaction_type FROM post_reactions WHERE post_id=:id"), {"id": post_id}) == "fire"
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause)
        second.close()
        with engine.begin() as connection:
            connection.execute(text(f"DELETE FROM {table} WHERE post_id=:id"), {"id": post_id})


@pytest.mark.integration
@pytest.mark.parametrize("suffix,table", [("reactions", "post_reactions"), ("bookmark", "post_bookmarks")])
def test_hide_wins_before_interaction_and_commit_failure_is_atomic(race_comments, suffix, table):
    _, actor, engine, post_id, _ = race_comments
    path = f"/posts/{post_id}/{suffix}"
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE FUNCTION m61a_commit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic deferred interaction'; END $$")
            connection.exec_driver_sql(f"CREATE CONSTRAINT TRIGGER m61a_commit_fail AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION m61a_commit_fail()")
        response = mutation(actor, "PUT", path, {"reaction_type": "like"})
        assert response.status_code == 500 and "synthetic" not in response.text
        with engine.begin() as connection:
            assert connection.scalar(text(f"SELECT count(*) FROM {table} WHERE post_id=:id"), {"id": post_id}) == 0
            connection.execute(text("UPDATE posts SET status='hidden' WHERE id=:id"), {"id": post_id})
        assert mutation(actor, "PUT", path, {"reaction_type": "like"}).status_code == 404
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(f"DROP TRIGGER m61a_commit_fail ON {table}")
            connection.exec_driver_sql("DROP FUNCTION m61a_commit_fail()")
            connection.execute(text(f"DELETE FROM {table} WHERE post_id=:id"), {"id": post_id})
