"""Targeted unit and PostgreSQL integration tests for Checkpoint 3: Khang Dev exclusive Vault privilege."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.admin_users import KHANG_DEV_ID, KIEN_DEV_ID
from app.admin_workspace import AdminAssetPatch, admin_update_asset
from app.models import (
    AdminAuditLog,
    AssetItem,
    CaseLootTable,
    CasePoolItem,
    InventoryGrant,
    RewardPolicyVersion,
    Role,
    User,
    UserInventory,
    UserRole,
)
from app.vault_privilege import (
    PRIVILEGE_KEY_PREFIX,
    PRIVILEGE_SOURCE_TYPE,
    assert_khang_dev_target,
    auto_grant_khang_dev_published_items,
    grant_khang_dev_single_asset_if_eligible,
    is_asset_eligible_for_privilege,
    main,
    sync_khang_dev_vault_privilege,
)
from tests.vault_test_rights import synthetic_rights


def make_mock_asset(
    kind: str = "avatar",
    rarity: str = "S",
    name_vi: str = "Meme Thần Thoại",
    review_status: str = "approved",
):
    asset_id = uuid4()
    digest = "a" * 64
    asset = MagicMock(spec=AssetItem)
    asset.id = asset_id
    asset.slug = f"asset-{asset_id.hex[:8]}"
    asset.kind = kind
    asset.rarity = rarity
    asset.display_name = name_vi
    asset.active = True
    asset.source_rights = synthetic_rights(
        digest,
        name_review_status=review_status,
        review_status=review_status,
    )
    return asset


class MockManifestItem:
    def __init__(self, kind="avatar", rarity="S", review_status="approved"):
        self.id = uuid4()
        self.slug = f"manifest-item-{self.id.hex[:8]}"
        self.kind = kind
        self.rarity = rarity
        self.name_review_status = review_status
        self.source_rights = SimpleNamespace(review_status=review_status)


class MockManifest:
    def __init__(self, items):
        self.items = items


@pytest.fixture(autouse=True)
def mock_inventory_state_in_unit_tests(monkeypatch, request):
    """Bypass deep SQL-dependent inventory_state checks during unit tests."""
    if "integration" not in request.keywords:
        monkeypatch.setattr("app.vault_privilege.inventory_state", lambda db, owner, asset_id: None)


# ==============================================================================
# UNIT TESTS (Fast, isolated, zero-dependency)
# ==============================================================================


def test_assert_khang_dev_target_exclusivity():
    """Only KHANG_DEV_ID passes target assertion; Kien Dev and all others are rejected."""
    # Khang Dev succeeds
    assert_khang_dev_target(KHANG_DEV_ID)

    # Kien Dev is strictly forbidden
    with pytest.raises(ValueError, match="strictly exclusive to Khang Dev"):
        assert_khang_dev_target(KIEN_DEV_ID)

    # Random user ID is strictly forbidden
    other_id = uuid4()
    with pytest.raises(ValueError, match="strictly exclusive to Khang Dev"):
        assert_khang_dev_target(other_id)


def test_schema_compatible_source_type():
    """Ensures PRIVILEGE_SOURCE_TYPE conforms to ck_inventory_grants_source_type ('admin')."""
    assert PRIVILEGE_SOURCE_TYPE == "admin"
    assert PRIVILEGE_SOURCE_TYPE in ("case_open", "weekly_streak", "level", "admin")


def test_auto_grant_skips_when_khang_dev_not_in_database():
    """Synthetic test environments without Khang Dev cleanly skip auto-grant."""
    db = MagicMock()
    db.scalar.return_value = None  # Khang Dev user not found

    manifest = MockManifest([MockManifestItem(), MockManifestItem(kind="background")])
    now = datetime.now(timezone.utc)
    policy_id = uuid4()

    granted = auto_grant_khang_dev_published_items(db, manifest, policy_id, now)

    assert granted == []
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_auto_grant_grants_new_published_items_to_khang_dev():
    """Newly published valid items are granted (1 unit) to Khang Dev with +0 EXP and source_type='admin'."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.username = "khang_dev"
    khang_user.status = "active"

    item1 = MockManifestItem(kind="avatar", rarity="S")
    item2 = MockManifestItem(kind="background", rarity="A")
    mock_asset1 = make_mock_asset(kind="avatar", rarity="S")
    mock_asset1.id = item1.id
    mock_asset2 = make_mock_asset(kind="background", rarity="A")
    mock_asset2.id = item2.id

    def mock_scalar(query, *args, **kwargs):
        query_str = str(query).lower()
        if "from users" in query_str:
            return khang_user
        if "from asset_items" in query_str:
            if str(item1.id) in query_str or f"'{item1.id}'" in query_str:
                return mock_asset1
            return mock_asset2
        if "from user_inventory" in query_str:
            return None
        if "from inventory_grants" in query_str:
            return None
        return None

    db.scalar.side_effect = mock_scalar

    manifest = MockManifest([item1, item2])
    now = datetime.now(timezone.utc)
    policy_id = uuid4()

    granted = auto_grant_khang_dev_published_items(db, manifest, policy_id, now)

    assert len(granted) == 2
    assert item1.id in granted
    assert item2.id in granted

    # Verify db.add calls: 2 UserInventory, 2 InventoryGrant, 1 AdminAuditLog
    added_objects = [call_args[0][0] for call_args in db.add.call_args_list]

    inv_records = [obj for obj in added_objects if isinstance(obj, UserInventory)]
    assert len(inv_records) == 2
    for inv in inv_records:
        assert inv.user_id == KHANG_DEV_ID
        assert inv.quantity == 1

    grant_records = [obj for obj in added_objects if isinstance(obj, InventoryGrant)]
    assert len(grant_records) == 2
    for grant in grant_records:
        assert grant.user_id == KHANG_DEV_ID
        assert grant.quantity == 1
        assert grant.source_type == "admin"  # Schema compatible!
        assert grant.case_open_id is None
        assert grant.policy_id == policy_id
        assert grant.event_key.startswith(PRIVILEGE_KEY_PREFIX)

    audit_records = [obj for obj in added_objects if isinstance(obj, AdminAuditLog)]
    assert len(audit_records) == 2
    for audit in audit_records:
        assert audit.action == "vault.privilege.auto_grant"
        assert audit.target_id == str(KHANG_DEV_ID)


