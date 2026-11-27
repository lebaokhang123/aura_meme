"""H06 PostgreSQL integration tests for Asset Lifecycle, Vault Pool Versioning, and System Asset Protection."""
from io import BytesIO
import os
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import delete, func, select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "h04"))
from safety_guard import load_env_file, verify_isolated_postgres, verify_runtime_env  # noqa: E402

pytestmark = pytest.mark.integration

ORIGIN = {"Origin": "http://127.0.0.1:5173"}
ADMIN_EMAIL = "khang_dev@example.com"
ADMIN_PASSWORD = "H01SimAdmin!2026"
USER_1_EMAIL = "sim_user_001@example.com"
USER_2_EMAIL = "sim_user_002@example.com"
MANIFEST_PATH = ROOT / "backend" / "h01.local" / "seed_manifest.json"
ENV_PATH = ROOT / "backend" / ".env.h01"


def _ensure_test_db():
    if ENV_PATH.exists():
        env_vals = load_env_file(ENV_PATH)
        for k, v in env_vals.items():
            os.environ.setdefault(k, v)
    else:
        env_vals = dict(os.environ)
    db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("TEST_DATABASE_URL / DATABASE_URL not configured.")
    verify_runtime_env({**env_vals, "DATABASE_URL": db_url})
    verify_isolated_postgres(db_url, MANIFEST_PATH)
    os.environ["DATABASE_URL"] = db_url


def _make_png_bytes() -> bytes:
    import random
    buf = BytesIO()
    img = Image.new("RGB", (64, 64), (random.randint(1, 250), random.randint(1, 250), random.randint(1, 250)))
    img.putpixel((0, 0), (random.randint(1, 250), random.randint(1, 250), random.randint(1, 250)))
    img.save(buf, format="PNG")
    return buf.getvalue()


def _login_admin(client: TestClient) -> str:
    pre = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    r = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, headers={"X-CSRF-Token": pre})
    assert r.status_code == 200
    return client.get("/api/v1/auth/csrf").json()["csrf_token"]


