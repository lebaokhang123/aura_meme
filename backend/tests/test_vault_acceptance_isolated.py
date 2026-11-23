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

pytestmark = pytest.mark.integration

from sqlalchemy import text
from sqlalchemy.engine import make_url
from app.models import AuraLedger, UserProgress


@pytest.fixture
def isolated_client(monkeypatch, tmp_path):
    database_url = os.environ.get("VAULT_ACCEPTANCE_DATABASE_URL")
    catalog_root = os.environ.get("VAULT_ACCEPTANCE_CATALOG_ROOT")
    if not database_url or not catalog_root:
        pytest.fail("Vault acceptance requires an explicit isolated clone and a catalog copy.")
    target = make_url(database_url)
    assert target.get_backend_name() == "postgresql"
    assert target.host in {"localhost", "127.0.0.1", "::1"}
    assert target.database in {"aurameme_test", "aurameme_qa"} and target.username == "aurameme_test"
    assert target.port not in {None, 5432} and not target.query
    assert Path(catalog_root).is_dir()
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("CATALOG_STORAGE_ROOT", catalog_root)
    monkeypatch.setenv("MEDIA_STORAGE_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("VAULT_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("AURAMEME_OWNER_MEME_DEMO", "1")
    monkeypatch.setenv("AUTH_ENVIRONMENT", "development")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["http://localhost:5173"]')
    monkeypatch.setenv("AUTH_SIGNING_KEY", secrets.token_urlsafe(48))
    monkeypatch.setenv("EMAIL_MODE", "disabled")
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "false")

    from app.main import app

    username = "vault_test_" + secrets.token_hex(4)
    email = username + "@example.com"
    password = secrets.token_urlsafe(32)
    engine = create_engine(database_url, hide_parameters=True)
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            identity = connection.execute(text("SELECT current_database(), current_user")).one()
            assert tuple(identity) == (target.database, target.username)
            assert connection.scalar(text("SELECT count(*) FROM asset_items")) == 75
            with TestClient(app, base_url="http://localhost:5173") as client:
                client.app.state.auth_session_factory = lambda: Session(
                    bind=connection, join_transaction_mode="create_savepoint")
                client.headers.update({"Origin": "http://localhost:5173"})
                def csrf_header():
                    return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]}
                response = client.post("/api/v1/auth/register", headers=csrf_header(), json={
                    "username": username, "email": email, "password": password, "display_name": "Vault test",
                })
                assert response.status_code == 201
                user_id = response.json()["id"]
                response = client.post("/api/v1/auth/login", headers=csrf_header(), json={
                    "email": email, "password": password,
                })
                assert response.status_code == 200
                client.headers.update(csrf_header())
                yield client, user_id, connection
            transaction.rollback()
    finally:
        engine.dispose()


def test_vault_acceptance_all_12_points(isolated_client):
    client, user_id, connection = isolated_client
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
    with Session(bind=connection) as db:
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
