"""Opt-in, committed Aura V1 races on a fresh dedicated E2E database; evidence is retained."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import os
import secrets
from threading import Event
import time
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.main import app
from app.models import AuraLedger, AuraRewardEvent, Base, DailyCheckin, Role, UserProgress, UserRole, WalletTransaction
from schema_guard import assert_auxiliary_objects

ORIGIN = "https://testserver"
PASSWORD = "Synthetic Aura concurrency password!"


def e2e_target(value, token):
    """Validate before creating any engine, without exposing secret inputs."""
    try:
        target = make_url(value)
        run = UUID(token)
        safe = (target.drivername == "postgresql+psycopg" and target.host in {"127.0.0.1", "localhost", "::1"}
            and target.port == 55434 and target.database == "aurameme_e2e" and target.username == "aurameme_e2e_app"
            and not target.query and run.version == 4 and str(run) == token)
    except (ArgumentError, ValueError, TypeError, AttributeError):
        safe = False
    if not safe:
        pytest.fail("Aura E2E requires dedicated loopback database/role, port 55434, no URL overrides and a fresh UUID4 run token", pytrace=False)
    return target, run


@pytest.mark.parametrize("url,token", [
    ("", str(uuid4())),
    ("sqlite:///aurameme_e2e", str(uuid4())),
    ("postgresql+psycopg://aurameme_e2e_app:synthetic@remote.invalid:55434/aurameme_e2e", str(uuid4())),
    ("postgresql+psycopg://aurameme_e2e_app:synthetic@127.0.0.1:5432/aurameme_e2e", str(uuid4())),
    ("postgresql+psycopg://aurameme_e2e_app:synthetic@127.0.0.1:55434/aurameme_demo", str(uuid4())),
    ("postgresql+psycopg://postgres:synthetic@127.0.0.1:55434/aurameme_e2e", str(uuid4())),
    ("postgresql+psycopg://aurameme_e2e_app:synthetic@127.0.0.1:55434/aurameme_e2e?options=bad", str(uuid4())),
    ("postgresql+psycopg://aurameme_e2e_app:synthetic@127.0.0.1:55434/aurameme_e2e", "reused-run"),
])
def test_aura_e2e_guard_rejects_unsafe_target(url, token):
    with pytest.raises(pytest.fail.Exception, match="dedicated loopback"):
        e2e_target(url, token)


def csrf(client):
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def mutation(client, method, path, body=None, token=None):
    return client.request(method, "/api/v1" + path, json=body,
        headers={"Origin": ORIGIN, "X-CSRF-Token": token or csrf(client)})


@pytest.fixture(scope="module")
def aura_e2e():
    if os.environ.get("AURA_V1_E2E_OPT_IN") != "1":
        pytest.skip("Committed Aura races require explicit AURA_V1_E2E_OPT_IN=1; no database was accessed")
    target, run = e2e_target(os.environ.get("AURA_V1_E2E_DATABASE_URL", ""), os.environ.get("AURA_V1_E2E_RUN_TOKEN", ""))
    tag = "aura_v1_race_" + run.hex
    engine = create_engine(target, hide_parameters=True, connect_args={"connect_timeout": 3,
        "application_name": tag, "options": "-c statement_timeout=18000 -c lock_timeout=12000"})
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            assert tuple(connection.execute(text("SELECT current_database(),current_user,current_schema()")).one()) == (
                "aurameme_e2e", "aurameme_e2e_app", "public"), "Unsafe Aura E2E identity"
            assert not connection.scalar(text("SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname=current_user"))
            assert not connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()")), "Dedicated database has another active connection"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0012_aura_v1"
            from app.demo import reviewed_demo_schema
            reviewed_demo_schema(connection)
            assert_auxiliary_objects(connection)
            assert not connection.scalar(text("SELECT count(*) FROM pg_policies WHERE schemaname='public'"))
            for table in Base.metadata.sorted_tables:
                assert connection.scalar(select(func.count()).select_from(table)) == 0, "Refusing existing business rows; evidence must never be reset"
        with ExitStack() as stack:
            patch = stack.enter_context(pytest.MonkeyPatch.context())
            patch.setenv("DATABASE_URL", target.render_as_string(hide_password=False))
            patch.setenv("AUTH_SIGNING_KEY", secrets.token_hex(32))
            patch.setenv("AUTH_ENVIRONMENT", "production")
            patch.setenv("AUTH_ALLOWED_ORIGINS", '["https://testserver"]')
            stack.enter_context(TestClient(app, base_url=ORIGIN))
            app.state.auth_session_factory = lambda: Session(engine)
            clients = []
            sequence = 0

            def account():
                nonlocal sequence
                sequence += 1
                name = "av1_" + run.hex[:8] + "_" + uuid4().hex[:12]
                client = TestClient(app, base_url=ORIGIN, client=("192.0.2." + str(sequence), 50000))
                clients.append(client)
                stack.callback(client.close)
                body = {"username": name, "email": name + "@example.com", "password": PASSWORD, "display_name": "Synthetic Aura race"}
                response = mutation(client, "POST", "/auth/register", body)
                assert response.status_code == 201, response.text
                ident = UUID(response.json()["id"])
                response = mutation(client, "POST", "/auth/login", {"email": body["email"], "password": PASSWORD})
                assert response.status_code == 200, response.text
                return client, ident

            admin, admin_id = account()
            with Session(engine) as db, db.begin():
                from app.aura_runtime import publish_v1
                role_id = uuid4()
                db.add(Role(id=role_id, code="ADMIN", description="Fresh isolated concurrency run"))
                db.flush()
                db.add(UserRole(user_id=admin_id, role_id=role_id, granted_at=app.state.auth.now()))
                db.flush()
                publish_v1(db, admin_id, app.state.auth.now())
            response = mutation(admin, "POST", "/admin/categories", {"name": "Aura concurrency", "slug": "av1-" + run.hex})
            assert response.status_code == 201, response.text
            category = response.json()["id"]

            def post(client):
                response = mutation(client, "POST", "/posts", {"content": "Synthetic concurrency evidence", "category_id": category,
                    "status": "published", "request_id": str(uuid4())})
                assert response.status_code == 201, response.text
                return UUID(response.json()["id"])

            yield SimpleNamespace(engine=engine, tag=tag, account=account, post=post, clients=clients)
    except SQLAlchemyError:
        pytest.fail("Isolated Aura E2E database operation failed; credentials and connection details suppressed", pytrace=False)
    finally:
        engine.dispose()  # All committed synthetic rows and immutable reward evidence remain in place.


def race(fixture, first, second):
    """Observe real advisory-lock contention rather than trusting thread scheduling."""
    held, release = Event(), Event()

    def pause(connection, cursor, statement, parameters, context, executemany):
        if "pg_advisory_xact_lock" in statement and not held.is_set():
            held.set()
            assert release.wait(12), "Aura mutation gate was not released"

    event.listen(fixture.engine, "after_cursor_execute", pause)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(first)
            try:
                assert held.wait(5), "First request did not acquire the Aura gate"
                two = pool.submit(second)
                deadline = time.monotonic() + 5
                waiting = False
                while time.monotonic() < deadline:
                    with fixture.engine.connect() as connection:
                        waiting = bool(connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:tag AND wait_event_type='Lock' AND wait_event='advisory'"), {"tag": fixture.tag}))
                    if waiting:
                        break
                    time.sleep(0.02)
                assert waiting, "No real PostgreSQL advisory-lock contention observed"
            finally:
                release.set()
            return one.result(timeout=20), two.result(timeout=20)
    finally:
        release.set()
        event.remove(fixture.engine, "after_cursor_execute", pause)


@pytest.mark.integration
def test_parallel_checkin_commits_one_receipt_and_15_xp(aura_e2e):
    client, owner = aura_e2e.account()
    second = TestClient(app, base_url=ORIGIN, client=("192.0.2.200", 50000))
    second.cookies.update(client.cookies)
    try:
        token = csrf(client)
        responses = race(aura_e2e, lambda: mutation(client, "POST", "/aura/check-in", token=token),
            lambda: mutation(second, "POST", "/aura/check-in", token=token))
        assert [response.status_code for response in responses] == [200, 200]
        assert sorted(response.json()["already_checked_in"] for response in responses) == [False, True]
        assert sorted(response.json()["earned_xp_delta"] for response in responses) == [0, 15]
        with Session(aura_e2e.engine) as db:
            assert db.scalar(select(func.count()).select_from(DailyCheckin).where(DailyCheckin.user_id == owner)) == 1
            entries = list(db.scalars(select(AuraLedger).where(AuraLedger.user_id == owner)))
            assert len(entries) == 1 and entries[0].base_xp == 15 and entries[0].bonus_xp == 0
            assert db.get(UserProgress, owner).aura_xp_earned == 15
            assert db.scalar(select(func.count()).select_from(WalletTransaction).where(WalletTransaction.user_id == owner)) == 0
    finally:
        second.close()


@pytest.mark.integration
def test_mutual_reactions_finish_without_user_lock_deadlock(aura_e2e):
    first, first_id = aura_e2e.account()
    second, second_id = aura_e2e.account()
    first_post, second_post = aura_e2e.post(first), aura_e2e.post(second)
    first_token, second_token = csrf(first), csrf(second)
    responses = race(aura_e2e,
        lambda: mutation(first, "PUT", f"/posts/{second_post}/reactions", {"reaction_type": "like"}, first_token),
        lambda: mutation(second, "PUT", f"/posts/{first_post}/reactions", {"reaction_type": "fire"}, second_token))
    assert [response.status_code for response in responses] == [200, 200]
    with Session(aura_e2e.engine) as db:
        for owner in (first_id, second_id):
            assert db.get(UserProgress, owner).aura_xp_earned == 13
            assert db.scalar(select(func.count()).select_from(AuraLedger).where(AuraLedger.user_id == owner, AuraLedger.event_type == "reaction")) == 2


@pytest.mark.integration
def test_delete_readd_cannot_reclaim_reaction_or_comment_rewards(aura_e2e):
    owner, owner_id = aura_e2e.account()
    actor, actor_id = aura_e2e.account()
    post_id = aura_e2e.post(owner)
    path = f"/posts/{post_id}/reactions"
    for _ in range(2):
        assert mutation(actor, "PUT", path, {"reaction_type": "like"}).status_code == 200
        assert mutation(actor, "DELETE", path).status_code == 204
    for _ in range(2):
        response = mutation(actor, "POST", f"/posts/{post_id}/comments", {"body": "Synthetic no-farming comment", "request_id": str(uuid4())})
        assert response.status_code == 201, response.text
        assert mutation(actor, "DELETE", "/comments/" + response.json()["id"]).status_code == 204
    with Session(aura_e2e.engine) as db:
        assert db.get(UserProgress, actor_id).aura_xp_earned == 0
        assert db.get(UserProgress, owner_id).aura_xp_earned == 10
        for kind in ("reaction", "comment"):
            assert db.scalar(select(func.count()).select_from(AuraRewardEvent).where(AuraRewardEvent.post_id == post_id, AuraRewardEvent.kind == kind)) == 1
            assert db.scalar(select(func.count()).select_from(AuraLedger).where(AuraLedger.source_post_id == post_id, AuraLedger.event_type == kind)) == 2
        reversals = list(db.scalars(select(AuraLedger).where(AuraLedger.source_post_id == post_id, AuraLedger.event_type == "reversal")))
        assert len(reversals) == len({entry.reverses_id for entry in reversals}) == 4
        assert sum(entry.base_xp for entry in reversals) == -8


@pytest.mark.integration
def test_parallel_last_actor_slot_keeps_author_awards_independent(aura_e2e):
    owner, owner_id = aura_e2e.account()
    actor, actor_id = aura_e2e.account()
    posts = [aura_e2e.post(owner) for _ in range(11)]
    for post_id in posts[:9]:
        assert mutation(actor, "PUT", f"/posts/{post_id}/reactions", {"reaction_type": "like"}).status_code == 200
    second = TestClient(app, base_url=ORIGIN, client=("192.0.2.201", 50000))
    second.cookies.update(actor.cookies)
    try:
        token = csrf(actor)
        responses = race(aura_e2e,
            lambda: mutation(actor, "PUT", f"/posts/{posts[9]}/reactions", {"reaction_type": "like"}, token),
            lambda: mutation(second, "PUT", f"/posts/{posts[10]}/reactions", {"reaction_type": "like"}, token))
        assert [response.status_code for response in responses] == [200, 200]
        with Session(aura_e2e.engine) as db:
            assert db.get(UserProgress, actor_id).aura_xp_earned == 10
            assert db.get(UserProgress, owner_id).aura_xp_earned == 42
            for ident, expected in ((actor_id, 10), (owner_id, 11)):
                assert db.scalar(select(func.count()).select_from(AuraLedger).where(AuraLedger.user_id == ident, AuraLedger.event_type == "reaction")) == expected
            assert db.scalar(select(func.count()).select_from(AuraRewardEvent).where(AuraRewardEvent.actor_id == actor_id, AuraRewardEvent.kind == "reaction")) == 11
    finally:
        second.close()

@pytest.mark.integration
def test_progress_read_and_incoming_reward_keep_coherent_snapshots(aura_e2e):
    owner, owner_id = aura_e2e.account()
    actor, actor_id = aura_e2e.account()
    for reader_first in (True, False):
        post_id = aura_e2e.post(owner)
        before = owner.get("/api/v1/aura/progress")
        assert before.status_code == 200, before.text
        baseline = before.json()["earned_xp"]
        token = csrf(actor)
        held, release = Event(), Event()

        def pause(connection, cursor, statement, parameters, context, executemany):
            reading = "FROM user_progress" in statement and "FOR UPDATE" not in statement
            writing = "INSERT INTO aura_ledger" in statement and isinstance(parameters, dict) and parameters.get("user_id") == owner_id
            if (reading if reader_first else writing) and not held.is_set():
                held.set()
                assert release.wait(12), "Progress/reward transaction was not released"

        def read():
            return owner.get("/api/v1/aura/progress")

        def reward():
            return mutation(actor, "PUT", f"/posts/{post_id}/reactions", {"reaction_type": "like"}, token)

        event.listen(aura_e2e.engine, "after_cursor_execute", pause)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(read if reader_first else reward)
                try:
                    assert held.wait(5), "Expected progress/reward statement was not reached"
                    second = pool.submit(reward if reader_first else read)
                    deadline = time.monotonic() + 5
                    waiting = False
                    while time.monotonic() < deadline:
                        with aura_e2e.engine.connect() as connection:
                            waiting = bool(connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:tag AND wait_event_type='Lock' AND wait_event<>'advisory'"), {"tag": aura_e2e.tag}))
                        if waiting:
                            break
                        time.sleep(0.02)
                    assert waiting, "No real User/FK lock contention observed"
                finally:
                    release.set()
                responses = [first.result(timeout=20), second.result(timeout=20)]
            assert [response.status_code for response in responses] == [200, 200]
            snapshot = responses[0 if reader_first else 1].json()
            assert snapshot["earned_xp"] == baseline + (0 if reader_first else 2)
            assert snapshot["bonus_xp"] == 0 and snapshot["total_xp"] == snapshot["earned_xp"]
        finally:
            release.set()
            event.remove(aura_e2e.engine, "after_cursor_execute", pause)
        final = owner.get("/api/v1/aura/progress")
        assert final.status_code == 200, final.text
        assert final.json()["earned_xp"] == baseline + 2
        with Session(aura_e2e.engine) as db:
            ledger = db.scalar(select(func.sum(AuraLedger.base_xp)).where(AuraLedger.user_id == owner_id))
            state = db.get(UserProgress, owner_id)
            assert state.aura_xp_earned == ledger == final.json()["earned_xp"]
            assert state.aura_xp_bonus == 0
    with Session(aura_e2e.engine) as db:
        assert db.get(UserProgress, actor_id).aura_xp_earned == 2