def _upload_and_approve(client: TestClient, filename: str, display_name: str) -> str:
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    up = client.post(
        "/api/v1/admin/assets/upload",
        files={"file": (filename, _make_png_bytes(), "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert up.status_code == 201, up.text
    aid = up.json()["items"][0]["id"]
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    ed = client.patch(
        f"/api/v1/admin/assets/{aid}",
        json={"display_name": display_name},
        headers={"X-CSRF-Token": csrf},
    )
    assert ed.status_code == 200, ed.text
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    ap = client.patch(
        f"/api/v1/admin/assets/{aid}",
        json={"action": "approve"},
        headers={"X-CSRF-Token": csrf},
    )
    assert ap.status_code == 200, ap.text
    return aid


def test_h06_asset_lifecycle_archive_restore_vault_and_protection(monkeypatch):
    _ensure_test_db()
    monkeypatch.setenv("AURAMEME_OWNER_MEME_DEMO", "1")
    from starlette.requests import Request
    from app.catalog_rights import reviewed_source_rights_sql
    from app.main import app
    from app.meme_reactions import meme_reaction_states
    from app.models import (
        AssetItem, AuraLedger, CaseDefinition, CaseLootRarity, CaseLootTable, CaseOpen,
        CasePoolItem, Category, InventoryGrant, Post, PostReaction,
        RewardPolicyVersion, User, UserEquipment, UserInventory,
    )
    from app.vault import RARITIES
    from app.vault_runtime import load_runtime_pool
    from app.vault_v1_policy import WEIGHTS

    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN) as client:
        csrf = _login_admin(client)
        # 1. Upload & approve a fresh admin-upload meme (unique color so no hash collision)
        png = _make_png_bytes()
        up = client.post(
            "/api/v1/admin/assets/upload",
            files={"file": ("D_281126_91.png", png, "image/png")},
            headers={"X-CSRF-Token": csrf},
        )
        assert up.status_code == 201, up.text
        asset_id = up.json()["items"][0]["id"]
        assert up.json()["items"][0]["review_status"] == "pending"
        assert up.json()["items"][0]["system_protected"] is False

        # Edit name & rarity while pending and unowned -> succeeds
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        ed = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"display_name": "H06 Lifecycle Meme", "rarity": "C"},
            headers={"X-CSRF-Token": csrf},
        )
        assert ed.status_code == 200
        assert ed.json()["display_name"] == "H06 Lifecycle Meme"
        assert ed.json()["rarity"] == "C"

        # Approve -> active=True, review_status='approved'
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        ap = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"action": "approve"},
            headers={"X-CSRF-Token": csrf},
        )
        assert ap.status_code == 200
        assert ap.json()["active"] is True
        assert ap.json()["review_status"] == "approved"

        # 2. Seed multi-user ownership, equipment, post reaction, and a Vault CaseOpen in DB
        now = app.state.auth.now()
        backup_by_rarity = {
            rar: _upload_and_approve(client, f"{rar}_281126_{idx + 10}.png", f"H06 Backup {rar}")
            for idx, rar in enumerate(RARITIES)
        }

        with app.state.auth_session_factory() as db, db.begin():
            for b_id in backup_by_rarity.values():
                b_asset = db.get(AssetItem, b_id)
                sha = (b_asset.source_rights or {}).get("sha256") or ("a" * 64)
                b_asset.source_rights = {
                    "review_status": "approved",
                    "name_review_status": "approved",
                    "source": "aurameme://original/h06-backup",
                    "author": "AuraMeme H06 Test",
                    "license": "LicenseRef-AuraMeme-Original",
                    "attribution": "AuraMeme H06 Test",
                    "sha256": sha,
                    "proof": {
                        "basis": "original",
                        "source": "aurameme://original/h06-backup",
                        "license_id": "LicenseRef-AuraMeme-Original",
                        "license_url": "aurameme://original/license",
                        "artifact_sha256": sha,
                        "evidence_sha256": sha,
                        "copyright_notice": "AuraMeme H06 Test",
                    },
                }
            u1 = db.scalar(select(User).where(User.email == USER_1_EMAIL))
            u2 = db.scalar(select(User).where(User.email == USER_2_EMAIL))
            khang = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
            pol = db.scalar(
                select(RewardPolicyVersion).where(
                    RewardPolicyVersion.status == "published",
                    RewardPolicyVersion.config_json.op("->>")("type") == "free-vault-v1",
                ).limit(1)
            )
            cat = db.scalar(select(Category).limit(1))
            assert u1 and u2 and khang and pol and cat

            # Grant to u1 and u2, equip on u1 and u2
            for u in (u1, u2):
                if db.scalar(select(UserInventory).where(UserInventory.user_id == u.id, UserInventory.asset_id == asset_id)) is None:
                    db.add(UserInventory(user_id=u.id, asset_id=asset_id, quantity=1, acquired_at=now, updated_at=now))
                db.execute(delete(UserEquipment).where(UserEquipment.user_id == u.id, UserEquipment.slot_kind == "avatar"))
            db.flush()
            for u in (u1, u2):
                db.add(UserEquipment(user_id=u.id, slot_kind="avatar", asset_id=asset_id, equipped_at=now))

            # Post reaction using this meme
            p = Post(id=uuid4(), author_id=u1.id, category_id=cat.id, title="H06 Reaction Post", content="h06", status="published", created_at=now, updated_at=now)
            db.add(p)
            db.flush()
            db.add(PostReaction(post_id=p.id, user_id=u1.id, reaction_type="meme", meme_asset_id=asset_id, created_at=now, updated_at=now))

            # Reuse or create an active CaseDefinition (uq_case_definitions_runtime_kind allows one per runtime_kind)
            case = db.scalar(select(CaseDefinition).where(CaseDefinition.runtime_kind == "avatar"))
            if case is None:
                case = CaseDefinition(id=uuid4(), slug=f"h06-case-{uuid4().hex[:6]}", label="H06 Case", cost_khi_van=0, status="active", runtime_kind="avatar", created_at=now, updated_at=now)
                db.add(case)
                db.flush()
            max_ver = db.scalar(select(func.max(CaseLootTable.odds_version)).where(CaseLootTable.case_id == case.id)) or 0
            lt = CaseLootTable(id=uuid4(), case_id=case.id, policy_id=pol.id, odds_version=max_ver + 1, band_no=1, min_earned_xp=0, max_earned_xp=None, status="draft", active_from=now, created_at=now)
            db.add(lt)
            db.flush()
            for rar, w in zip(RARITIES, WEIGHTS):
                db.add(CaseLootRarity(loot_table_id=lt.id, rarity=rar, weight_bps=w))
                db.add(CasePoolItem(loot_table_id=lt.id, asset_id=backup_by_rarity[rar], rarity=rar, item_weight=1))
            db.add(CasePoolItem(loot_table_id=lt.id, asset_id=asset_id, rarity="C", item_weight=1))
            db.flush()
            lt.status = "published"
            db.flush()

            # Record a real CaseOpen referencing (lt.id, asset_id)
            earned = db.scalar(
                select(func.coalesce(func.sum(AuraLedger.base_xp), 0)).where(
                    AuraLedger.user_id == u1.id, AuraLedger.occurred_at <= now
                )
            )
            co = CaseOpen(
                id=uuid4(), user_id=u1.id, request_key=f"h06-open-{uuid4().hex}",
                case_id=case.id, loot_table_id=lt.id, reward_asset_id=asset_id,
                earned_xp_at_open=int(earned or 0), cost_khi_van=0, wallet_transaction_id=None,
                is_daily_free=False, effective_day=now.date(),
                decision_trace={"runtime": "free-vault-v1"}, created_at=now,
            )
            db.add(co)
            db.flush()
            lt_id = lt.id
            case_id = case.id
            post_id = p.id
            khang_id = khang.id

        # Rarity change after owned & in published pool -> 409 RARITY_IMMUTABLE (never 500)
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        rc = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"rarity": "B"},
            headers={"X-CSRF-Token": csrf},
        )
        assert rc.status_code == 409
        assert rc.json()["error"]["code"] == "RARITY_IMMUTABLE"

        # 3. Archive the used meme -> MUST SUCCEED (200), auto-unequip, version loot table, keep history!
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        ar = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"action": "archive"},
            headers={"X-CSRF-Token": csrf},
        )
        assert ar.status_code == 200, ar.text
        assert ar.json()["active"] is False
        assert ar.json()["review_status"] == "approved"

        with app.state.auth_session_factory() as db:
            # Equipment removed
            eq_cnt = db.scalar(select(func.count()).select_from(UserEquipment).where(UserEquipment.asset_id == asset_id))
            assert eq_cnt == 0
            # Multi-user inventory preserved
            inv_cnt = db.scalar(select(func.count()).select_from(UserInventory).where(UserInventory.asset_id == asset_id, UserInventory.quantity == 1))
            assert inv_cnt >= 2
            # Old loot table retired, new version 2 published without archived asset
            old_lt = db.get(CaseLootTable, lt_id)
            assert old_lt.status == "retired"
            new_lt = db.scalar(select(CaseLootTable).where(CaseLootTable.case_id == case_id, CaseLootTable.odds_version == max_ver + 2))
            assert new_lt is not None and new_lt.status == "published"
            # Vault pool still loads cleanly with original D/C/B/A/S weights!
            pool = load_runtime_pool(db, db.get(CaseDefinition, case_id), app.state.auth.now())
            assert pool.id == new_lt.id and pool.version == max_ver + 2
            # Meme reaction on post is excluded while inactive
            fake_req = Request({"type": "http", "app": app, "headers": []})
            mr = meme_reaction_states(db, PostReaction, [post_id], None, fake_req)
            assert mr[post_id]["meme_reactions"] == []

        # 4. Restore archived meme -> active=True, no duplicate InventoryGrant for khang_dev!
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        rs = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"action": "approve"},
            headers={"X-CSRF-Token": csrf},
        )
        assert rs.status_code == 200
        assert rs.json()["active"] is True
        with app.state.auth_session_factory() as db:
            grant_cnt = db.scalar(
                select(func.count()).select_from(InventoryGrant).where(
                    InventoryGrant.user_id == khang_id, InventoryGrant.asset_id == asset_id
                )
            )
            assert grant_cnt <= 1

        # 5. System original assets (70 memes + 5 backgrounds) remain protected on backend
        with app.state.auth_session_factory() as db:
            orig_meme = db.scalar(select(AssetItem).where(AssetItem.collection != "admin-upload", AssetItem.kind == "avatar").limit(1))
            orig_bg = db.scalar(select(AssetItem).where(AssetItem.kind == "background").limit(1))
            assert orig_meme and orig_bg
        for sys_id in (orig_meme.id, orig_bg.id):
            csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
            prot = client.patch(
                f"/api/v1/admin/assets/{sys_id}",
                json={"action": "archive"},
                headers={"X-CSRF-Token": csrf},
            )
            assert prot.status_code == 409
            assert prot.json()["error"]["code"] == "SYSTEM_ASSET_PROTECTED"


