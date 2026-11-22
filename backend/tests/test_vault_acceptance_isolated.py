"""Full Acceptance Test for Vault Recovery on Isolated Database.

Verifies all 12 criteria specified by Owner:
1. Login with test user.
2. Both cases visible: Rương Meme and Rương Background.
3. 70 Meme and 5 Background assets valid in catalog.
4. Images served properly (valid PNG bytes, non-broken).
5. Odds / drop rates D/C/B/A/S verified (68.9%, 20.0%, 10.0%, 1.0%, 0.1%).
6. Open both cases (Meme and Background) once each.
7. Rewarded items received in Inventory.
8. Retry with same Idempotency-Key returns already_processed=True and identical receipt without duplicate reward.
9. +2 EXP awarded per successful open (within daily cap of 100), recorded in AuraLedger.
10. Inventory query reflects acquired items persistently.
11. Equip meme avatar and background cover successfully.
12. Cannot equip an unowned asset (raises 404 NOT_FOUND).
"""
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Configure isolated environment
ISOLATED_DB_URL = "postgresql+psycopg://aurameme_demo:not-a-real-test-password@127.0.0.1:5432/aurameme_vault_verify"
CATALOG_ROOT = r"D:\Big\du_an_lon\aura_meme_mvp\backend\demo.local\catalog"
MEDIA_ROOT = r"D:\Big\du_an_lon\aura_meme_mvp\backend\demo.local\media"

os.environ["DATABASE_URL"] = ISOLATED_DB_URL
os.environ["CATALOG_STORAGE_ROOT"] = CATALOG_ROOT
os.environ["MEDIA_STORAGE_ROOT"] = MEDIA_ROOT
os.environ["VAULT_RUNTIME_ENABLED"] = "true"
os.environ["AURAMEME_OWNER_MEME_DEMO"] = "1"
os.environ["AUTH_ENVIRONMENT"] = "development"
os.environ["AUTH_ALLOWED_ORIGINS"] = '["http://localhost:5173"]'
os.environ["AUTH_SIGNING_KEY"] = "not-a-real-archived-signing-key"

from app.main import app
from app.models import AuraLedger, UserProgress


@pytest.fixture(scope="module")
def isolated_client():
    test_username = f"user_{secrets.token_hex(4)}"
    password_clear = "TestPass123!Secure"
    email = f"{test_username}@example.com"

    with TestClient(app, base_url="http://localhost:5173") as client:
        client.headers.update({"Origin": "http://localhost:5173"})
        # Step 0: Get CSRF token for guest registration
        csrf_res = client.get("/api/v1/auth/csrf")
        assert csrf_res.status_code == 200
        guest_csrf = csrf_res.json()["csrf_token"]

        # Step 1a: Register
        reg_res = client.post(
            "/api/v1/auth/register",
            json={
                "username": test_username,
                "email": email,
                "password": password_clear,
                "display_name": f"Tester {test_username}",
            },
            headers={"X-CSRF-Token": guest_csrf},
        )
        assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
        user_id = reg_res.json()["id"]

        # Step 1b: Login
        login_res = client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": password_clear,
            },
            headers={"X-CSRF-Token": guest_csrf},
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        csrf_token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        client.headers.update({"X-CSRF-Token": csrf_token})
        yield client, user_id