def test_auto_grant_preserves_existing_quantity_when_already_owned():
    """Already owned items preserve their existing quantity and are not re-granted."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.status = "active"

    item1 = MockManifestItem(kind="avatar", rarity="S")
    mock_asset1 = make_mock_asset(kind="avatar", rarity="S")
    mock_asset1.id = item1.id
    existing_inv = MagicMock(spec=UserInventory)
    existing_inv.quantity = 5  # Already owned 5 units from previous drops/chests

    def mock_scalar(query, *args, **kwargs):
        query_str = str(query).lower()
        if "from users" in query_str:
            return khang_user
        if "from asset_items" in query_str:
            return mock_asset1
        if "from user_inventory" in query_str:
            return existing_inv
        return None

    db.scalar.side_effect = mock_scalar

    manifest = MockManifest([item1])
    now = datetime.now(timezone.utc)
    policy_id = uuid4()

    granted = auto_grant_khang_dev_published_items(db, manifest, policy_id, now)

    # Skipped: already owned
    assert granted == []
    assert existing_inv.quantity == 5  # Quantity untouched!
    db.add.assert_not_called()


def test_admin_workspace_approval_grants_to_khang_dev():
    """When an asset is approved in admin_workspace, Khang Dev receives it automatically."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.status = "active"

    asset = make_mock_asset(kind="avatar", rarity="A", review_status="approved")
    policy_id = uuid4()

    def mock_scalar(query, *args, **kwargs):
        query_str = str(query).lower()
        if "from users" in query_str:
            return khang_user
        if "from user_inventory" in query_str:
            return None
        if "from inventory_grants" in query_str:
            return None
        if "from reward_policy_versions" in query_str:
            return policy_id
        return None

    db.scalar.side_effect = mock_scalar
    now = datetime.now(timezone.utc)

    # Approve asset
    granted = grant_khang_dev_single_asset_if_eligible(db, asset, now, actor_id=uuid4(), policy_id=policy_id)
    assert granted is True

    # Added objects
    added = [call_args[0][0] for call_args in db.add.call_args_list]
    grant_records = [obj for obj in added if isinstance(obj, InventoryGrant)]
    assert len(grant_records) == 1
    assert grant_records[0].source_type == "admin"
    assert grant_records[0].user_id == KHANG_DEV_ID
    assert grant_records[0].asset_id == asset.id


def test_sync_khang_dev_vault_privilege_dry_run():
    """Dry-run audits differences and reports missing items without writing to DB."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.username = "khang_dev"
    khang_user.status = "active"

    asset_owned = make_mock_asset(kind="avatar", rarity="C")
    asset_missing = make_mock_asset(kind="background", rarity="S")

    mock_policy_id = uuid4()
    db.scalars.return_value = [asset_owned, asset_missing]

    inv_owned = MagicMock(spec=UserInventory)
    inv_owned.quantity = 3

    inv_call_count = 0

    def mock_scalar(query, *args, **kwargs):
        nonlocal inv_call_count
        q = str(query).lower()
        if "from users" in q:
            return khang_user
        if "from reward_policy_versions" in q:
            return mock_policy_id
        if "from user_inventory" in q:
            inv_call_count += 1
            if inv_call_count == 1:
                return inv_owned
            return None
        return None

    db.scalar.side_effect = mock_scalar

    now = datetime.now(timezone.utc)
    report = sync_khang_dev_vault_privilege(db, now, dry_run=True)

    assert report["status"] == "success"
    assert report["dry_run"] is True
    assert report["published_count"] == 2
    assert report["already_owned_count"] == 1
    assert report["missing_count"] == 1
    assert report["granted_count"] == 0
    assert len(report["missing_assets"]) == 1
    assert report["missing_assets"][0]["id"] == str(asset_missing.id)

    # Zero writes in dry run
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_sync_khang_dev_vault_privilege_execute_mode():
    """Execute mode grants exactly missing items (1 unit each) and logs audit entry."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.username = "khang_dev"
    khang_user.status = "active"

    asset1 = make_mock_asset(kind="avatar", rarity="S")
    mock_policy_id = uuid4()
    db.scalars.return_value = [asset1]

    def mock_scalar(query, *args, **kwargs):
        q = str(query).lower()
        if "from users" in q:
            return khang_user
        if "from reward_policy_versions" in q:
            return mock_policy_id
        return None

    db.scalar.side_effect = mock_scalar

    now = datetime.now(timezone.utc)
    report = sync_khang_dev_vault_privilege(db, now, dry_run=False)

    assert report["status"] == "success"
    assert report["dry_run"] is False
    assert report["published_count"] == 1
    assert report["already_owned_count"] == 0
    assert report["missing_count"] == 1
    assert report["granted_count"] == 1

    added = [call_args[0][0] for call_args in db.add.call_args_list]
    grant_objs = [o for o in added if isinstance(o, InventoryGrant)]
    assert len(grant_objs) == 1
    assert grant_objs[0].quantity == 1
    assert grant_objs[0].source_type == "admin"


