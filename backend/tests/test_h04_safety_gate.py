"""Targeted safety gate tests for H04 benchmark, simulator, and integration harness."""
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "h04"))
import safety_guard  # noqa: E402


def _mock_docker_ok(cmd, **kwargs):
    if cmd[:2] == ["docker", "inspect"]:
        return subprocess.CompletedProcess(cmd, 0, stdout="true\n", stderr="")
    if cmd[:2] == ["docker", "port"]:
        return subprocess.CompletedProcess(cmd, 0, stdout="127.0.0.1:55450\n", stderr="")
    raise AssertionError(f"Unexpected subprocess command: {cmd}")


def _mock_engine_factory(db_name="aurameme_test", revision="0018_canonical_asset_filenames", has_user=1, has_post=1):
    conn = MagicMock()

    def execute(stmt, params=None):
        sql = str(stmt)
        res = MagicMock()
        if "alembic_version" in sql:
            res.one.return_value = (db_name, revision)
        elif "FROM users" in sql:
            res.scalar.return_value = has_user
        elif "FROM posts" in sql:
            res.scalar.return_value = has_post
        return res

    conn.execute.side_effect = execute
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    return engine


def test_verify_isolated_postgres_accepts_valid_env(tmp_path, monkeypatch):
    manifest = tmp_path / "seed_manifest.json"
    manifest.write_text('{"post_1_id": "81883f01-ce34-50ed-a693-8be124c9509e"}', encoding="utf-8")
    monkeypatch.setattr(safety_guard.subprocess, "run", _mock_docker_ok)
    monkeypatch.setattr(safety_guard, "create_engine", lambda *a, **kw: _mock_engine_factory())

    info = safety_guard.verify_isolated_postgres(
        "postgresql+psycopg://u:p@127.0.0.1:55450/aurameme_test",
        manifest,
    )
    assert info["database"] == "aurameme_test"
    assert info["alembic_revision"] == "0018_canonical_asset_filenames"
    assert info["fixture_verified"] is True


@pytest.mark.parametrize(
    "bad_url",
    [
        "postgresql+psycopg://u:p@localhost:55450/aurameme_test",
        "postgresql+psycopg://u:p@127.0.0.1:5432/aurameme_test",
        "postgresql+psycopg://u:p@127.0.0.1:55450/aurameme_demo",
        "postgresql+psycopg://u:p@127.0.0.1:55450/aurameme_dev",
    ],
)
def test_verify_isolated_postgres_rejects_wrong_url(tmp_path, bad_url):
    manifest = tmp_path / "seed_manifest.json"
    manifest.write_text('{"post_1_id": "81883f01-ce34-50ed-a693-8be124c9509e"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="DB Identity Guard failed"):
        safety_guard.verify_isolated_postgres(bad_url, manifest)


def test_verify_isolated_postgres_rejects_wrong_revision(tmp_path, monkeypatch):
    manifest = tmp_path / "seed_manifest.json"
    manifest.write_text('{"post_1_id": "81883f01-ce34-50ed-a693-8be124c9509e"}', encoding="utf-8")
    monkeypatch.setattr(safety_guard.subprocess, "run", _mock_docker_ok)
    monkeypatch.setattr(safety_guard, "create_engine", lambda *a, **kw: _mock_engine_factory(revision="0017_old"))

    with pytest.raises(RuntimeError, match="DB Identity Guard failed"):
        safety_guard.verify_isolated_postgres(
            "postgresql+psycopg://u:p@127.0.0.1:55450/aurameme_test",
            manifest,
        )


def test_verify_isolated_postgres_rejects_stopped_container_or_bad_mapping(tmp_path, monkeypatch):
    manifest = tmp_path / "seed_manifest.json"
    manifest.write_text('{"post_1_id": "81883f01-ce34-50ed-a693-8be124c9509e"}', encoding="utf-8")

    monkeypatch.setattr(
        safety_guard.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="false\n", stderr=""),
    )
    with pytest.raises(RuntimeError, match="is not running"):
        safety_guard.verify_isolated_postgres("postgresql+psycopg://u:p@127.0.0.1:55450/aurameme_test", manifest)

    def bad_port(cmd, **kw):
        if cmd[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="true\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="127.0.0.1:5432\n", stderr="")

    monkeypatch.setattr(safety_guard.subprocess, "run", bad_port)
    with pytest.raises(RuntimeError, match="port mapping mismatch"):
        safety_guard.verify_isolated_postgres("postgresql+psycopg://u:p@127.0.0.1:55450/aurameme_test", manifest)


def test_verify_isolated_postgres_rejects_missing_fixture_marker(tmp_path, monkeypatch):
    manifest = tmp_path / "seed_manifest.json"
    manifest.write_text('{"post_1_id": "81883f01-ce34-50ed-a693-8be124c9509e"}', encoding="utf-8")
    monkeypatch.setattr(safety_guard.subprocess, "run", _mock_docker_ok)
    monkeypatch.setattr(safety_guard, "create_engine", lambda *a, **kw: _mock_engine_factory(has_user=None))

    with pytest.raises(RuntimeError, match="Synthetic fixture identity check failed"):
        safety_guard.verify_isolated_postgres("postgresql+psycopg://u:p@127.0.0.1:55450/aurameme_test", manifest)


def test_owned_uvicorn_server_rejects_port_collision(tmp_path, monkeypatch):
    monkeypatch.setattr(safety_guard, "_is_port_listening", lambda host, port: True)
    popen_mock = MagicMock()
    monkeypatch.setattr(safety_guard.subprocess, "Popen", popen_mock)

    env_vals = {"DATABASE_URL": "postgresql+psycopg://u:p@127.0.0.1:55450/aurameme_test", "EMAIL_MODE": "sandbox"}
    with pytest.raises(RuntimeError, match="already in use"):
        with safety_guard.owned_uvicorn_server(tmp_path, env_vals, port=18080):
            pass
    popen_mock.assert_not_called()


def test_owned_uvicorn_server_stops_on_early_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(safety_guard, "_is_port_listening", lambda host, port: False)
    proc = MagicMock()
    proc.poll.return_value = 1
    proc.returncode = 1
    monkeypatch.setattr(safety_guard.subprocess, "Popen", lambda *a, **kw: proc)

    env_vals = {"DATABASE_URL": "postgresql+psycopg://u:p@127.0.0.1:55450/aurameme_test", "EMAIL_MODE": "sandbox"}
    with pytest.raises(RuntimeError, match="exited early"):
        with safety_guard.owned_uvicorn_server(tmp_path, env_vals, port=18080):
            pass


def test_verify_runtime_env_rejects_unsafe_settings():
    with pytest.raises(RuntimeError, match="EMAIL_MODE"):
        safety_guard.verify_runtime_env({"DATABASE_URL": "x", "EMAIL_MODE": "smtp"})
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_ID"):
        safety_guard.verify_runtime_env({"DATABASE_URL": "x", "EMAIL_MODE": "sandbox", "GOOGLE_CLIENT_ID": "real-id"})