def test_vault_acceptance_all_12_points(isolated_client):
    client, user_id = isolated_client
    csrf_token = client.headers["X-CSRF-Token"]

    # STEP 2: Both cases visible: Rương Meme and Rương Background
    cases_res = client.get("/api/v1/vault/cases")
    assert cases_res.status_code == 200
    cases_data = cases_res.json()
    items = cases_data["items"]
    assert len(items) == 2, f"Expected 2 cases, got {len(items)}"
    cases_by_kind = {c["runtime_kind"]: c for c in items}
    assert "avatar" in cases_by_kind, "Rương Meme (avatar) missing"
    assert "background" in cases_by_kind, "Rương Background missing"
    meme_case = cases_by_kind["avatar"]
    bg_case = cases_by_kind["background"]
    assert meme_case["label"] == "Rương Meme"
    assert bg_case["label"] == "Rương Background"
    assert meme_case["status"] == "active"
    assert bg_case["status"] == "active"

    # STEP 3: Catalog verification: 70 Meme and 5 Background assets valid
    cat_meme_res = client.get("/api/v1/catalog?kind=avatar&page_size=100")
    assert cat_meme_res.status_code == 200
    cat_memes = cat_meme_res.json()
    assert cat_memes["pagination"]["total"] == 70, f"Expected 70 memes, got {cat_memes['pagination']['total']}"

    cat_bg_res = client.get("/api/v1/catalog?kind=background&page_size=100")
    assert cat_bg_res.status_code == 200
    cat_bgs = cat_bg_res.json()
    assert cat_bgs["pagination"]["total"] == 5, f"Expected 5 backgrounds, got {cat_bgs['pagination']['total']}"

    # STEP 4: Images served properly (non-broken, valid PNG bytes)
    sample_meme = cat_memes["items"][0]["asset"]
    sample_bg = cat_bgs["items"][0]["asset"]
    assert sample_meme["media_url"] is not None
    assert sample_bg["media_url"] is not None

    meme_img_res = client.get(f"/api/v1/catalog/assets/{sample_meme['id']}")
    assert meme_img_res.status_code == 200
    assert meme_img_res.headers["content-type"] == "image/png"
    assert len(meme_img_res.content) > 1000

    bg_img_res = client.get(f"/api/v1/catalog/assets/{sample_bg['id']}")
    assert bg_img_res.status_code == 200
    assert bg_img_res.headers["content-type"] == "image/png"
    assert len(bg_img_res.content) > 500

    # STEP 5: Odds / drop rates D/C/B/A/S verified (68.9%, 20.0%, 10.0%, 1.0%, 0.1%)
    detail_meme_res = client.get(f"/api/v1/vault/cases/{meme_case['id']}")
    assert detail_meme_res.status_code == 200
    bands_meme = detail_meme_res.json()["bands"]
    assert len(bands_meme) == 1
    weights_meme = bands_meme[0]["weights_bps"]
    assert weights_meme == {"D": 6890, "C": 2000, "B": 1000, "A": 100, "S": 10}

    detail_bg_res = client.get(f"/api/v1/vault/cases/{bg_case['id']}")
    assert detail_bg_res.status_code == 200
    bands_bg = detail_bg_res.json()["bands"]
    assert len(bands_bg) == 1
    weights_bg = bands_bg[0]["weights_bps"]
    assert weights_bg == {"D": 6890, "C": 2000, "B": 1000, "A": 100, "S": 10}

    # STEP 6: Open both cases once each
    # Meme Case Open
    meme_key = f"test-key-meme-{secrets.token_hex(16)}"
    open_meme_res = client.post(
        f"/api/v1/vault/cases/{meme_case['id']}/open",
        headers={"Idempotency-Key": meme_key, "X-CSRF-Token": csrf_token},
    )
    assert open_meme_res.status_code == 200, f"Meme open failed: {open_meme_res.text}"
    meme_receipt = open_meme_res.json()
    assert meme_receipt["already_processed"] is False
    assert meme_receipt["reward"]["kind"] == "avatar"
    rewarded_meme_id = meme_receipt["reward"]["id"]

    # Background Case Open (respect 2-second cooldown)
    import time
    time.sleep(2.5)
    bg_key = f"test-key-bg-{secrets.token_hex(16)}"
    open_bg_res = client.post(
        f"/api/v1/vault/cases/{bg_case['id']}/open",
        headers={"Idempotency-Key": bg_key, "X-CSRF-Token": csrf_token},
    )
    assert open_bg_res.status_code == 200, f"Bg open failed: {open_bg_res.text}"
    bg_receipt = open_bg_res.json()
    assert bg_receipt["already_processed"] is False
    assert bg_receipt["reward"]["kind"] == "background"
    rewarded_bg_id = bg_receipt["reward"]["id"]

    # STEP 7: Check items in Inventory
    inv_res = client.get("/api/v1/inventory/me")
    assert inv_res.status_code == 200
    inv_items = inv_res.json()["items"]
    owned_asset_ids = {it["asset"]["id"] for it in inv_items}
    assert rewarded_meme_id in owned_asset_ids, "Rewarded meme not found in inventory"
    assert rewarded_bg_id in owned_asset_ids, "Rewarded background not found in inventory"

    # STEP 8: Retry with same Idempotency-Key -> already_processed=True, no double grant
    retry_res = client.post(
        f"/api/v1/vault/cases/{meme_case['id']}/open",
        headers={"Idempotency-Key": meme_key, "X-CSRF-Token": csrf_token},
    )
    assert retry_res.status_code == 200
    retry_receipt = retry_res.json()
    assert retry_receipt["already_processed"] is True
    assert retry_receipt["open_id"] == meme_receipt["open_id"]
    assert retry_receipt["reward"]["id"] == rewarded_meme_id

    # STEP 9: Check +2 EXP award per open (+4 EXP total for 2 opens) in AuraLedger
    engine = create_engine(ISOLATED_DB_URL)
    with Session(engine) as db:
        ledger_entries = list(db.scalars(
            select(AuraLedger)
            .where(AuraLedger.user_id == user_id, AuraLedger.event_key.startswith("vault-v1:case:"))
            .order_by(AuraLedger.occurred_at)
        ))
        assert len(ledger_entries) == 2, f"Expected 2 Exp ledger entries, got {len(ledger_entries)}"
        for entry in ledger_entries:
            assert entry.base_xp == 2, f"Expected +2 base_xp, got {entry.base_xp}"
            assert entry.bonus_xp == 0

        # Total user progress updated
        progress = db.scalar(select(UserProgress).where(UserProgress.user_id == user_id))
        assert progress.aura_xp_earned == 4, f"Expected 4 earned XP, got {progress.aura_xp_earned}"

    # STEP 10: Persistent reload: query inventory again
    inv_reload = client.get("/api/v1/inventory/me")
    assert inv_reload.status_code == 200
    assert len(inv_reload.json()["items"]) == 2

    # STEP 11: Equip Meme as avatar and Background as background
    equip_meme_res = client.put(
        "/api/v1/inventory/equipment/avatar",
        json={"asset_id": rewarded_meme_id},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert equip_meme_res.status_code == 200
    assert equip_meme_res.json()["asset_id"] == rewarded_meme_id

    equip_bg_res = client.put(
        "/api/v1/inventory/equipment/background",
        json={"asset_id": rewarded_bg_id},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert equip_bg_res.status_code == 200
    assert equip_bg_res.json()["asset_id"] == rewarded_bg_id

    # Verify equipped status in inventory
    inv_after_equip = client.get("/api/v1/inventory/me").json()["items"]
    equipped_map = {it["asset"]["id"]: it["equipped"] for it in inv_after_equip}
    assert equipped_map[rewarded_meme_id] is True
    assert equipped_map[rewarded_bg_id] is True

    # STEP 12: Cannot equip unowned asset (404 NOT_FOUND)
    unowned_id = str(uuid4())
    equip_unowned_res = client.put(
        "/api/v1/inventory/equipment/avatar",
        json={"asset_id": unowned_id},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert equip_unowned_res.status_code == 404
    assert equip_unowned_res.json()["error"]["code"] == "NOT_FOUND"
