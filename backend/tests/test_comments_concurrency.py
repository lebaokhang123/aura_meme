"""Independent committed PostgreSQL requests with observed row-lock contention."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from app.main import app
from app.models import AuthSession, Category, Comment, MediaUpload, Post, Profile, Role, User, UserRole
from test_auth import ORIGIN, csrf, login, migrated, register
from test_blog import mutation
from test_comments import add, listing


@pytest.fixture
def race_comments(migrated, monkeypatch):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("AUTH_ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["https://testserver"]')
    tag = "m33_" + uuid4().hex
    engine = create_engine(migrated.url, hide_parameters=True, connect_args={
        "application_name": tag, "options": "-c statement_timeout=12000 -c lock_timeout=8000"})
    names = ["comment_" + uuid4().hex[:16] for _ in range(2)]
    category, post_id = uuid4(), uuid4()
    with TestClient(app, base_url=ORIGIN) as owner:
        app.state.auth_session_factory = lambda: Session(engine)
        commenter = TestClient(app, base_url=ORIGIN)
        try:
            for client, name in zip([owner, commenter], names):
                assert register(client, username=name, email=name + "@example.com").status_code == 201
                assert login(client, email=name + "@example.com").status_code == 200
            now = app.state.auth.now()
            with engine.begin() as connection:
                author = connection.scalar(select(User.id).where(User.username == names[0]))
                connection.execute(Category.__table__.insert().values(id=category, slug=tag, name="Race", status="active", created_at=now, updated_at=now))
                connection.execute(Post.__table__.insert().values(id=post_id, author_id=author, category_id=category,
                    title="Race", content="Text", status="published", created_at=now, updated_at=now))
            yield owner, commenter, engine, post_id, tag
        finally:
            commenter.close()
            with engine.begin() as connection:
                ids = list(connection.scalars(select(User.id).where(User.username.in_(names))))
                roles = set(connection.scalars(select(UserRole.role_id).where(UserRole.user_id.in_(ids))))
                connection.execute(Comment.__table__.delete().where(Comment.post_id == post_id))
                connection.execute(Post.__table__.delete().where(Post.id == post_id))
                connection.execute(Category.__table__.delete().where(Category.id == category))
                for model, column in [(AuthSession, AuthSession.user_id), (UserRole, UserRole.user_id), (Profile, Profile.user_id), (User, User.id)]:
                    connection.execute(model.__table__.delete().where(column.in_(ids)))
                for role in roles:
                    assert connection.scalar(select(UserRole.user_id).where(UserRole.role_id == role)) is None
                    connection.execute(Role.__table__.delete().where(Role.id == role))
            engine.dispose()


def wait_for_lock(engine, tag):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            waiting = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:tag AND wait_event_type='Lock'"), {"tag": tag})
        if waiting: return
        time.sleep(0.02)
    raise AssertionError("Requests did not overlap at a PostgreSQL row lock")


@pytest.mark.integration
@pytest.mark.parametrize("action", ["hide", "delete"])
@pytest.mark.parametrize("winner", ["create", "mutation"])
def test_create_vs_post_visibility_mutation(race_comments, action, winner):
    owner, commenter, engine, post_id, tag = race_comments
    owner_token, comment_token = csrf(owner), csrf(commenter)
    locked, release = Event(), Event()
    target = "FOR SHARE" if winner == "create" else "FOR UPDATE"
    def pause_after_lock(conn, cursor, statement, parameters, context, executemany):
        if "FROM posts" in statement and target in statement and not locked.is_set():
            locked.set()
            assert release.wait(7), "Lock holder was not released"
    event.listen(engine, "after_cursor_execute", pause_after_lock)
    def create():
        return mutation(commenter, "POST", f"/posts/{post_id}/comments", {"body": "Race comment"}, comment_token)
    def mutate():
        if action == "delete":
            return mutation(owner, "DELETE", "/posts/" + str(post_id), token=owner_token)
        with engine.begin() as connection:
            connection.execute(select(Post.id).where(Post.id == post_id).with_for_update())
            connection.execute(Post.__table__.update().where(Post.id == post_id).values(status="hidden"))
        return None  # No moderation API is added; this is the real database hide transaction.
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(create if winner == "create" else mutate)
            try:
                assert locked.wait(5)
                second = pool.submit(mutate if winner == "create" else create)
                wait_for_lock(engine, tag)
            finally:
                release.set()
            first_response, second_response = first.result(timeout=15), second.result(timeout=15)
        response = first_response if winner == "create" else second_response
        assert response.status_code == (201 if winner == "create" else 404), response.text
        assert listing(commenter, post_id).status_code == 404
        with engine.connect() as connection:
            assert len(list(connection.scalars(select(Comment.id)))) == (1 if winner == "create" else 0)
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_after_lock)


@pytest.mark.integration
def test_two_deletes_have_one_winner(race_comments):
    owner, commenter, engine, post_id, tag = race_comments
    ident = add(commenter, post_id).json()["id"]
    token = csrf(commenter)
    second = TestClient(app, base_url=ORIGIN)
    second.cookies.update(commenter.cookies)
    locked, release = Event(), Event()
    def pause(conn, cursor, statement, parameters, context, executemany):
        if "FROM comments" in statement and "FOR UPDATE" in statement and not locked.is_set():
            locked.set()
            assert release.wait(7)
    event.listen(engine, "after_cursor_execute", pause)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(mutation, commenter, "DELETE", "/comments/" + ident, None, token)
            try:
                assert locked.wait(5)
                other = pool.submit(mutation, second, "DELETE", "/comments/" + ident, None, token)
                wait_for_lock(engine, tag)
            finally:
                release.set()
            assert [first.result(timeout=15).status_code, other.result(timeout=15).status_code] == [204, 404]
        with engine.connect() as connection:
            row = connection.execute(select(Comment.__table__).where(Comment.id == UUID(ident))).mappings().one()
            assert row["status"] == "deleted" and row["deleted_at"] == row["updated_at"]
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause)
        second.close()


@pytest.mark.integration
def test_comment_commit_failure_cannot_return_201(race_comments):
    owner, commenter, engine, post_id, _ = race_comments
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE FUNCTION m33_commit_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic deferred comment failure'; END $$")
            connection.exec_driver_sql("CREATE CONSTRAINT TRIGGER m33_commit_reject AFTER INSERT ON comments DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION m33_commit_reject()")
        assert add(commenter, post_id).status_code == 500
        with engine.connect() as connection:
            assert list(connection.scalars(select(Comment.id))) == []
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TRIGGER m33_commit_reject ON comments")
            connection.exec_driver_sql("DROP FUNCTION m33_commit_reject()")