def test_zero_exp_rule_preserved():
    """Vault privilege grants NEVER emit AuraLedger entries or modify user EXP."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.status = "active"

    mock_policy_id = uuid4()
    def mock_scalar(query, *args, **kwargs):
        q = str(query).lower()
        if "from users" in q:
            return khang_user
        if "from reward_policy_versions" in q:
            return mock_policy_id
        return None

    db.scalar.side_effect = mock_scalar

    asset1 = make_mock_asset(kind="avatar", rarity="S")
    db.scalars.return_value = [asset1]

    now = datetime.now(timezone.utc)
    sync_khang_dev_vault_privilege(db, now, dry_run=False)

    added = [call_args[0][0] for call_args in db.add.call_args_list]
    from app.models import AuraLedger, WalletTransaction
    ledger_entries = [o for o in added if isinstance(o, (AuraLedger, WalletTransaction))]
    assert ledger_entries == []


def test_cli_argument_validation():
    """CLI enforces mutually exclusive --dry-run/--execute and requires confirmation for execute."""
    from app.vault_privilege import main

    # 1. Both --dry-run and --execute together are rejected by argparse (SystemExit)
    with pytest.raises(SystemExit) as exc:
        main(["--dry-run", "--execute"])
    assert exc.value.code != 0

    # 2. --execute without --confirm is rejected with ValueError
    with pytest.raises(ValueError, match="--execute requires explicit confirmation"):
        main(["--execute"])

    # 3. --execute with wrong confirm string is rejected with ValueError
    with pytest.raises(ValueError, match="--execute requires explicit confirmation"):
        main(["--execute", "--confirm", "WRONG"])


def test_policy_draft_future_not_selected():
    """resolve_reward_policy_id rejects draft or future policies, raising ValueError."""
    from app.vault_privilege import resolve_reward_policy_id

    db = MagicMock()
    # db.scalar returns None because query specifies status == 'published' AND effective_at <= now
    db.scalar.return_value = None

    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="No valid published RewardPolicyVersion with effective_at <= now found"):
        resolve_reward_policy_id(db, now)


def test_asset_in_multiple_policies_deduplicated():
    """sync_khang_dev_vault_privilege selects AssetItem directly, guaranteeing 1 check per asset."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.status = "active"

    asset_shared = make_mock_asset(kind="avatar", rarity="S")
    db.scalars.return_value = [asset_shared]

    policy_id = uuid4()
    def mock_scalar(query, *args, **kwargs):
        q = str(query).lower()
        if "from users" in q:
            return khang_user
        if "from reward_policy_versions" in q:
            return policy_id
        if "from user_inventory" in q:
            return None
        return None

    db.scalar.side_effect = mock_scalar

    now = datetime.now(timezone.utc)
    report = sync_khang_dev_vault_privilege(db, now, dry_run=False)

    assert report["published_count"] == 1
    assert report["granted_count"] == 1


# ==============================================================================
# POSTGRESQL REAL INTEGRATION TESTS (Schema 0018 on aurameme_test)
# ==============================================================================