def test_h06_empty_rarity_bucket_rollback(monkeypatch):
    _ensure_test_db()
    monkeypatch.setenv("AURAMEME_OWNER_MEME_DEMO", "1")
    from app.catalog_rights import reviewed_source_rights_sql
    from app.main import app
    from app.models import (
        AssetItem, CaseDefinition, CaseLootRarity, CaseLootTable,
        CasePoolItem, RewardPolicyVersion,
    )
    from app.vault import RARITIES
    from app.vault_v1_policy import WEIGHTS

    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN) as client:
        csrf = _login_admin(client)
        up = client.post(
            "/api/v1/admin/assets/upload",
            files={"file": ("C_281126_92.png", _make_png_bytes(), "image/png")},
            headers={"X-CSRF-Token": csrf},
        )
        assert up.status_code == 201, up.text
        asset_id = up.json()["items"][0]["id"]
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        ap = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"action": "approve"},
            headers={"X-CSRF-Token": csrf},
        )
        assert ap.status_code == 200, ap.text

        backup_by_rarity = {
            rar: _upload_and_approve(client, f"{rar}_281126_{idx + 20}.png", f"H06 Empty Backup {rar}")
            for idx, rar in enumerate(RARITIES)
            if rar != "C"
        }

        with app.state.auth_session_factory() as db, db.begin():
            now = app.state.auth.now()
            pol = db.scalar(
                select(RewardPolicyVersion).where(
                    RewardPolicyVersion.status == "published",
                    RewardPolicyVersion.config_json.op("->>")("type") == "free-vault-v1",
                ).limit(1)
            )
            case = db.scalar(select(CaseDefinition).where(CaseDefinition.runtime_kind == "avatar"))
            if case is None:
                case = CaseDefinition(
                    id=uuid4(), slug=f"h06-empty-{uuid4().hex[:6]}", label="H06 Empty Bucket Case",
                    cost_khi_van=0, status="active", runtime_kind="avatar", created_at=now, updated_at=now,
                )
                db.add(case)
                db.flush()
            max_ver = db.scalar(select(func.max(CaseLootTable.odds_version)).where(CaseLootTable.case_id == case.id)) or 0
            lt = CaseLootTable(
                id=uuid4(), case_id=case.id, policy_id=pol.id, odds_version=max_ver + 1,
                band_no=1, min_earned_xp=0, max_earned_xp=None, status="draft",
                active_from=now, created_at=now,
            )
            db.add(lt)
            db.flush()
            for rar, w in zip(RARITIES, WEIGHTS):
                db.add(CaseLootRarity(loot_table_id=lt.id, rarity=rar, weight_bps=w))
                if rar == "C":
                    db.add(CasePoolItem(loot_table_id=lt.id, asset_id=asset_id, rarity="C", item_weight=1))
                else:
                    db.add(CasePoolItem(loot_table_id=lt.id, asset_id=backup_by_rarity[rar], rarity=rar, item_weight=1))
            db.flush()
            lt.status = "published"
            db.flush()
            lt_id = lt.id

        # Archiving the sole item in bucket C must fail 409 EMPTY_RARITY_BUCKET and roll back cleanly
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        ar = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"action": "archive"},
            headers={"X-CSRF-Token": csrf},
        )
        assert ar.status_code == 409, ar.text
        assert ar.json()["error"]["code"] == "EMPTY_RARITY_BUCKET"

        with app.state.auth_session_factory() as db:
            lt_after = db.get(CaseLootTable, lt_id)
            assert lt_after.status == "published"
            asset_after = db.get(AssetItem, asset_id)
            assert asset_after.active is True
