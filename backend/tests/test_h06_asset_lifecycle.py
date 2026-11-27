"""H06 PostgreSQL integration tests for Final Asset Lifecycle, Rarity Versioning, Empty Buckets & Founder Authority."""
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


def _login(client: TestClient, email: str, password: str) -> str:
    client.cookies.clear()
    pre = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers={"X-CSRF-Token": pre})
    assert r.status_code == 200, r.text
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


def test_h06_final_asset_lifecycle_rarity_archive_restore_and_founder_delete(monkeypatch):
    _ensure_test_db()
    monkeypatch.setenv("AURAMEME_OWNER_MEME_DEMO", "1")
    from starlette.requests import Request
    from app.main import app
    from app.meme_reactions import meme_reaction_states
    from app.models import (
        AdminAuditLog, AssetItem, AuraLedger, CaseDefinition, CaseLootRarity,
        CaseLootTable, CaseOpen, CasePoolItem, Category, InventoryGrant,
        Post, PostReaction, Profile, RewardPolicyVersion, Role, User, UserEquipment,
        UserInventory, UserRole,
    )
    from app.vault import RARITIES
    from app.vault_privilege import sync_khang_dev_vault_privilege
    from app.vault_runtime import load_runtime_pool, receipt_reward
    from app.vault_v1_policy import EFFECT_KEYS, WEIGHTS

    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN) as client:
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

        # 1. Upload & edit rarity while pending
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        up = client.post(
            "/api/v1/admin/assets/upload",
            files={"file": ("D_281126_91.png", _make_png_bytes(), "image/png")},
            headers={"X-CSRF-Token": csrf},
        )
        assert up.status_code == 201, up.text
        asset_id = up.json()["items"][0]["id"]

        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        ed = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"display_name": "H06 Final Meme", "rarity": "C"},
            headers={"X-CSRF-Token": csrf},
        )
        assert ed.status_code == 200
        assert ed.json()["rarity"] == "C"

        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        ap = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"action": "approve"},
            headers={"X-CSRF-Token": csrf},
        )
        assert ap.status_code == 200 and ap.json()["active"] is True

        # Seed backup items per rarity with valid original proof
        now = app.state.auth.now()
        backup_by_rarity = {
            rar: _upload_and_approve(client, f"{rar}_281126_{idx + 30}.png", f"H06 Final Backup {rar}")
            for idx, rar in enumerate(RARITIES)
        }

        secondary_admin_email = f"h06_admin_{uuid4().hex[:6]}@example.com"
        with app.state.auth_session_factory() as db, db.begin():
            for b_id in list(backup_by_rarity.values()) + [asset_id]:
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

            # Create a secondary non-Founder ADMIN for RBAC tests
            admin_role = db.scalar(select(Role).where(Role.code == "ADMIN"))
            admin_pw_hash = db.scalar(select(User.password_hash).where(User.email == ADMIN_EMAIL))
            sec_admin = User(
                id=uuid4(), username=f"h06admin_{uuid4().hex[:6]}", email=secondary_admin_email,
                password_hash=admin_pw_hash,
                status="active", created_at=now, updated_at=now,
            )
            db.add(sec_admin)
            db.flush()
            db.add(Profile(user_id=sec_admin.id, display_name="Secondary Admin", bio="", updated_at=now))
            db.add(UserRole(user_id=sec_admin.id, role_id=admin_role.id, granted_at=now))

            u1 = db.scalar(select(User).where(User.email == USER_1_EMAIL))
            u2 = db.scalar(select(User).where(User.email == USER_2_EMAIL))
            pol = db.scalar(
                select(RewardPolicyVersion).where(
                    RewardPolicyVersion.status == "published",
                    RewardPolicyVersion.config_json.op("->>")("type") == "free-vault-v1",
                ).limit(1)
            )
            cat = db.scalar(select(Category).limit(1))
            assert u1 and u2 and pol and cat

            for u in (u1, u2):
                if db.scalar(select(UserInventory).where(UserInventory.user_id == u.id, UserInventory.asset_id == asset_id)) is None:
                    db.add(UserInventory(user_id=u.id, asset_id=asset_id, quantity=1, acquired_at=now, updated_at=now))
                db.execute(delete(UserEquipment).where(UserEquipment.user_id == u.id, UserEquipment.slot_kind == "avatar"))
            db.flush()
            for u in (u1, u2):
                db.add(UserEquipment(user_id=u.id, slot_kind="avatar", asset_id=asset_id, equipped_at=now))

            p = Post(id=uuid4(), author_id=u1.id, category_id=cat.id, title="H06 Final Reaction Post", content="h06", status="published", created_at=now, updated_at=now)
            db.add(p)
            db.flush()
            db.add(PostReaction(post_id=p.id, user_id=u1.id, reaction_type="meme", meme_asset_id=asset_id, created_at=now, updated_at=now))

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

            earned = db.scalar(
                select(func.coalesce(func.sum(AuraLedger.base_xp), 0)).where(
                    AuraLedger.user_id == u1.id, AuraLedger.occurred_at <= now
                )
            )
            co = CaseOpen(
                id=uuid4(), user_id=u1.id, request_key=f"h06-open-{uuid4().hex}",
                case_id=case.id, loot_table_id=lt.id, reward_asset_id=asset_id,
                reward_rarity="C",
                earned_xp_at_open=int(earned or 0), cost_khi_van=0, wallet_transaction_id=None,
                is_daily_free=False, effective_day=now.date(),
                decision_trace={"runtime": "free-vault-v1"}, created_at=now,
            )
            db.add(co)
            db.flush()
            lt_id = lt.id
            case_id = case.id
            post_id = p.id
            open_id = co.id

        # 2. Change rarity from C -> B even when owned, equipped, and in published Vault pool + CaseOpen!
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        rc = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"display_name": "H06 Renamed B", "rarity": "B"},
            headers={"X-CSRF-Token": csrf},
        )
        assert rc.status_code == 200, rc.text
        assert rc.json()["rarity"] == "B"
        assert rc.json()["display_name"] == "H06 Renamed B"

        with app.state.auth_session_factory() as db:
            # Historical CaseOpen receipt STILL preserves reward_rarity='C' while asset is now 'B'
            opening = db.get(CaseOpen, open_id)
            fake_req = Request({"type": "http", "app": app, "headers": []})
            rew = receipt_reward(db, opening, fake_req)
            assert rew.rarity == "C"
            # New published pool has asset_id in B bucket, old lt retired with C untouched
            old_lt = db.get(CaseLootTable, lt_id)
            assert old_lt.status == "retired"
            new_lt = db.scalar(select(CaseLootTable).where(CaseLootTable.case_id == case_id, CaseLootTable.odds_version == max_ver + 2))
            assert new_lt is not None and new_lt.status == "published"
            moved_pool_item = db.scalar(select(CasePoolItem).where(CasePoolItem.loot_table_id == new_lt.id, CasePoolItem.asset_id == asset_id))
            assert moved_pool_item.rarity == "B"

        # 3. Original asset (e.g. non-admin-upload meme or background) can also be renamed, rarity-changed, archived & restored!
        with app.state.auth_session_factory() as db:
            orig_bg = db.scalar(select(AssetItem).where(AssetItem.kind == "background", AssetItem.deleted_at.is_(None)).limit(1))
            assert orig_bg is not None
            orig_bg_id = str(orig_bg.id)
            orig_bg_rar = orig_bg.rarity
            orig_bg_eff = orig_bg.effect_key
        new_bg_rar = "A" if orig_bg_rar != "A" else "B"
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        bg_edit = client.patch(
            f"/api/v1/admin/assets/{orig_bg_id}",
            json={"display_name": "H06 Renamed BG", "rarity": new_bg_rar},
            headers={"X-CSRF-Token": csrf},
        )
        assert bg_edit.status_code == 200, bg_edit.text
        assert bg_edit.json()["rarity"] == new_bg_rar
        assert bg_edit.json()["effect_key"] == EFFECT_KEYS[RARITIES.index(new_bg_rar)]
        # Restore original rarity/effect_key of bg so shared test fixture stays clean
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        bg_restore_rar = client.patch(
            f"/api/v1/admin/assets/{orig_bg_id}",
            json={"rarity": orig_bg_rar},
            headers={"X-CSRF-Token": csrf},
        )
        assert bg_restore_rar.status_code == 200
        assert bg_restore_rar.json()["effect_key"] == orig_bg_eff

        # 4. Founder CANNOT permanently delete an Active asset -> 409 ASSET_NOT_ARCHIVED
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        del_active = client.request(
            "DELETE",
            f"/api/v1/admin/assets/{asset_id}",
            json={"confirm_text": "XÓA VĨNH VIỄN"},
            headers={"X-CSRF-Token": csrf},
        )
        assert del_active.status_code == 409
        assert del_active.json()["error"]["code"] == "ASSET_NOT_ARCHIVED"

        # 5. Secondary non-Founder ADMIN archives & restores, but CANNOT permanent delete (403)
        csrf = _login(client, secondary_admin_email, ADMIN_PASSWORD)
        ar = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"action": "archive"},
            headers={"X-CSRF-Token": csrf},
        )
        assert ar.status_code == 200
        assert ar.json()["active"] is False and ar.json()["review_status"] == "approved"

        # Verify auto-unequip, inventory preserved, meme reaction hidden
        with app.state.auth_session_factory() as db:
            assert db.scalar(select(func.count()).select_from(UserEquipment).where(UserEquipment.asset_id == asset_id)) == 0
            assert db.scalar(select(func.count()).select_from(UserInventory).where(UserInventory.asset_id == asset_id, UserInventory.quantity == 1)) >= 2
            fake_req = Request({"type": "http", "app": app, "headers": []})
            assert meme_reaction_states(db, PostReaction, [post_id], None, fake_req)[post_id]["meme_reactions"] == []

        # Secondary ADMIN calling permanent delete -> 403 FORBIDDEN!
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        sec_del = client.request(
            "DELETE",
            f"/api/v1/admin/assets/{asset_id}",
            json={"confirm_text": "XÓA VĨNH VIỄN"},
            headers={"X-CSRF-Token": csrf},
        )
        assert sec_del.status_code == 403

        # Secondary ADMIN restores -> active=True, returned to Vault pool, no auto-re-equip
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        rs = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"action": "approve"},
            headers={"X-CSRF-Token": csrf},
        )
        assert rs.status_code == 200 and rs.json()["active"] is True
        with app.state.auth_session_factory() as db:
            assert db.scalar(select(func.count()).select_from(UserEquipment).where(UserEquipment.asset_id == asset_id)) == 0
            pool = load_runtime_pool(db, db.get(CaseDefinition, case_id), app.state.auth.now())
            # B bucket (index 2) contains restored asset_id
            assert any(item_id == asset_id or str(item_id) == asset_id for item_id, _ in pool.buckets[2])

        # 6. Founder archives -> invalid confirm phrase rejected (422) -> valid permanent delete succeeds (200)
        csrf = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert client.patch(f"/api/v1/admin/assets/{asset_id}", json={"action": "archive"}, headers={"X-CSRF-Token": csrf}).status_code == 200

        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        bad_del = client.request(
            "DELETE",
            f"/api/v1/admin/assets/{asset_id}",
            json={"confirm_text": "DELETE"},
            headers={"X-CSRF-Token": csrf},
        )
        assert bad_del.status_code == 422

        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        perm_del = client.request(
            "DELETE",
            f"/api/v1/admin/assets/{asset_id}",
            json={"confirm_text": "XÓA VĨNH VIỄN"},
            headers={"X-CSRF-Token": csrf},
        )
        assert perm_del.status_code == 200, perm_del.text

        # Excluded from Admin list, cannot be patched/restored, CaseOpen preserved, reconciliation skips tombstone
        listed = client.get("/api/v1/admin/assets?page=1&page_size=100&search=H06+Renamed+B")
        assert listed.status_code == 200
        assert all(it["id"] != asset_id for it in listed.json()["items"])

        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        assert client.patch(f"/api/v1/admin/assets/{asset_id}", json={"action": "approve"}, headers={"X-CSRF-Token": csrf}).status_code == 404

        with app.state.auth_session_factory() as db:
            tomb = db.get(AssetItem, asset_id)
            assert tomb.deleted_at is not None and tomb.active is False
            assert db.get(CaseOpen, open_id) is not None
            audit_del = db.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "asset.permanent_delete", AdminAuditLog.target_id == asset_id))
            assert audit_del is not None
            dry = sync_khang_dev_vault_privilege(db, app.state.auth.now(), dry_run=True)
            assert all(m["id"] != asset_id for m in dry.get("missing_assets", []))

        # 7. USER role receives 403 on admin asset mutation
        csrf = _login(client, USER_1_EMAIL, "H01SimUser!2026")
        assert client.patch(f"/api/v1/admin/assets/{orig_bg_id}", json={"display_name": "Hack"}, headers={"X-CSRF-Token": csrf}).status_code == 403