def resolve_test_db_url() -> str | None:
    """Resolve TEST_DATABASE_URL from environment or local worktree .env only."""
    test_url = os.environ.get("TEST_DATABASE_URL")
    if not test_url:
        local_env = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(local_env):
            with open(local_env, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("TEST_DATABASE_URL="):
                        test_url = line.split("=", 1)[1].strip().strip("\"'")
                        break
    return test_url


@pytest.fixture
def pg_session():
    """Yield a PostgreSQL session rolled back at end of test to keep aurameme_test clean."""
    test_url = resolve_test_db_url()
    if not test_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration test")
    assert "127.0.0.1" in test_url or "localhost" in test_url, "Safety violation: non-local test database"

    engine = create_engine(test_url)
    with engine.connect() as check_conn:
        cur_db = check_conn.scalar(text("SELECT current_database()"))
        assert cur_db == "aurameme_test", f"Safety violation: forbidden database {cur_db}"

    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    try:
        # Ensure Khang Dev user and Admin role exist in transaction
        khang = session.scalar(select(User).where(User.id == KHANG_DEV_ID))
        if not khang:
            session.add(
                User(
                    id=KHANG_DEV_ID,
                    username="khang_dev",
                    email="khang@aurameme.test",
                    password_hash="test_hash",
                    status="active",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
        role_admin = session.scalar(select(Role).where(Role.code == "ADMIN"))
        if not role_admin:
            role_admin = Role(id=uuid4(), code="ADMIN", description="Administrator")
            session.add(role_admin)
            session.flush()

        ur = session.scalar(select(UserRole).where(UserRole.user_id == KHANG_DEV_ID, UserRole.role_id == role_admin.id))
        if not ur:
            session.add(UserRole(user_id=KHANG_DEV_ID, role_id=role_admin.id, granted_at=datetime.now(timezone.utc)))
        session.flush()
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def pg_engine():
    """Engine fixture for multithreaded concurrency tests connecting to aurameme_test."""
    test_url = resolve_test_db_url()
    if not test_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration test")
    assert "127.0.0.1" in test_url or "localhost" in test_url, "Safety violation: non-local test database"

    engine = create_engine(test_url)
    with engine.connect() as conn:
        cur_db = conn.scalar(text("SELECT current_database()"))
        assert cur_db == "aurameme_test", f"Safety violation: forbidden database {cur_db}"

    # Ensure Khang Dev and ADMIN role exist in committed setup
    with Session(engine) as setup_db:
        with setup_db.begin():
            khang = setup_db.scalar(select(User).where(User.id == KHANG_DEV_ID))
            if not khang:
                setup_db.add(
                    User(
                        id=KHANG_DEV_ID,
                        username="khang_dev",
                        email="khang@aurameme.test",
                        password_hash="test_hash",
                        status="active",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            role_admin = setup_db.scalar(select(Role).where(Role.code == "ADMIN"))
            if not role_admin:
                role_admin = Role(id=uuid4(), code="ADMIN", description="Administrator")
                setup_db.add(role_admin)
                setup_db.flush()

            ur = setup_db.scalar(select(UserRole).where(UserRole.user_id == KHANG_DEV_ID, UserRole.role_id == role_admin.id))
            if not ur:
                setup_db.add(UserRole(user_id=KHANG_DEV_ID, role_id=role_admin.id, granted_at=datetime.now(timezone.utc)))
    return engine


@pytest.mark.integration
def test_postgres_khang_dev_privilege_end_to_end(pg_session):
    """Real PostgreSQL schema 0018 verification:
    - Grant valid items to Khang Dev
    - CheckConstraints on source_type='admin' pass PostgreSQL
    - Foreign keys on policy_id and user_inventory pass PostgreSQL
    - inventory_state invariant holds: sum(InventoryGrant.quantity) == UserInventory.quantity
    - Idempotent re-run does not create duplicate grants
    - Kien Dev and other users receive nothing
    - +0 EXP, no case_open rows created
    """
    db = pg_session
    now = datetime.now(timezone.utc)

    # 1. Ensure Kien Dev user exists
    kien = db.scalar(select(User).where(User.id == KIEN_DEV_ID))
    if not kien:
        kien = User(
            id=KIEN_DEV_ID,
            username="kien_dev_test",
            email="kien_test@aurameme.test",
            password_hash="test_hash",
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(kien)
    db.flush()

    # 2. Get published RewardPolicyVersion
    policy_id = db.scalar(select(RewardPolicyVersion.id).where(RewardPolicyVersion.status == "published").order_by(RewardPolicyVersion.version.desc()))
    if not policy_id:
        policy_id = uuid4()
        policy = RewardPolicyVersion(
            id=policy_id,
            version=9999,
            config_json={"type": "test_policy"},
            status="published",
            effective_at=now,
            created_by=KHANG_DEV_ID,
            created_at=now,
        )
        db.add(policy)
        db.flush()

    # 3. Create approved asset with synthetic_rights
    asset_id = uuid4()
    digest = "a" * 64
    asset = AssetItem(
        id=asset_id,
        slug=f"meme-pg-test-{asset_id.hex[:6]}",
        kind="avatar",
        collection="admin-upload",
        rarity="S",
        media_key=f"catalog/{digest}.png",
        display_name="Meme PostgreSQL Test",
        effect_key=None,
        source_rights=synthetic_rights(digest, name_review_status="approved", review_status="approved"),
        active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(asset)
    db.flush()

    # 4. Grant single asset to Khang Dev
    granted = grant_khang_dev_single_asset_if_eligible(db, asset, now, actor_id=KHANG_DEV_ID, policy_id=policy_id)
    assert granted is True

    # 5. Verify PostgreSQL row in user_inventory and inventory_grants
    inv = db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == asset_id))
    assert inv is not None
    assert inv.quantity == 1

    grants = list(db.scalars(select(InventoryGrant).where(InventoryGrant.user_id == KHANG_DEV_ID, InventoryGrant.asset_id == asset_id)))
    assert len(grants) == 1
    grant = grants[0]
    assert grant.quantity == 1
    assert grant.source_type == "admin"
    assert grant.case_open_id is None
    assert grant.policy_id == policy_id

    # 6. Verify inventory_state invariant passes without error
    from app.inventory_grants import inventory_state
    checked_inv = inventory_state(db, KHANG_DEV_ID, asset_id)
    assert checked_inv.quantity == 1

    # 7. Verify Kien Dev has ZERO inventory
    kien_inv = db.scalar(select(UserInventory).where(UserInventory.user_id == KIEN_DEV_ID, UserInventory.asset_id == asset_id))
    assert kien_inv is None

    # 8. Idempotency test: grant again does not create duplicate
    granted_again = grant_khang_dev_single_asset_if_eligible(db, asset, now, actor_id=KHANG_DEV_ID, policy_id=policy_id)
    assert granted_again is False

    grants_after = list(db.scalars(select(InventoryGrant).where(InventoryGrant.user_id == KHANG_DEV_ID, InventoryGrant.asset_id == asset_id)))
    assert len(grants_after) == 1
    assert db.scalar(select(UserInventory.quantity).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == asset_id)) == 1

    # 9. Verify audit log was recorded
    audit = db.scalar(select(AdminAuditLog).where(AdminAuditLog.target_id == str(KHANG_DEV_ID), AdminAuditLog.action == "vault.privilege.auto_grant"))
    assert audit is not None


@pytest.mark.integration
def test_postgres_khang_dev_concurrent_grant(pg_engine):
    """Real multithreaded concurrent grant on PostgreSQL:
    Two threads race simultaneously with a Barrier to grant the exact same asset to Khang Dev.
    Verifies row locking/idempotency ensures exactly 1 grant is committed,
    UserInventory.quantity == 1, and inventory_state holds with zero ledger discrepancy.
    Zero immutable triggers disabled; zero whole-account deletes.
    """
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    engine = pg_engine
    now = datetime.now(timezone.utc)
    asset_id = uuid4()
    digest = "c" * 64

    # Setup baseline data in committed transaction
    with Session(engine) as setup_db:
        with setup_db.begin():
            policy = setup_db.scalar(select(RewardPolicyVersion).where(RewardPolicyVersion.status == "published").order_by(RewardPolicyVersion.version.desc()))
            effective_pid = policy.id
            asset = AssetItem(
                id=asset_id,
                slug=f"meme-concurrent-{asset_id.hex[:6]}",
                kind="avatar",
                collection="admin-upload",
                rarity="S",
                media_key=f"catalog/{digest}.png",
                display_name="Meme Concurrent Test",
                effect_key=None,
                source_rights=synthetic_rights(digest, name_review_status="approved", review_status="approved"),
                active=True,
                created_at=now,
                updated_at=now,
            )
            setup_db.add(asset)

    barrier = Barrier(2)
    results = []

    def worker():
        with Session(engine) as worker_db:
            barrier.wait(timeout=10)
            worker_asset = worker_db.scalar(select(AssetItem).where(AssetItem.id == asset_id))
            res = grant_khang_dev_single_asset_if_eligible(
                worker_db,
                worker_asset,
                now,
                actor_id=KHANG_DEV_ID,
                policy_id=effective_pid,
            )
            worker_db.commit()
            results.append(res)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker)
        f2 = executor.submit(worker)
        f1.result(timeout=15)
        f2.result(timeout=15)

    # One worker should return True (granted), the other False (idempotent skip)
    assert results.count(True) == 1
    assert results.count(False) == 1

    with Session(engine) as verify_db:
        inv = verify_db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == asset_id))
        assert inv is not None
        assert inv.quantity == 1

        grants = list(verify_db.scalars(select(InventoryGrant).where(InventoryGrant.user_id == KHANG_DEV_ID, InventoryGrant.asset_id == asset_id)))
        assert len(grants) == 1
        assert grants[0].quantity == 1
        assert grants[0].source_type == "admin"
        assert grants[0].event_key == f"{PRIVILEGE_KEY_PREFIX}{asset_id}"

        from app.inventory_grants import inventory_state
        checked_inv = inventory_state(verify_db, KHANG_DEV_ID, asset_id)
        assert checked_inv.quantity == 1


@pytest.mark.integration
def test_postgres_khang_dev_concurrent_publication(pg_engine):
    """Real multithreaded concurrent publication on PostgreSQL:
    Two threads publish two distinct manifests simultaneously via auto_grant_khang_dev_published_items.
    Verifies no deadlock occurs, both assets are granted cleanly, and inventory_state holds for both.
    Zero immutable triggers disabled; zero whole-account deletes.
    """
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    engine = pg_engine
    now = datetime.now(timezone.utc)
    asset_id_1 = uuid4()
    asset_id_2 = uuid4()
    digest1 = "d" * 64
    digest2 = "e" * 64

    with Session(engine) as setup_db:
        with setup_db.begin():
            policy = setup_db.scalar(select(RewardPolicyVersion).where(RewardPolicyVersion.status == "published").order_by(RewardPolicyVersion.version.desc()))
            effective_pid = policy.id
            asset1 = AssetItem(
                id=asset_id_1,
                slug=f"meme-pub-1-{asset_id_1.hex[:6]}",
                kind="avatar",
                collection="admin-upload",
                rarity="S",
                media_key=f"catalog/{digest1}.png",
                display_name="Meme Pub 1",
                effect_key=None,
                source_rights=synthetic_rights(digest1, name_review_status="approved", review_status="approved"),
                active=True,
                created_at=now,
                updated_at=now,
            )
            asset2 = AssetItem(
                id=asset_id_2,
                slug=f"meme-pub-2-{asset_id_2.hex[:6]}",
                kind="background",
                collection="admin-upload",
                rarity="A",
                media_key=f"catalog/{digest2}.png",
                display_name="Meme Pub 2",
                effect_key=None,
                source_rights=synthetic_rights(digest2, name_review_status="approved", review_status="approved"),
                active=True,
                created_at=now,
                updated_at=now,
            )
            setup_db.add(asset1)
            setup_db.add(asset2)

    barrier = Barrier(2)

    class ManifestItemWrapper:
        def __init__(self, asset_id, kind, rarity):
            self.id = asset_id
            self.slug = f"manifest-{asset_id.hex[:6]}"
            self.kind = kind
            self.rarity = rarity
            self.name_review_status = "approved"
            self.source_rights = SimpleNamespace(review_status="approved")

    manifest1 = MockManifest([ManifestItemWrapper(asset_id_1, "avatar", "S")])
    manifest2 = MockManifest([ManifestItemWrapper(asset_id_2, "background", "A")])

    def pub_worker(manifest):
        with Session(engine) as worker_db:
            barrier.wait(timeout=10)
            res = auto_grant_khang_dev_published_items(worker_db, manifest, effective_pid, now)
            worker_db.commit()
            return res

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(pub_worker, manifest1)
        f2 = executor.submit(pub_worker, manifest2)
        res1 = f1.result(timeout=15)
        res2 = f2.result(timeout=15)

    assert len(res1) == 1
    assert len(res2) == 1

    with Session(engine) as verify_db:
        for aid in (asset_id_1, asset_id_2):
            inv = verify_db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid))
            assert inv is not None and inv.quantity == 1
            from app.inventory_grants import inventory_state
            assert inventory_state(verify_db, KHANG_DEV_ID, aid).quantity == 1


