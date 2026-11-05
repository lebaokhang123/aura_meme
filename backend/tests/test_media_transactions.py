"""Committed transactions, concurrency and a real process-crash window on test-only resources."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.main import app
from app.models import AuthSession, MediaUpload, Profile, Role, User, UserRole
from test_auth import ORIGIN, csrf, login, migrated, register
from test_media import picture, upload


@pytest.fixture
def committed_media(migrated, tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("AUTH_ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["https://testserver"]')
    root = tmp_path / "uploads"
    monkeypatch.setenv("MEDIA_STORAGE_ROOT", str(root))
    engine = create_engine(migrated.url, hide_parameters=True,
                          connect_args={"options": "-c statement_timeout=10000 -c lock_timeout=3000"})
    names = ["media_" + uuid4().hex[:16] for _ in range(2)]
    with TestClient(app, base_url=ORIGIN) as first:
        app.state.auth_session_factory = lambda: Session(engine)
        second = TestClient(app, base_url=ORIGIN)
        try:
            for client, name in zip([first, second], names):
                assert register(client, username=name, email=name + "@example.com").status_code == 201
                assert login(client, email=name + "@example.com").status_code == 200
            yield first, second, engine, root
        finally:
            second.close()
            with Session(engine) as db, db.begin():
                ids = list(db.scalars(select(User.id).where(User.username.in_(names))))
                roles = list(db.scalars(select(UserRole.role_id).where(UserRole.user_id.in_(ids))))
                db.execute(MediaUpload.__table__.delete().where(MediaUpload.owner_id.in_(ids)))
                for model, column in [(AuthSession, AuthSession.user_id), (UserRole, UserRole.user_id),
                                      (Profile, Profile.user_id), (User, User.id)]:
                    db.execute(model.__table__.delete().where(column.in_(ids)))
                for role in set(roles):
                    assert db.scalar(select(UserRole.user_id).where(UserRole.role_id == role)) is None
                    db.execute(Role.__table__.delete().where(Role.id == role))
            engine.dispose()
            if root.exists():
                for file in root.iterdir():
                    assert file.is_file() and not file.is_symlink()
                    file.unlink()
                assert list(root.iterdir()) == []


@pytest.mark.integration
def test_real_commit_failure_removes_only_new_object(committed_media):
    first, second, engine, root = committed_media
    baseline = upload(first)
    assert baseline.status_code == 201
    old = {file.name: file.read_bytes() for file in root.iterdir()}
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE FUNCTION m32_commit_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic deferred COMMIT rejection'; END $$")
            connection.exec_driver_sql("CREATE CONSTRAINT TRIGGER m32_commit_reject AFTER INSERT ON media_uploads DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION m32_commit_reject()")
        response = upload(second)
        assert response.status_code == 500, response.text
        assert {file.name: file.read_bytes() for file in root.iterdir()} == old
        with Session(engine) as db:
            assert list(db.scalars(select(MediaUpload.id))) == [UUID(baseline.json()["id"])]
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TRIGGER m32_commit_reject ON media_uploads")
            connection.exec_driver_sql("DROP FUNCTION m32_commit_reject()")


@pytest.mark.integration
def test_lost_commit_acknowledgement_preserves_committed_bytes(committed_media, caplog):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    first, second, engine, root = committed_media
    token = csrf(first)
    class LostAcknowledgementSession(Session):
        pass
    @event.listens_for(LostAcknowledgementSession, "after_flush")
    def track_media(db, context):
        if any(isinstance(row, MediaUpload) for row in db.new):
            db.info["uploaded"] = True
    @event.listens_for(LostAcknowledgementSession, "after_commit")
    def lose_ack(db):
        if db.info.get("uploaded"):
            raise OperationalError("COMMIT", {}, RuntimeError("synthetic lost acknowledgement"))
    app.state.auth_session_factory = lambda: LostAcknowledgementSession(engine)
    response = first.post("/api/v1/media", files={"file": ("x.png", picture(), "image/png")},
                          headers={"Origin": ORIGIN, "X-CSRF-Token": token})
    assert response.status_code == 500
    assert "media_commit_uncertain" in caplog.text and "reconcile_required" in caplog.text
    with Session(engine) as db:
        key = db.scalars(select(MediaUpload.object_key)).one()
    assert (root / key).read_bytes() == picture()


def test_storage_pins_exact_object_during_compensation(tmp_path):
    from app.storage import LocalObject
    root = tmp_path / "uploads"
    moved = tmp_path / "moved"
    saved = LocalObject(root, "png", picture())
    try:
        if os.name == "nt":
            with pytest.raises(OSError): root.rename(moved)
            with pytest.raises(OSError): (root / saved.key).rename(root / "replacement")
        else:
            root.rename(moved)
        saved.discard()
    finally:
        saved.close()
    assert list((root if os.name == "nt" else moved).iterdir()) == []


@pytest.mark.integration
@pytest.mark.parametrize("one_fails", [False, True])
def test_concurrent_uploads_and_cleanup_isolation(committed_media, one_fails):
    first, second, engine, root = committed_media
    token_a, token_b = csrf(first), csrf(second)
    if one_fails:
        with engine.begin() as connection:
            owner_b = connection.scalar(select(User.id).where(User.email == second.get("/api/v1/users/me").json()["email"]))
            connection.exec_driver_sql("CREATE FUNCTION m32_concurrent_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.owner_id = '" + str(owner_b) + "'::uuid THEN RAISE EXCEPTION 'synthetic insert rejection'; END IF; RETURN NEW; END $$")
            connection.exec_driver_sql("CREATE TRIGGER m32_concurrent_reject BEFORE INSERT ON media_uploads FOR EACH ROW EXECUTE FUNCTION m32_concurrent_reject()")
    def send(client, token):
        return client.post("/api/v1/media", files={"file": ("../same.png", picture(), "image/png")},
                           headers={"Origin": ORIGIN, "X-CSRF-Token": token})
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(send, client, token) for client, token in [(first, token_a), (second, token_b)]]
            responses = [future.result(timeout=15) for future in futures]
        assert [response.status_code for response in responses] == [201, 500 if one_fails else 201]
        with Session(engine) as db:
            keys = set(db.scalars(select(MediaUpload.object_key)))
        assert len(keys) == (1 if one_fails else 2)
        assert {file.name for file in root.iterdir()} == keys
        assert all(file.read_bytes() == picture() for file in root.iterdir())
    finally:
        if one_fails:
            with engine.begin() as connection:
                connection.exec_driver_sql("DROP TRIGGER m32_concurrent_reject ON media_uploads")
                connection.exec_driver_sql("DROP FUNCTION m32_concurrent_reject()")


@pytest.mark.integration
def test_crash_between_file_and_database_leaves_identifiable_orphan(committed_media):
    first, second, engine, root = committed_media
    script = "from pathlib import Path; from app.storage import LocalObject; import os,sys; saved=LocalObject(Path(sys.argv[1]),'png',bytes.fromhex(sys.argv[2])); print(saved.key,flush=True); os._exit(19)"
    process = subprocess.run([sys.executable, "-c", script, str(root), picture().hex()],
                             capture_output=True, text=True, timeout=15)
    assert process.returncode == 19
    key = process.stdout.strip()
    from app.storage import KEY
    assert KEY.fullmatch(key)
    with Session(engine) as db:
        assert db.scalar(select(MediaUpload.id).where(MediaUpload.object_key == key)) is None
    assert (root / key).read_bytes() == picture()
    # Manual reconciliation must compare DB keys first; never blanket-delete a real root.
    (root / key).unlink()
    assert list(root.iterdir()) == []
