"""H05 E2E Presence & SQL Cost Verification Runner (uses isolated safety_guard)."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
from sqlalchemy import event
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "h04"))
from safety_guard import (  # noqa: E402
    DEFAULT_HARNESS_PORT,
    load_env_file,
    owned_uvicorn_server,
    verify_isolated_postgres,
    verify_runtime_env,
)

BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
ENV_FILE = BACKEND_DIR / ".env.h01"
MANIFEST_FILE = BACKEND_DIR / "h01.local" / "seed_manifest.json"
PREVIEW_PORT = 15173
ORIGIN_URL = f"http://127.0.0.1:{PREVIEW_PORT}"


def measure_heartbeat_sql_cost(env_vals: dict[str, str]) -> dict:
    for k, v in env_vals.items():
        os.environ[k] = v
    sys.path.insert(0, str(BACKEND_DIR))
    from fastapi.testclient import TestClient
    from app.main import app

    @contextmanager
    def count_sql():
        stmts: list[str] = []

        def before(conn, cursor, statement, parameters, context, executemany):
            stmts.append(statement.strip().splitlines()[0][:100])

        event.listen(Engine, "before_cursor_execute", before)
        try:
            yield stmts
        finally:
            event.remove(Engine, "before_cursor_execute", before)

    with TestClient(app, base_url=f"http://127.0.0.1:{DEFAULT_HARNESS_PORT}", headers={"Origin": "http://127.0.0.1:5173"}) as c:
        with count_sql() as g_sql:
            t0 = time.perf_counter()
            rg = c.post("/api/v1/presence/heartbeat")
            g_ms = round((time.perf_counter() - t0) * 1000, 2)
        assert rg.status_code == 200

        csrf = c.get("/api/v1/auth/csrf").json()["csrf_token"]
        login = c.post(
            "/api/v1/auth/login",
            json={"email": "sim_user_001@example.com", "password": "H01SimUser!2026"},
            headers={"X-CSRF-Token": csrf},
        )
        assert login.status_code == 200

        with count_sql() as a_sql:
            t0 = time.perf_counter()
            ra = c.post("/api/v1/presence/heartbeat")
            a_ms = round((time.perf_counter() - t0) * 1000, 2)
        assert ra.status_code == 200

    return {
        "guest_sql_count": len(g_sql),
        "guest_elapsed_ms": g_ms,
        "auth_sql_count": len(a_sql),
        "auth_elapsed_ms": a_ms,
        "auth_sql_statements": a_sql,
    }


def main():
    env_vals = load_env_file(ENV_FILE)
    verify_runtime_env(env_vals)
    db_identity = verify_isolated_postgres(env_vals["DATABASE_URL"], MANIFEST_FILE)

    print("[1/2] Measuring heartbeat SQL cost...")
    sql_cost = measure_heartbeat_sql_cost(env_vals)
    print("SQL Cost:", json.dumps(sql_cost, indent=2))

    # Allow preview origin in isolated backend subprocess
    origins = json.loads(env_vals.get("AUTH_ALLOWED_ORIGINS", '["http://127.0.0.1:5173"]'))
    if ORIGIN_URL not in origins:
        origins.append(ORIGIN_URL)
    sub_env = {**env_vals, "AUTH_ALLOWED_ORIGINS": json.dumps(origins)}

    print(f"[2/2] Starting owned uvicorn ({DEFAULT_HARNESS_PORT}) + vite preview ({PREVIEW_PORT}) for Playwright E2E...")
    with owned_uvicorn_server(BACKEND_DIR, sub_env, port=DEFAULT_HARNESS_PORT):
        preview_env = {**os.environ, "AURAMEME_API_TARGET": f"http://127.0.0.1:{DEFAULT_HARNESS_PORT}"}
        preview_proc = subprocess.Popen(
            ["npx.cmd", "vite", "preview", "--host", "127.0.0.1", "--port", str(PREVIEW_PORT), "--strictPort"],
            cwd=str(FRONTEND_DIR),
            env=preview_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(40):
                try:
                    if httpx.get(ORIGIN_URL, timeout=1.5).status_code == 200:
                        break
                except Exception:
                    pass
                time.sleep(0.25)
            else:
                raise RuntimeError("Vite preview did not start in time.")

            e2e = subprocess.run(
                ["node", str(ROOT / "scripts" / "h05" / "e2e_playwright_h05.mjs")],
                cwd=str(FRONTEND_DIR),
                env={**os.environ, "H05_BASE_URL": ORIGIN_URL, "H05_SCREENSHOT_PATH": str(BACKEND_DIR / "h01.local" / "h05_admin_overview.png")},
                capture_output=True,
                text=True,
                timeout=120,
            )
            print(e2e.stdout)
            if e2e.returncode != 0:
                print(e2e.stderr)
                raise RuntimeError(f"Playwright E2E failed with code {e2e.returncode}")
        finally:
            if preview_proc.poll() is None:
                preview_proc.terminate()
                try:
                    preview_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    preview_proc.kill()

    report = {
        "db_identity": db_identity,
        "heartbeat_sql_cost": sql_cost,
        "e2e_status": "PASS",
    }
    out_path = BACKEND_DIR / "h01.local" / "h05_e2e_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved H05 E2E report to {out_path}")


if __name__ == "__main__":
    main()