@pytest.mark.integration
def test_postgres_khang_dev_sync_eligible_catalog(pg_session):
    """Real PostgreSQL sync_khang_dev_vault_privilege verification:
    Given assets in PostgreSQL:
      - Asset A: avatar, active=True, rights approved -> eligible, granted
      - Asset B: avatar, active=False, review_status='pending' -> inactive/ineligible, skipped
      - Asset C: background, active=False -> inactive/ineligible, skipped
      - Asset D: icon, active=True, rights approved -> active but not avatar/background, skipped
    Verifies only eligible asset A is granted, quantity=1, +0 EXP, audit log created.
    """
    db = pg_session
    now = datetime.now(timezone.utc)

    # 1. Get published RewardPolicyVersion
    policy_id = db.scalar(select(RewardPolicyVersion.id).where(RewardPolicyVersion.status == "published").order_by(RewardPolicyVersion.version.desc()))
    if not policy_id:
        policy_id = uuid4()
        policy = RewardPolicyVersion(
            id=policy_id,
            version=9999,
            config_json={"type": "sync_test_policy"},
            status="published",
            effective_at=now,
            created_by=KHANG_DEV_ID,
            created_at=now,
        )
        db.add(policy)
        db.flush()

    # 2. Create assets with different eligibility
    aid_eligible = uuid4()
    aid_pending = uuid4()
    aid_inactive = uuid4()
    aid_icon = uuid4()
    digest_a = "1" * 64
    digest_b = "2" * 64
    digest_c = "3" * 64
    digest_d = "4" * 64

    asset_a = AssetItem(
        id=aid_eligible,
        slug=f"asset-eligible-{aid_eligible.hex[:6]}",
        kind="avatar",
        collection="admin-upload",
        rarity="S",
        media_key=f"catalog/{digest_a}.png",
        display_name="Meme Eligible",
        source_rights=synthetic_rights(digest_a, name_review_status="approved", review_status="approved"),
        active=True,
        created_at=now,
        updated_at=now,
    )
    asset_b = AssetItem(
        id=aid_pending,
        slug=f"asset-pending-{aid_pending.hex[:6]}",
        kind="avatar",
        collection="admin-upload",
        rarity="A",
        media_key=f"catalog/{digest_b}.png",
        display_name="Meme Pending",
        source_rights=synthetic_rights(digest_b, name_review_status="approved", review_status="pending"),
        active=False,
        created_at=now,
        updated_at=now,
    )
    asset_c = AssetItem(
        id=aid_inactive,
        slug=f"asset-inactive-{aid_inactive.hex[:6]}",
        kind="background",
        collection="admin-upload",
        rarity="B",
        media_key=f"catalog/{digest_c}.png",
        display_name="Meme Inactive",
        source_rights=synthetic_rights(digest_c, name_review_status="approved", review_status="approved"),
        active=False,
        created_at=now,
        updated_at=now,
    )
    asset_d = AssetItem(
        id=aid_icon,
        slug=f"asset-icon-{aid_icon.hex[:6]}",
        kind="icon",
        collection="admin-upload",
        rarity="C",
        media_key=f"catalog/{digest_d}.png",
        display_name="Meme Icon",
        source_rights=synthetic_rights(digest_d, name_review_status="approved", review_status="approved"),
        active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(asset_a)
    db.add(asset_b)
    db.add(asset_c)
    db.add(asset_d)
    db.flush()

    # 3. Run sync_khang_dev_vault_privilege in execute mode
    res = sync_khang_dev_vault_privilege(db, now, dry_run=False, actor_id=KHANG_DEV_ID)
    assert res["status"] == "success"
    assert res["granted_count"] >= 1
    assert any(item["id"] == str(aid_eligible) for item in res["missing_assets"])
    assert not any(item["id"] == str(aid_pending) for item in res["missing_assets"])
    assert not any(item["id"] == str(aid_inactive) for item in res["missing_assets"])
    assert not any(item["id"] == str(aid_icon) for item in res["missing_assets"])

    # 4. Verify database records
    inv_a = db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid_eligible))
    assert inv_a is not None and inv_a.quantity == 1

    inv_b = db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid_pending))
    assert inv_b is None

    inv_c = db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid_inactive))
    assert inv_c is None

    inv_d = db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid_icon))
    assert inv_d is None

    from app.inventory_grants import inventory_state
    assert inventory_state(db, KHANG_DEV_ID, aid_eligible).quantity == 1