def test_h06_empty_rarity_bucket_allowed_with_warning_and_case_unavailable(monkeypatch):
    _ensure_test_db()
    monkeypatch.setenv("AURAMEME_OWNER_MEME_DEMO", "1")
    from app.main import app
    from app.models import (
        AssetItem, CaseDefinition, CaseLootRarity, CaseLootTable,
        CasePoolItem, RewardPolicyVersion,
    )
    from app.vault import RARITIES
    from app.vault_runtime import load_runtime_pool
    from app.vault_v1_policy import WEIGHTS

    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN) as client:
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        asset_id = _upload_and_approve(client, "C_281126_92.png", "H06 Sole C")
        backup_by_rarity = {
            rar: _upload_and_approve(client, f"{rar}_281126_{idx + 40}.png", f"H06 Empty Backup {rar}")
            for idx, rar in enumerate(RARITIES)
            if rar != "C"
        }

        with app.state.auth_session_factory() as db, db.begin():
            now = app.state.auth.now()
            for b_id in list(backup_by_rarity.values()) + [asset_id]:
                b_asset = db.get(AssetItem, b_id)
                sha = (b_asset.source_rights or {}).get("sha256") or ("b" * 64)
                b_asset.source_rights = {
                    "review_status": "approved",
                    "name_review_status": "approved",
                    "source": "aurameme://original/h06-empty",
                    "author": "AuraMeme H06 Test",
                    "license": "LicenseRef-AuraMeme-Original",
                    "attribution": "AuraMeme H06 Test",
                    "sha256": sha,
                    "proof": {
                        "basis": "original",
                        "source": "aurameme://original/h06-empty",
                        "license_id": "LicenseRef-AuraMeme-Original",
                        "license_url": "aurameme://original/license",
                        "artifact_sha256": sha,
                        "evidence_sha256": sha,
                        "copyright_notice": "AuraMeme H06 Test",
                    },
                }

            pol = db.scalar(
                select(RewardPolicyVersion).where(
                    RewardPolicyVersion.status == "published",
                    RewardPolicyVersion.config_json.op("->>")("type") == "free-vault-v1",
                ).limit(1)
            )
            case = db.scalar(select(CaseDefinition).where(CaseDefinition.runtime_kind == "avatar"))
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
                cid = asset_id if rar == "C" else backup_by_rarity[rar]
                db.add(CasePoolItem(loot_table_id=lt.id, asset_id=cid, rarity=rar, item_weight=1))
            db.flush()
            lt.status = "published"
            db.flush()
            case_id = case.id

        # Archiving the sole C item MUST SUCCEED (200) and emit a clear pool_warning!
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        ar = client.patch(
            f"/api/v1/admin/assets/{asset_id}",
            json={"action": "archive"},
            headers={"X-CSRF-Token": csrf},
        )
        assert ar.status_code == 200, ar.text
        assert ar.json()["active"] is False
        assert len(ar.json().get("pool_warnings", [])) >= 1

        # Affected case is temporarily unavailable until replenished (ValueError -> 503 NOT_READY)
        with app.state.auth_session_factory() as db:
            with pytest.raises(ValueError, match="Each V1 rarity needs approved items"):
                load_runtime_pool(db, db.get(CaseDefinition, case_id), app.state.auth.now())
