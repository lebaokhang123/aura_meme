"""H04 End-to-End User Simulator & Data Integrity Verification.

Covers:
- Guest: Feed (newest, hot, search), post detail, comments, vault cases
- Member: Login + CSRF, reaction, comment, bookmark, daily check-in (/api/v1/aura/check-in)
- Vault Player: List cases, open case (/api/v1/vault/cases/{id}/open with Idempotency-Key), catalog, equipment
- Creator: Create post
- Admin: Admin users (with email), audit logs
- Data integrity checks on PostgreSQL
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

import httpx
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
ENV_FILE = BACKEND_DIR / ".env.h01"
MANIFEST_FILE = BACKEND_DIR / "h01.local" / "seed_manifest.json"
BASE_URL = "http://127.0.0.1:8000"
ORIGIN_HEADERS = {"Origin": "http://127.0.0.1:5173"}
USER_PASSWORD = "H01SimUser!2026"
ADMIN_PASSWORD = "H01SimAdmin!2026"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def login_client(email: str, password: str) -> tuple[httpx.Client, str]:
    client = httpx.Client(timeout=15.0, headers=ORIGIN_HEADERS)
    pre_csrf = client.get(f"{BASE_URL}/api/v1/auth/csrf").json()["csrf_token"]
    r = client.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": pre_csrf},
    )
    if r.status_code != 200:
        raise RuntimeError(f"Login failed for {email}: {r.status_code} {r.text}")
    csrf = client.get(f"{BASE_URL}/api/v1/auth/csrf").json()["csrf_token"]
    return client, csrf


def run_data_integrity_checks(db_url: str) -> dict:
    engine = create_engine(db_url, pool_pre_ping=True)
    checks = {}
    with engine.connect() as conn:
        checks["negative_xp_users"] = conn.execute(
            text("SELECT count(*) FROM user_progress WHERE aura_xp_earned < 0 OR aura_xp_bonus < 0")
        ).scalar_one()
        checks["negative_khi_van_wallets"] = conn.execute(
            text("SELECT count(*) FROM wallets WHERE khi_van_balance < 0")
        ).scalar_one()
        checks["orphaned_case_opens"] = conn.execute(
            text("SELECT count(*) FROM case_opens co LEFT JOIN inventory_grants ig ON ig.case_open_id = co.id WHERE ig.id IS NULL")
        ).scalar_one()
        checks["negative_inventory_qty"] = conn.execute(
            text("SELECT count(*) FROM user_inventory WHERE quantity < 0")
        ).scalar_one()
    engine.dispose()
    checks["all_zero"] = all(v == 0 for k, v in checks.items() if k != "all_zero")
    return checks


def main():
    env_vals = load_env_file(ENV_FILE)
    db_url = env_vals["DATABASE_URL"]
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))

    proc_env = os.environ.copy()
    proc_env.update(env_vals)
    proc = subprocess.Popen(
        [str(BACKEND_DIR / ".venv" / "Scripts" / "python.exe"), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1", "--log-level", "warning"],
        cwd=str(BACKEND_DIR),
        env=proc_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    results: dict[str, dict] = {}
    try:
        with httpx.Client(timeout=15.0, headers=ORIGIN_HEADERS) as guest:
            for _ in range(30):
                try:
                    if guest.get(f"{BASE_URL}/health").status_code == 200:
                        break
                except Exception:
                    pass
                time.sleep(0.3)

            # 1. Guest flow
            r_feed = guest.get(f"{BASE_URL}/api/v1/posts?page=1&page_size=20&include_interactions=true")
            r_hot = guest.get(f"{BASE_URL}/api/v1/posts?sort=reaction_desc&page=1&page_size=20&include_interactions=true")
            r_search = guest.get(f"{BASE_URL}/api/v1/posts?search=Tu%20Tien&page=1&page_size=20&include_interactions=true")
            r_detail = guest.get(f"{BASE_URL}/api/v1/posts/{manifest['post_1_id']}")
            r_comments = guest.get(f"{BASE_URL}/api/v1/posts/{manifest['post_1_id']}/comments?page=1&page_size=20")
            r_cases = guest.get(f"{BASE_URL}/api/v1/vault/cases")
            results["guest"] = {
                "feed_status": r_feed.status_code,
                "hot_status": r_hot.status_code,
                "search_status": r_search.status_code,
                "detail_status": r_detail.status_code,
                "comments_status": r_comments.status_code,
                "vault_cases_status": r_cases.status_code,
            }
            cases = r_cases.json().get("items", [])

        # 2. Member flow (reaction, comment, bookmark, check-in)
        member, m_csrf = login_client("sim_user_001@example.com", USER_PASSWORD)
        try:
            pid = manifest["post_1_id"]
            r_react = member.put(
                f"{BASE_URL}/api/v1/posts/{pid}/reactions",
                json={"reaction_type": "laugh"},
                headers={"X-CSRF-Token": m_csrf},
            )
            r_comment = member.post(
                f"{BASE_URL}/api/v1/posts/{pid}/comments",
                json={"body": f"H04 simulator comment {uuid.uuid4().hex[:8]}"},
                headers={"X-CSRF-Token": m_csrf},
            )
            r_bmark = member.put(
                f"{BASE_URL}/api/v1/posts/{pid}/bookmark",
                headers={"X-CSRF-Token": m_csrf},
            )
            r_checkin = member.post(
                f"{BASE_URL}/api/v1/aura/check-in",
                headers={"X-CSRF-Token": m_csrf},
            )
            results["member"] = {
                "reaction_status": r_react.status_code,
                "comment_status": r_comment.status_code,
                "bookmark_status": r_bmark.status_code,
                "checkin_status": r_checkin.status_code,
                "checkin_body": r_checkin.json() if r_checkin.status_code == 200 else r_checkin.text,
            }
        finally:
            member.close()

        # 3. Vault Player flow (open case + catalog + equipment)
        vplayer, v_csrf = login_client("sim_user_002@example.com", USER_PASSWORD)
        try:
            case_id = cases[0]["id"] if cases else None
            idem_key = f"h04-sim-{uuid.uuid4().hex}"
            r_open = vplayer.post(
                f"{BASE_URL}/api/v1/vault/cases/{case_id}/open",
                headers={"X-CSRF-Token": v_csrf, "Idempotency-Key": idem_key},
            ) if case_id else None
            r_cat = vplayer.get(f"{BASE_URL}/api/v1/catalog?page=1&page_size=20")
            r_eq = vplayer.get(f"{BASE_URL}/api/v1/inventory/equipment")
            results["vault_player"] = {
                "case_id": case_id,
                "open_status": r_open.status_code if r_open is not None else None,
                "open_body": r_open.json() if (r_open is not None and r_open.status_code in (200, 429)) else (r_open.text if r_open is not None else None),
                "catalog_status": r_cat.status_code,
                "equipment_status": r_eq.status_code,
            }
        finally:
            vplayer.close()

        # 4. Creator flow
        creator, c_csrf = login_client("sim_user_003@example.com", USER_PASSWORD)
        try:
            r_post = creator.post(
                f"{BASE_URL}/api/v1/posts",
                json={
                    "title": f"H04 Sim Post {uuid.uuid4().hex[:6]}",
                    "content": "Simulated post during H04 verification.",
                    "category_id": manifest["category_tu_tien_id"],
                },
                headers={"X-CSRF-Token": c_csrf},
            )
            results["creator"] = {
                "create_post_status": r_post.status_code,
            }
        finally:
            creator.close()

        # 5. Admin flow
        admin, _ = login_client("khang_dev@example.com", ADMIN_PASSWORD)
        try:
            r_users = admin.get(f"{BASE_URL}/api/v1/admin/users?page=1&page_size=20")
            r_audit = admin.get(f"{BASE_URL}/api/v1/admin/audit-logs?page=1&page_size=20")
            users_items = r_users.json().get("items", []) if r_users.status_code == 200 else []
            results["admin"] = {
                "users_status": r_users.status_code,
                "users_has_email": bool(users_items and "email" in users_items[0]),
                "audit_logs_status": r_audit.status_code,
            }
        finally:
            admin.close()

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    integrity = run_data_integrity_checks(db_url)
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "flows": results,
        "data_integrity": integrity,
    }
    out_path = BACKEND_DIR / "h01.local" / "h04_simulator_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