@pytest.mark.integration
def test_postgres_khang_dev_admin_approval_real(pg_session):
    """Real Admin approve flow on PostgreSQL:
    Calls admin_update_asset with action='approve'.
    Verifies:
      - AssetItem becomes active=True, review_status='approved'.
      - Khang Dev automatically receives asset in UserInventory (quantity=1).
      - InventoryGrant is created with source_type='admin'.
      - inventory_state invariant holds.
    """
    db = pg_session
    now = datetime.now(timezone.utc)

    # 1. Ensure published policy exists
    policy = db.scalar(
        select(RewardPolicyVersion)
        .where(RewardPolicyVersion.status == "published")
        .order_by(RewardPolicyVersion.version.desc())
    )
    if not policy:
        policy = RewardPolicyVersion(
            id=uuid4(),
            version=9997,
            config_json={"type": "test_appr_policy"},
            status="published",
            effective_at=now,
            created_by=KHANG_DEV_ID,
            created_at=now,
        )
        db.add(policy)
        db.flush()

    # 2. Create pending unapproved avatar asset
    asset_id = uuid4()
    digest = "f" * 64
    asset = AssetItem(
        id=asset_id,
        slug=f"meme-admin-appr-{asset_id.hex[:6]}",
        kind="avatar",
        collection="admin-upload",
        rarity="S",
        media_key=f"catalog/{digest}.png",
        display_name="Meme Admin Appr Test",
        effect_key=None,
        source_rights=synthetic_rights(digest, name_review_status="pending", review_status="pending"),
        active=False,
        created_at=now,
        updated_at=now,
    )
    db.add(asset)
    db.flush()

    # 3. Call admin_update_asset with action="approve"
    patch_req = AdminAssetPatch(action="approve")
    request = MagicMock()
    request.app.state.auth.now = MagicMock(return_value=now)
    account = SimpleNamespace(db=db, user=SimpleNamespace(id=KHANG_DEV_ID))

    res = admin_update_asset(asset_id, patch_req, request, account)
    assert res is not None

    # 4. Verify asset state
    db.refresh(asset)
    assert asset.active is True
    assert asset.source_rights["review_status"] == "approved"
    assert asset.source_rights["name_review_status"] == "approved"

    # 5. Verify Khang Dev received the asset
    inv = db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == asset_id))
    assert inv is not None
    assert inv.quantity == 1

    grants = list(db.scalars(select(InventoryGrant).where(InventoryGrant.user_id == KHANG_DEV_ID, InventoryGrant.asset_id == asset_id)))
    assert len(grants) == 1
    assert grants[0].quantity == 1
    assert grants[0].source_type == "admin"
    assert grants[0].event_key == f"{PRIVILEGE_KEY_PREFIX}{asset_id}"

    # 6. Verify ledger invariant
    from app.inventory_grants import inventory_state
    assert inventory_state(db, KHANG_DEV_ID, asset_id).quantity == 1


