"""H06 Playwright E2E runner for Admin Asset Lifecycle & Founder Permanent Delete (isolated safety_guard)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from sqlalchemy import select

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


def seed_e2e_fixtures(env_vals: dict[str, str]) -> tuple[str, str]:
    for k, v in env_vals.items():
        os.environ[k] = v
    sys.path.insert(0, str(BACKEND_DIR))
    from datetime import datetime, timezone
    from app.config import load_settings
    from app.db import create_db_engine
    from app.models import AssetItem, Profile, Role, User, UserRole
    from sqlalchemy.orm import Session

    engine = create_db_engine(load_settings())
    now = datetime.now(timezone.utc)
    sec_email = f"h06_pw_admin_{uuid4().hex[:6]}@example.com"
    asset_name = f"H06 PW Asset {uuid4().hex[:6]}"
    with Session(engine) as db, db.begin():
        admin_pw_hash = db.scalar(select(User.password_hash).where(User.email == "khang_dev@example.com"))
        admin_role = db.scalar(select(Role).where(Role.code == "ADMIN"))
        sec_user = User(
            id=uuid4(), username=f"h06pw_{uuid4().hex[:6]}", email=sec_email,
            password_hash=admin_pw_hash, status="active", created_at=now, updated_at=now,
        )
        db.add(sec_user)
        db.flush()
        db.add(Profile(user_id=sec_user.id, display_name="H06 PW Admin", bio="", updated_at=now))
        db.add(UserRole(user_id=sec_user.id, role_id=admin_role.id, granted_at=now))

        sha = uuid4().hex * 2
        asset = AssetItem(
            id=uuid4(), slug=f"h06-pw-{uuid4().hex[:8]}", kind="avatar", collection="admin-upload",
            rarity="C", media_key=f"catalog/{sha}.png", display_name=asset_name, effect_key=None,
            source_rights={
                "review_status": "approved", "name_review_status": "approved",
                "source": "aurameme://original/h06-pw", "author": "AuraMeme H06 PW",
                "license": "LicenseRef-AuraMeme-Original", "attribution": "AuraMeme H06 PW",
                "sha256": sha,
                "proof": {
                    "basis": "original", "source": "aurameme://original/h06-pw",
                    "license_id": "LicenseRef-AuraMeme-Original", "license_url": "aurameme://original/license",
                    "artifact_sha256": sha, "evidence_sha256": sha, "copyright_notice": "AuraMeme H06 PW",
                },
            },
            active=True, created_at=now, updated_at=now,
        )
        db.add(asset)
    return sec_email, asset_name


def main():
    env_vals = load_env_file(ENV_FILE)
    verify_runtime_env(env_vals)
    db_identity = verify_isolated_postgres(env_vals["DATABASE_URL"], MANIFEST_FILE)

    sec_email, asset_name = seed_e2e_fixtures(env_vals)
    origins = json.loads(env_vals.get("AUTH_ALLOWED_ORIGINS", '["http://127.0.0.1:5173"]'))
    if ORIGIN_URL not in origins:
        origins.append(ORIGIN_URL)
    sub_env = {**env_vals, "AUTH_ALLOWED_ORIGINS": json.dumps(origins)}

    print(f"[1/2] Starting owned uvicorn ({DEFAULT_HARNESS_PORT}) + vite preview ({PREVIEW_PORT}) for H06 Playwright E2E...")
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
                ["node", str(ROOT / "scripts" / "h06" / "e2e_playwright_h06.mjs")],
                cwd=str(FRONTEND_DIR),
                env={
                    **os.environ,
                    "H06_BASE_URL": ORIGIN_URL,
                    "H06_SEC_ADMIN_EMAIL": sec_email,
                    "H06_ASSET_NAME": asset_name,
                },
                capture_output=True,
                text=True,
                timeout=120,
            )
            print(e2e.stdout)
            if e2e.returncode != 0:
                print(e2e.stderr)
                raise RuntimeError(f"Playwright H06 E2E failed with code {e2e.returncode}")
        finally:
            if preview_proc.poll() is None:
                preview_proc.terminate()
                try:
                    preview_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    preview_proc.kill()

    report = {"db_identity": db_identity, "e2e_status": "PASS", "asset_name": asset_name}
    out_path = BACKEND_DIR / "h01.local" / "h06_e2e_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved H06 E2E report to {out_path}")


if __name__ == "__main__":
    main()
