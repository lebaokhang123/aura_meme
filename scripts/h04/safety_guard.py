"""Shared fail-closed test environment & process ownership guard for H04 harnesses."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.parse import urlparse

import httpx
import psutil
from sqlalchemy import create_engine, text

EXPECTED_CONTAINER = "aurameme-h01-sim-pg"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 55450
EXPECTED_DB = "aurameme_test"
EXPECTED_REVISION = "0021_comment_replies"
DEFAULT_HARNESS_PORT = 18080


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def verify_runtime_env(env_vals: dict[str, str]) -> None:
    """Fail-closed check ensuring synthetic DB, SMTP sandbox, and no live external keys."""
    if env_vals.get("EMAIL_MODE", "").lower() != "sandbox":
        raise RuntimeError(f"Unsafe EMAIL_MODE={env_vals.get('EMAIL_MODE')!r}; expected 'sandbox'.")
    if env_vals.get("GOOGLE_CLIENT_ID"):
        raise RuntimeError("Unsafe GOOGLE_CLIENT_ID configured in isolated test env.")
    if "DATABASE_URL" not in env_vals:
        raise RuntimeError("Missing DATABASE_URL in isolated test env.")


def verify_isolated_postgres(
    database_url: str,
    manifest_path: Path,
    *,
    container_name: str = EXPECTED_CONTAINER,
    expected_host: str = EXPECTED_HOST,
    expected_port: int = EXPECTED_PORT,
    expected_db: str = EXPECTED_DB,
    expected_revision: str = EXPECTED_REVISION,
) -> dict:
    """Fail-closed guard verifying Docker container, port mapping, DB identity, revision, and synthetic fixture marker."""
    parsed = urlparse(database_url)
    db_name = parsed.path.lstrip("/")
    host = parsed.hostname
    port = parsed.port
    if db_name != expected_db or host != expected_host or port != expected_port:
        raise RuntimeError(
            f"DB Identity Guard failed: got {host}:{port}/{db_name}, "
            f"expected {expected_host}:{expected_port}/{expected_db}"
        )

    # Verify Docker container is running and maps 5432/tcp -> 127.0.0.1:55450
    inspect_proc = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if inspect_proc.returncode != 0 or inspect_proc.stdout.strip().lower() != "true":
        raise RuntimeError(f"Docker container {container_name!r} is not running.")

    port_proc = subprocess.run(
        ["docker", "port", container_name, "5432/tcp"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    expected_mapping = f"{expected_host}:{expected_port}"
    if port_proc.returncode != 0 or expected_mapping not in port_proc.stdout:
        raise RuntimeError(
            f"Docker port mapping mismatch for {container_name}: "
            f"got {port_proc.stdout.strip()!r}, expected {expected_mapping!r}."
        )

    if not manifest_path.exists():
        raise RuntimeError(f"Synthetic manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    marker_post_id = manifest.get("post_1_id")
    if not marker_post_id:
        raise RuntimeError("Synthetic manifest missing post_1_id marker.")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT current_database(), (SELECT version_num FROM alembic_version LIMIT 1)")
            ).one()
            actual_db, revision = row[0], row[1]
            if actual_db != expected_db or revision != expected_revision:
                raise RuntimeError(
                    f"DB Identity Guard failed: db={actual_db}, revision={revision}, "
                    f"expected {expected_db} @ {expected_revision}"
                )
            has_sim_user = conn.execute(
                text("SELECT 1 FROM users WHERE email = 'sim_user_001@example.com' LIMIT 1")
            ).scalar()
            has_marker_post = conn.execute(
                text("SELECT 1 FROM posts WHERE id = :pid LIMIT 1"),
                {"pid": marker_post_id},
            ).scalar()
            if not has_sim_user or not has_marker_post:
                raise RuntimeError(
                    "Synthetic fixture identity check failed: missing sim_user_001 or manifest post_1_id."
                )
    finally:
        engine.dispose()

    return {
        "container": container_name,
        "database": actual_db,
        "host": host,
        "port": port,
        "alembic_revision": revision,
        "fixture_verified": True,
    }


def _is_port_listening(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        if sock.connect_ex((host, port)) == 0:
            return True
    for conn in psutil.net_connections(kind="inet"):
        if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
            return True
    return False


def _process_owns_listener(pid: int, port: int) -> bool:
    try:
        root_proc = psutil.Process(pid)
        procs = [root_proc, *root_proc.children(recursive=True)]
    except psutil.NoSuchProcess:
        return False
    for p in procs:
        try:
            for conn in p.net_connections(kind="inet"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


@contextmanager
def owned_uvicorn_server(
    backend_dir: Path,
    env_vals: dict[str, str],
    *,
    host: str = EXPECTED_HOST,
    port: int = DEFAULT_HARNESS_PORT,
):
    """Start an isolated uvicorn process on a dedicated test port with strict ownership checks."""
    verify_runtime_env(env_vals)
    if _is_port_listening(host, port):
        raise RuntimeError(
            f"Port {host}:{port} is already in use by another process. "
            "Refusing to start, kill external processes, or send mutations."
        )

    proc_env = os.environ.copy()
    proc_env.update(env_vals)
    proc = subprocess.Popen(
        [
            str(backend_dir / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            host,
            "--port",
            str(port),
            "--workers",
            "1",
            "--log-level",
            "warning",
        ],
        cwd=str(backend_dir),
        env=proc_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://{host}:{port}"
    try:
        ready = False
        with httpx.Client(timeout=2.0) as hc:
            for _ in range(40):
                if proc.poll() is not None:
                    raise RuntimeError(
                        f"Owned uvicorn subprocess exited early with code {proc.returncode}."
                    )
                if _process_owns_listener(proc.pid, port):
                    try:
                        r = hc.get(f"{base_url}/health")
                        if r.status_code == 200:
                            ready = True
                            break
                    except Exception:
                        pass
                time.sleep(0.25)
        if not ready:
            raise RuntimeError(
                f"Owned uvicorn subprocess (pid={proc.pid}) failed ownership or /health check on {base_url}."
            )
        yield proc, base_url
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