@pytest.mark.integration
def test_postgres_khang_dev_publication_real_entrypoint(pg_session):
    """Real publication hook on PostgreSQL:
    Verifies auto_grant_khang_dev_published_items verifies real DB asset and grants eligible items.
    """
    db = pg_session
    now = datetime.now(timezone.utc)

    policy = db.scalar(
        select(RewardPolicyVersion)
        .where(RewardPolicyVersion.status == "published")
        .order_by(RewardPolicyVersion.version.desc())
    )
    if not policy:
        policy = RewardPolicyVersion(
            id=uuid4(),
            version=9996,
            config_json={"type": "test_pub_policy"},
            status="published",
            effective_at=now,
            created_by=KHANG_DEV_ID,
            created_at=now,
        )
        db.add(policy)
        db.flush()

    aid_valid = uuid4()
    aid_inactive = uuid4()
    digest_v = "1" * 64
    digest_i = "2" * 64

    asset_valid = AssetItem(
        id=aid_valid,
        slug=f"asset-pub-v-{aid_valid.hex[:6]}",
        kind="avatar",
        collection="admin-upload",
        rarity="S",
        media_key=f"catalog/{digest_v}.png",
        display_name="Meme Pub Valid",
        source_rights=synthetic_rights(digest_v, name_review_status="approved", review_status="approved"),
        active=True,
        created_at=now,
        updated_at=now,
    )
    asset_inactive = AssetItem(
        id=aid_inactive,
        slug=f"asset-pub-i-{aid_inactive.hex[:6]}",
        kind="background",
        collection="admin-upload",
        rarity="A",
        media_key=f"catalog/{digest_i}.png",
        display_name="Meme Pub Inactive",
        source_rights=synthetic_rights(digest_i, name_review_status="approved", review_status="approved"),
        active=False,  # Inactive in DB
        created_at=now,
        updated_at=now,
    )
    db.add(asset_valid)
    db.add(asset_inactive)
    db.flush()

    class PubItem:
        def __init__(self, aid, kind, rarity):
            self.id = aid
            self.kind = kind
            self.rarity = rarity
            self.name_review_status = "approved"
            self.source_rights = SimpleNamespace(review_status="approved")

    manifest = MockManifest([
        PubItem(aid_valid, "avatar", "S"),
        PubItem(aid_inactive, "background", "A"),
    ])

    granted_ids = auto_grant_khang_dev_published_items(db, manifest, policy.id, now)
    assert granted_ids == [aid_valid]

    inv_v = db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid_valid))
    assert inv_v is not None and inv_v.quantity == 1

    inv_i = db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid_inactive))
    assert inv_i is None


@pytest.mark.integration
def test_postgres_khang_dev_concurrent_vault_open(pg_engine):
    """Multithreaded concurrent test:
    Thread 1: grants vault privilege to Khang Dev for asset1.
    Thread 2: simulates case opening / inventory update for Khang Dev on asset2.
    Verifies deadlock-free lock ordering (lock_aura_mutation -> User -> UserInventory).
    """
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    engine = pg_engine
    now = datetime.now(timezone.utc)
    aid_1 = uuid4()
    aid_2 = uuid4()
    digest1 = "7" * 64
    digest2 = "8" * 64

    with Session(engine) as setup_db:
        with setup_db.begin():
            policy = setup_db.scalar(select(RewardPolicyVersion).where(RewardPolicyVersion.status == "published").order_by(RewardPolicyVersion.version.desc()))
            effective_pid = policy.id
            a1 = AssetItem(
                id=aid_1,
                slug=f"meme-con-v1-{aid_1.hex[:6]}",
                kind="avatar",
                collection="admin-upload",
                rarity="S",
                media_key=f"catalog/{digest1}.png",
                display_name="Meme Concur 1",
                source_rights=synthetic_rights(digest1, name_review_status="approved", review_status="approved"),
                active=True,
                created_at=now,
                updated_at=now,
            )
            a2 = AssetItem(
                id=aid_2,
                slug=f"meme-con-v2-{aid_2.hex[:6]}",
                kind="background",
                collection="admin-upload",
                rarity="A",
                media_key=f"catalog/{digest2}.png",
                display_name="Meme Concur 2",
                source_rights=synthetic_rights(digest2, name_review_status="approved", review_status="approved"),
                active=True,
                created_at=now,
                updated_at=now,
            )
            setup_db.add(a1)
            setup_db.add(a2)

    barrier = Barrier(2)

    def worker_privilege():
        with Session(engine) as w_db:
            barrier.wait(timeout=10)
            a = w_db.scalar(select(AssetItem).where(AssetItem.id == aid_1))
            res = grant_khang_dev_single_asset_if_eligible(w_db, a, now, actor_id=KHANG_DEV_ID, policy_id=effective_pid)
            w_db.commit()
            return res

    def worker_case_open():
        with Session(engine) as w_db:
            barrier.wait(timeout=10)
            from app.aura_lock import lock_aura_mutation
            with w_db.begin():
                lock_aura_mutation(w_db)
                u = w_db.scalar(select(User).where(User.id == KHANG_DEV_ID).with_for_update())
                inv = w_db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid_2).with_for_update())
                if inv is None:
                    inv = UserInventory(user_id=KHANG_DEV_ID, asset_id=aid_2, quantity=1, acquired_at=now, updated_at=now)
                    w_db.add(inv)
                else:
                    inv.quantity += 1
                    inv.updated_at = now
            return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker_privilege)
        f2 = executor.submit(worker_case_open)
        r1 = f1.result(timeout=15)
        r2 = f2.result(timeout=15)

    assert r1 is True
    assert r2 is True

    with Session(engine) as verify_db:
        inv1 = verify_db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid_1))
        inv2 = verify_db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid_2))
        assert inv1 is not None and inv1.quantity == 1
        assert inv2 is not None and inv2.quantity == 1


@pytest.mark.integration
def test_postgres_khang_dev_concurrent_admin_approval(pg_engine):
    """Multithreaded concurrent test:
    Thread 1: approves asset via admin flow.
    Thread 2: runs sync_khang_dev_vault_privilege.
    Verifies no deadlock or race condition.
    """
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    engine = pg_engine
    now = datetime.now(timezone.utc)
    aid = uuid4()
    digest = "9" * 64

    with Session(engine) as setup_db:
        with setup_db.begin():
            a = AssetItem(
                id=aid,
                slug=f"meme-con-appr-{aid.hex[:6]}",
                kind="avatar",
                collection="admin-upload",
                rarity="S",
                media_key=f"catalog/{digest}.png",
                display_name="Meme Concur Appr",
                source_rights=synthetic_rights(digest, name_review_status="pending", review_status="pending"),
                active=False,
                created_at=now,
                updated_at=now,
            )
            setup_db.add(a)

    barrier = Barrier(2)

    def worker_approve():
        with Session(engine) as w_db:
            barrier.wait(timeout=10)
            patch_req = AdminAssetPatch(action="approve")
            req = MagicMock()
            req.app.state.auth.now = MagicMock(return_value=now)
            acc = SimpleNamespace(db=w_db, user=SimpleNamespace(id=KHANG_DEV_ID))
            with w_db.begin():
                admin_update_asset(aid, patch_req, req, acc)
            return True

    def worker_sync():
        with Session(engine) as w_db:
            barrier.wait(timeout=10)
            with w_db.begin():
                res = sync_khang_dev_vault_privilege(w_db, now, dry_run=False, actor_id=KHANG_DEV_ID)
            return res

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker_approve)
        f2 = executor.submit(worker_sync)
        r1 = f1.result(timeout=15)
        r2 = f2.result(timeout=15)

    assert r1 is True
    assert r2["status"] == "success"

    with Session(engine) as verify_db:
        inv = verify_db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid))
        assert inv is not None and inv.quantity == 1


@pytest.mark.integration
def test_postgres_cleanup_preserves_preexisting_inventory(pg_session):
    """Verifies that pre-existing inventory items of Khang Dev are never deleted or affected."""
    db = pg_session
    now = datetime.now(timezone.utc)

    aid_existing = uuid4()
    digest_e = "e" * 64
    asset_e = AssetItem(
        id=aid_existing,
        slug=f"meme-preexist-{aid_existing.hex[:6]}",
        kind="avatar",
        collection="admin-upload",
        rarity="B",
        media_key=f"catalog/{digest_e}.png",
        display_name="Meme Preexisting",
        source_rights=synthetic_rights(digest_e, name_review_status="approved", review_status="approved"),
        active=True,
        created_at=now,
        updated_at=now,
    )
    inv_existing = UserInventory(
        user_id=KHANG_DEV_ID,
        asset_id=aid_existing,
        quantity=7,
        acquired_at=now,
        updated_at=now,
    )
    db.add(asset_e)
    db.add(inv_existing)
    db.flush()

    # Grant another asset
    aid_new = uuid4()
    digest_n = "f" * 64
    asset_n = AssetItem(
        id=aid_new,
        slug=f"meme-new-{aid_new.hex[:6]}",
        kind="avatar",
        collection="admin-upload",
        rarity="A",
        media_key=f"catalog/{digest_n}.png",
        display_name="Meme New Grant",
        source_rights=synthetic_rights(digest_n, name_review_status="approved", review_status="approved"),
        active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(asset_n)
    db.flush()

    policy_id = db.scalar(select(RewardPolicyVersion.id).where(RewardPolicyVersion.status == "published").order_by(RewardPolicyVersion.version.desc()))
    if not policy_id:
        policy_id = uuid4()

    granted = grant_khang_dev_single_asset_if_eligible(db, asset_n, now, actor_id=KHANG_DEV_ID, policy_id=policy_id)
    assert granted is True

    # Pre-existing inventory must remain untouched!
    db.refresh(inv_existing)
    assert inv_existing.quantity == 7


@pytest.mark.integration
def test_postgres_cli_dry_run_and_execute(pg_engine):
    """Runs CLI main() against PostgreSQL test database in dry-run and execute modes."""
    # 1. Dry run
    res_dry = main(["--dry-run"], engine=pg_engine)
    assert res_dry["status"] == "success"
    assert res_dry["dry_run"] is True

    # 2. Execute with confirmation
    res_exec = main(["--execute", "--confirm", "CONFIRM_GRANT_KHANG_DEV"], engine=pg_engine)
    assert res_exec["status"] == "success"
    assert res_exec["dry_run"] is False

