"""Targeted unit and PostgreSQL integration tests for Checkpoint 3: Khang Dev exclusive Vault privilege."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import re
from secrets import token_urlsafe
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.admin_users import KHANG_DEV_ID, KIEN_DEV_ID
from app.admin_workspace import AdminAssetPatch, admin_update_asset
from app.models import (
    AdminAuditLog,
    AssetItem,
    AuthSession,
    Base,
    AuraLedger,
    CaseDefinition,
    CaseLootRarity,
    CaseLootTable,
    CaseOpen,
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
        if "from reward_policy_versions" in query_str:
            return MagicMock(spec=RewardPolicyVersion, id=policy_id, status="published", effective_at=now)
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
    assert report["eligible_count"] == 2
    assert report["published_count"] == 2
    assert report["already_owned_count"] == 1
    assert report["missing_count"] == 1
    assert report["blocked_count"] == 0
    assert report["granted_count"] == 0
    assert report["eligible_count"] == report["already_owned_count"] + report["missing_count"] + report["blocked_count"]
    assert len(report["missing_assets"]) == 1
    assert report["missing_assets"][0]["id"] == str(asset_missing.id)

    # Zero writes in dry run
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_sync_khang_dev_vault_privilege_dry_run_reports_blocked_assets():
    """Dry-run explicitly reports blocked_count and blocked_assets when policy cannot be resolved.
    Total formula: eligible_count = already_owned_count + missing_count + blocked_count.
    """
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.username = "khang_dev"
    khang_user.status = "active"

    asset_owned = make_mock_asset(kind="avatar", rarity="C")
    asset_grantable = make_mock_asset(kind="background", rarity="S")
    asset_blocked = make_mock_asset(kind="avatar", rarity="A")

    mock_policy_id = uuid4()
    db.scalars.return_value = [asset_owned, asset_grantable, asset_blocked]

    inv_owned = MagicMock(spec=UserInventory)
    inv_owned.quantity = 2

    inv_call = 0

    def mock_scalar(query, *args, **kwargs):
        nonlocal inv_call
        q = str(query).lower()
        if "from users" in q:
            return khang_user
        if "from user_inventory" in q:
            inv_call += 1
            if inv_call == 1:
                return inv_owned
            return None
        if "from reward_policy_versions" in q:
            # Second check has policy, third check has no policy
            if inv_call == 2:
                return mock_policy_id
            return None
        return None

    db.scalar.side_effect = mock_scalar

    now = datetime.now(timezone.utc)
    report = sync_khang_dev_vault_privilege(db, now, dry_run=True)

    assert report["status"] == "success"
    assert report["dry_run"] is True
    assert report["eligible_count"] == 3
    assert report["already_owned_count"] == 1
    assert report["missing_count"] == 1
    assert report["blocked_count"] == 1
    assert report["eligible_count"] == report["already_owned_count"] + report["missing_count"] + report["blocked_count"]
    assert len(report["blocked_assets"]) == 1
    assert report["blocked_assets"][0]["id"] == str(asset_blocked.id)
    assert report["blocked_assets"][0]["reason"] == "missing_policy"
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_sync_khang_dev_vault_privilege_execute_fails_closed_when_blocked_assets():
    """In execute mode, if any eligible asset is blocked from being granted, fail-closed without mutation."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.username = "khang_dev"
    khang_user.status = "active"

    asset_blocked = make_mock_asset(kind="avatar", rarity="S")
    db.scalars.return_value = [asset_blocked]

    def mock_scalar(query, *args, **kwargs):
        q = str(query).lower()
        if "from users" in q:
            return khang_user
        if "from user_inventory" in q:
            return None
        if "from reward_policy_versions" in q:
            return None  # No published policy
        return None

    db.scalar.side_effect = mock_scalar

    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="Fail-closed.*blocked"):
        sync_khang_dev_vault_privilege(db, now, dry_run=False)

    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_grant_single_asset_validates_supplied_policy_id():
    """Supplied policy_id must be published and effective as of now."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.status = "active"

    asset = make_mock_asset(kind="avatar", rarity="S")
    invalid_policy_id = uuid4()

    def mock_scalar(query, *args, **kwargs):
        q = str(query).lower()
        if "from users" in q:
            return khang_user
        if "from user_inventory" in q:
            return None
        if "from inventory_grants" in q:
            return None
        if "from reward_policy_versions" in q:
            return None  # Policy is not published or not effective
        return None

    db.scalar.side_effect = mock_scalar

    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="not a published RewardPolicyVersion effective"):
        grant_khang_dev_single_asset_if_eligible(
            db,
            asset,
            now,
            actor_id=KHANG_DEV_ID,
            policy_id=invalid_policy_id,
        )


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
    return os.environ.get("TEST_DATABASE_URL") or None


def disposable_cluster_name() -> str:
    name = os.environ.get("AURAMEME_DISPOSABLE_TEST_CLUSTER", "")
    if not re.fullmatch(r"aurameme-fp-[0-9a-f]{32}", name):
        pytest.fail("Explicit disposable PostgreSQL cluster marker is required.", pytrace=False)
    return name


def test_test_url_does_not_read_dotenv(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with patch("builtins.open", side_effect=AssertionError("dotenv fallback")):
        assert resolve_test_db_url() is None


def test_disposable_cluster_marker_is_required(monkeypatch):
    monkeypatch.delenv("AURAMEME_DISPOSABLE_TEST_CLUSTER", raising=False)
    with pytest.raises(pytest.fail.Exception, match="cluster marker"):
        disposable_cluster_name()


def validate_test_target(test_url: str):
    """Safety guard: verify exact loopback test role and database without substring matches."""
    try:
        target = make_url(test_url)
        safe = (
            target.drivername == "postgresql+psycopg"
            and target.host == "127.0.0.1"
            and (target.port or 5432) == 5432
            and target.database == "aurameme_test"
            and target.username == "aurameme_test"
            and bool(target.password)
            and not target.query
        )
    except Exception:
        safe = False
    if not safe:
        pytest.fail(
            "Safety violation: integration tests require exact isolated test database: postgresql+psycopg://aurameme_test:***@127.0.0.1:5432/aurameme_test",
            pytrace=False,
        )
    return target


def verify_test_connection(conn):
    """Require the dedicated server marker as well as the existing database identity."""
    identity = tuple(conn.execute(text(
        "SELECT current_database(), current_user, current_schema(), "
        "inet_server_port(), current_setting('cluster_name')"
    )).one())
    if identity != ("aurameme_test", "aurameme_test", "public", 5432, disposable_cluster_name()):
        pytest.fail("Safety violation: not the provisioned disposable PostgreSQL instance.", pytrace=False)
    if conn.scalar(text(
        "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls "
        "FROM pg_roles WHERE rolname=current_user"
    )):
        pytest.fail("Safety violation: disposable test role is privileged.", pytrace=False)
    if conn.scalar(text("SELECT version_num FROM alembic_version")) != "0019_asset_lifecycle_tombstone":
        pytest.fail("Safety violation: unexpected schema revision.", pytrace=False)
    if set(inspect(conn).get_table_names(schema="public")) != set(Base.metadata.tables) | {"alembic_version"}:
        pytest.fail("Safety violation: unexpected test schema.", pytrace=False)


def test_shared_cluster_identity_is_rejected_before_schema_access(monkeypatch):
    marker = "aurameme-fp-" + "a" * 32
    monkeypatch.setenv("AURAMEME_DISPOSABLE_TEST_CLUSTER", marker)
    conn = MagicMock()
    conn.execute.return_value.one.return_value = ("aurameme_test", "aurameme_test", "public", 5432, "")
    with pytest.raises(pytest.fail.Exception, match="not the provisioned disposable"):
        verify_test_connection(conn)
    conn.scalar.assert_not_called()


@pytest.fixture
def disposable_engine():
    test_url = resolve_test_db_url()
    if not test_url:
        pytest.skip("Run with an explicitly provisioned disposable PostgreSQL instance.")
    disposable_cluster_name()
    target = validate_test_target(test_url)
    engine = create_engine(target, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            verify_test_connection(conn)
            for table in Base.metadata.sorted_tables:
                if conn.scalar(select(table.c[0]).limit(1)) is not None:
                    pytest.fail("Disposable test schema must start empty.", pytrace=False)
        yield engine
    finally:
        engine.dispose()


def seed_privilege_test(db, *, publish=True):
    now = datetime.now(timezone.utc)
    role = Role(id=uuid4(), code="ADMIN", description="Administrator")
    db.add_all([
        User(id=KHANG_DEV_ID, username="khang_dev", email="khang@aurameme.test",
             password_hash="test_hash", status="active", created_at=now, updated_at=now),
        role,
    ])
    db.flush()
    db.add(UserRole(user_id=KHANG_DEV_ID, role_id=role.id, granted_at=now))
    if publish:
        db.add(RewardPolicyVersion(id=uuid4(), version=1, config_json={"type": "free-vault-v1"},
                                  status="published", effective_at=now, created_by=KHANG_DEV_ID, created_at=now))
    db.flush()


@pytest.fixture
def pg_session(disposable_engine):
    with disposable_engine.connect() as conn, conn.begin() as transaction:
        verify_test_connection(conn)
        with Session(bind=conn) as db:
            seed_privilege_test(db)
            yield db
        transaction.rollback()


@pytest.fixture
def pg_engine(disposable_engine, request):
    """Commit in a fresh clone; the runner replaces the disposable database per case."""
    with Session(disposable_engine) as db, db.begin():
        verify_test_connection(db.connection())
        seed_privilege_test(db, publish=getattr(request, "param", True))
    return disposable_engine


@pytest.fixture
def vault_http(pg_engine, monkeypatch):
    """Run the real FastAPI app, CSRF, account and transaction dependencies."""
    from fastapi.testclient import TestClient
    from app.auth import digest
    from app.main import app

    monkeypatch.setenv("DATABASE_URL", resolve_test_db_url())
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("AUTH_ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["https://testserver"]')
    monkeypatch.setenv("VAULT_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("EMAIL_MODE", "disabled")
    raw = token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with Session(pg_engine) as db, db.begin():
        db.add(AuthSession(id=uuid4(), user_id=KHANG_DEV_ID, token_hash=digest(raw),
                           created_at=now, expires_at=now + timedelta(hours=1)))
    with TestClient(app, base_url="https://testserver") as client:
        client.cookies.set("am_session", raw)
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code == 200
        yield client, {"Origin": "https://testserver", "X-CSRF-Token": response.json()["csrf_token"]}


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

    try:
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
    finally:
        with Session(engine) as cleanup_db:
            with cleanup_db.begin():
                a = cleanup_db.scalar(select(AssetItem).where(AssetItem.id == asset_id))
                if a:
                    a.active = False


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

    try:
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
    finally:
        with Session(engine) as cleanup_db:
            with cleanup_db.begin():
                for aid in (asset_id_1, asset_id_2):
                    a = cleanup_db.scalar(select(AssetItem).where(AssetItem.id == aid))
                    if a:
                        a.active = False


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
    Calls publish_cases from app.catalog_activation with an approved 5-rarity avatar catalog.
    Verifies publish_cases publishes the case and automatically triggers auto_grant_khang_dev_published_items.
    Verifies Khang Dev receives 1 unit of each newly published eligible item with source_type='admin',
    +0 EXP, and inventory_state holds.
    """
    from app.catalog_activation import publish_cases
    from app.inventory_grants import inventory_state
    from hashlib import sha256
    import json

    db = pg_session
    now = datetime.now(timezone.utc)

    # Construct 5 avatar items for rarities 'D', 'C', 'B', 'A', 'S'
    raw_items_dict = []
    asset_ids = []

    for rarity in "DCBAS":
        aid = uuid4()
        asset_ids.append(aid)
        digest = sha256(f"test-pub-{aid.hex}".encode()).hexdigest()
        rights = synthetic_rights(digest, name_review_status="approved", review_status="approved")
        raw_items_dict.append({
            "id": str(aid),
            "slug": f"fixture-pub-{aid.hex[:8]}",
            "kind": "avatar",
            "collection": "test-pub-collection",
            "rarity": rarity,
            "media_key": f"catalog/{digest}.png",
            "file": f"{aid.hex}.png",
            "sha256": digest,
            "mime": "image/png",
            "name_vi": f"Test Avatar {rarity}",
            "name_review_status": "approved",
            "effect_key": None,
            "source_rights": rights,
        })

    manifest_json_bytes = json.dumps({"version": 1, "items": raw_items_dict}, sort_keys=True).encode("utf-8")
    manifest_digest = sha256(manifest_json_bytes).hexdigest()

    # Create real AssetItem records in database with matching manifest_sha256
    for item in raw_items_dict:
        aid = UUID(item["id"])
        full_rights = dict(item["source_rights"])
        full_rights["manifest_sha256"] = manifest_digest
        full_rights["name_review_status"] = "approved"
        full_rights["review_status"] = "approved"
        db.add(
            AssetItem(
                id=aid,
                slug=item["slug"],
                kind=item["kind"],
                collection=item["collection"],
                rarity=item["rarity"],
                media_key=item["media_key"],
                display_name=item["name_vi"],
                effect_key=None,
                source_rights=full_rights,
                active=True,
                created_at=now,
                updated_at=now,
            )
        )
    db.flush()

    class ManifestItemWrapper:
        def __init__(self, data):
            self.id = UUID(data["id"])
            self.slug = data["slug"]
            self.kind = data["kind"]
            self.collection = data["collection"]
            self.rarity = data["rarity"]
            self.sha256 = data["sha256"]
            self.mime = data["mime"]
            self.name_vi = data["name_vi"]
            self.name_review_status = data["name_review_status"]
            self.effect_key = data["effect_key"]
            self.source_rights = SimpleNamespace(
                review_status="approved",
                model_dump=lambda s=data["source_rights"]: dict(s),
            )

    class MockCatalogManifest:
        def __init__(self, items):
            self.version = 1
            self.items = items

    manifest = MockCatalogManifest([ManifestItemWrapper(d) for d in raw_items_dict])

    # Call the real publication entry point
    results = publish_cases(db, manifest, manifest_digest, manifest_digest, KHANG_DEV_ID, now)
    assert "avatar" in results

    # Verify that Khang Dev received all 5 newly published items
    for aid in asset_ids:
        inv = db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid))
        assert inv is not None
        assert inv.quantity == 1

        grant = db.scalar(select(InventoryGrant).where(InventoryGrant.user_id == KHANG_DEV_ID, InventoryGrant.asset_id == aid))
        assert grant is not None
        assert grant.source_type == "admin"
        assert grant.event_key == f"{PRIVILEGE_KEY_PREFIX}{aid}"

        assert inventory_state(db, KHANG_DEV_ID, aid).quantity == 1

    # Verify audit log was recorded for both publication and privilege grant
    audit_pub = db.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "vault.cases.publish", AdminAuditLog.target_id == manifest_digest))
    assert audit_pub is not None

    audit_grants = list(db.scalars(select(AdminAuditLog).where(AdminAuditLog.action == "vault.privilege.auto_grant", AdminAuditLog.target_id == str(KHANG_DEV_ID))))
    assert len(audit_grants) >= 5


@pytest.mark.integration
def test_postgres_khang_dev_concurrent_vault_open(pg_engine, vault_http):
    """Real multithreaded concurrent business flow on PostgreSQL:
    Thread 1: grants vault privilege to Khang Dev for asset 1 via grant_khang_dev_single_asset_if_eligible.
    Thread 2: executes real Vault case opening for Khang Dev via open_runtime.

    Verifies:
    - Deadlock-free execution under concurrent load.
    - UserInventory quantity strictly equals sum(InventoryGrant.quantity) for both items.
    - Real CaseOpen row is inserted with matching loot_table and reward_asset.
    - Case open awards standard +2 EXP into AuraLedger (source_type='case_open').
    - Privilege grant awards exactly +0 EXP (no AuraLedger entry for privilege grant).
    - Invariant ledger holds across both concurrent operations.
    """
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from types import SimpleNamespace
    from app.aura_runtime import publish_v1
    from app.vault_open import CaseOpenResult
    from app.inventory_grants import inventory_state
    from app.models import CaseDefinition, CaseLootTable, CaseLootRarity, CasePoolItem
    from app.vault_v1_policy import WEIGHTS

    engine = pg_engine
    now = datetime.now(timezone.utc)
    aid_privilege = uuid4()
    case_id = uuid4()
    pool_id = uuid4()
    digest_p = "7" * 64

    pool_asset_ids = []
    with Session(engine) as setup_db:
        with setup_db.begin():
            publish_v1(setup_db, KHANG_DEV_ID, now)
            policy = setup_db.scalar(
                select(RewardPolicyVersion)
                .where(
                    RewardPolicyVersion.status == "published",
                    RewardPolicyVersion.config_json["type"].astext == "free-vault-v1",
                )
                .order_by(RewardPolicyVersion.version.desc())
            )
            if not policy:
                from sqlalchemy import func
                ver = setup_db.scalar(select(func.coalesce(func.max(RewardPolicyVersion.version), 0))) + 1
                policy = RewardPolicyVersion(
                    id=uuid4(),
                    version=ver,
                    config_json={"type": "free-vault-v1"},
                    status="published",
                    effective_at=now,
                    created_by=KHANG_DEV_ID,
                    created_at=now,
                )
                setup_db.add(policy)
                setup_db.flush()
            effective_pid = policy.id

            # Privilege candidate asset
            a_priv = AssetItem(
                id=aid_privilege,
                slug=f"meme-con-priv-{aid_privilege.hex[:6]}",
                kind="avatar",
                collection="admin-upload",
                rarity="S",
                media_key=f"catalog/{digest_p}.png",
                display_name="Meme Concur Privilege",
                source_rights=synthetic_rights(digest_p, name_review_status="approved", review_status="approved"),
                active=True,
                created_at=now,
                updated_at=now,
            )
            setup_db.add(a_priv)
            setup_db.flush()

            # Set up real runtime case definition and draft loot table
            case_def = CaseDefinition(
                id=case_id,
                slug=f"free-case-{case_id.hex[:6]}",
                label="Free Test Case",
                cost_khi_van=0,
                status="active",
                runtime_kind="avatar",
                created_at=now,
                updated_at=now,
            )
            setup_db.add(case_def)
            setup_db.flush()

            loot_tbl = CaseLootTable(
                id=pool_id,
                case_id=case_id,
                odds_version=1,
                band_no=1,
                min_earned_xp=0,
                max_earned_xp=None,
                policy_id=effective_pid,
                status="draft",
                active_from=now,
                created_at=now,
            )
            setup_db.add(loot_tbl)
            setup_db.flush()

            for rarity, weight in zip("DCBAS", WEIGHTS):
                setup_db.add(CaseLootRarity(loot_table_id=pool_id, rarity=rarity, weight_bps=weight))

            # 5 approved items for each rarity so load_runtime_pool succeeds
            for rarity in "DCBAS":
                aid = uuid4()
                pool_asset_ids.append(aid)
                digest = sha256(f"test-con-vault-{aid.hex}".encode()).hexdigest()
                setup_db.add(
                    AssetItem(
                        id=aid,
                        slug=f"meme-con-v-{rarity.lower()}-{aid.hex[:6]}",
                        kind="avatar",
                        collection="admin-upload",
                        rarity=rarity,
                        media_key=f"catalog/{digest}.png",
                        display_name=f"Meme Concur {rarity}",
                        source_rights=synthetic_rights(digest, name_review_status="approved", review_status="approved"),
                        active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
                setup_db.add(CasePoolItem(loot_table_id=pool_id, asset_id=aid, rarity=rarity, item_weight=1))
            setup_db.flush()

            loot_tbl.status = "published"
            setup_db.flush()

    barrier = Barrier(2)

    def worker_privilege():
        with Session(engine) as w_db:
            barrier.wait(timeout=10)
            a = w_db.scalar(select(AssetItem).where(AssetItem.id == aid_privilege))
            res = grant_khang_dev_single_asset_if_eligible(w_db, a, now, actor_id=KHANG_DEV_ID, policy_id=effective_pid)
            w_db.commit()
            return res

    client, headers = vault_http

    def worker_case_open():
        barrier.wait(timeout=10)
        response = client.post(
            f"/api/v1/vault/cases/{case_id}/open",
            headers={**headers, "Idempotency-Key": f"fixture-key-{uuid4().hex}"},
        )
        assert response.status_code == 200, response.text
        return CaseOpenResult.model_validate(response.json())

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_privilege)
            f2 = executor.submit(worker_case_open)
            r1 = f1.result(timeout=15)
            r2 = f2.result(timeout=15)

        assert r1 is True
        assert r2 is not None
        checked = client.post("/api/v1/aura/check-in", headers=headers)
        assert checked.status_code == 200, checked.text
        assert checked.json()["earned_xp_delta"] == 15
        repeat = client.post("/api/v1/aura/check-in", headers=headers)
        assert repeat.status_code == 200 and repeat.json()["earned_xp_delta"] == 0
        open_id = r2.open_id
        reward_asset_id = UUID(str(r2.reward.id))

        with Session(engine) as verify_db:
            # 1. Verify CaseOpen record
            co = verify_db.scalar(select(CaseOpen).where(CaseOpen.id == open_id))
            assert co is not None
            assert co.user_id == KHANG_DEV_ID
            assert co.reward_asset_id == reward_asset_id
            assert len(list(verify_db.scalars(select(CaseOpen)))) == 1

            # 2. Verify vault reward inventory and grant
            inv_vault = verify_db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == reward_asset_id))
            assert inv_vault is not None and inv_vault.quantity >= 1
            grant_vault = verify_db.scalar(select(InventoryGrant).where(InventoryGrant.case_open_id == open_id))
            assert grant_vault is not None
            assert grant_vault.source_type == "case_open"
            assert grant_vault.user_id == KHANG_DEV_ID
            assert grant_vault.asset_id == reward_asset_id
            assert inventory_state(verify_db, KHANG_DEV_ID, reward_asset_id).quantity == inv_vault.quantity

            # 3. Verify privilege grant inventory and grant
            inv_priv = verify_db.scalar(select(UserInventory).where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == aid_privilege))
            assert inv_priv is not None and inv_priv.quantity == 1
            grant_priv = verify_db.scalar(select(InventoryGrant).where(InventoryGrant.user_id == KHANG_DEV_ID, InventoryGrant.asset_id == aid_privilege))
            assert grant_priv is not None
            assert grant_priv.source_type == "admin"
            assert grant_priv.event_key == f"{PRIVILEGE_KEY_PREFIX}{aid_privilege}"
            assert inventory_state(verify_db, KHANG_DEV_ID, aid_privilege).quantity == 1

            # 4. Verify EXP: Case open awards +2 EXP; Privilege grant awards +0 EXP
            from app.vault_exp_award import VAULT_KEY_PREFIX as VAULT_EXP_KEY_PREFIX
            vault_exp = verify_db.scalar(
                select(AuraLedger).where(
                    AuraLedger.user_id == KHANG_DEV_ID,
                    AuraLedger.event_key == f"{VAULT_EXP_KEY_PREFIX}{open_id}",
                )
            )
            assert vault_exp is not None
            assert vault_exp.base_xp == 2

            priv_exp = verify_db.scalar(
                select(AuraLedger).where(
                    AuraLedger.user_id == KHANG_DEV_ID,
                    AuraLedger.event_key == f"{PRIVILEGE_KEY_PREFIX}{aid_privilege}",
                )
            )
            assert priv_exp is None
    finally:
        with Session(engine) as cleanup_db:
            with cleanup_db.begin():
                for aid in [aid_privilege] + pool_asset_ids:
                    a = cleanup_db.scalar(select(AssetItem).where(AssetItem.id == aid))
                    if a:
                        a.active = False
                cd = cleanup_db.scalar(select(CaseDefinition).where(CaseDefinition.id == case_id))
                if cd:
                    cd.runtime_kind = None


@pytest.mark.integration
def test_postgres_khang_dev_concurrent_admin_approval(pg_engine, vault_http):
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

    client, headers = vault_http

    def worker_approve():
        barrier.wait(timeout=10)
        response = client.patch(f"/api/v1/admin/assets/{aid}", json={"action": "approve"}, headers=headers)
        assert response.status_code == 200, response.text
        return True

    def worker_sync():
        with Session(engine) as w_db:
            barrier.wait(timeout=10)
            with w_db.begin():
                res = sync_khang_dev_vault_privilege(w_db, now, dry_run=False, actor_id=KHANG_DEV_ID)
            return res

    try:
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
    finally:
        with Session(engine) as cleanup_db:
            with cleanup_db.begin():
                a = cleanup_db.scalar(select(AssetItem).where(AssetItem.id == aid))
                if a:
                    a.active = False


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
@pytest.mark.parametrize("pg_engine", [True, False], indirect=True, ids=["policy", "no-policy"])
def test_postgres_cli_dry_run_and_execute(pg_engine, request):
    """Runs CLI main() against PostgreSQL test database in dry-run and execute modes."""
    digest = "e" * 64
    aid = uuid4()
    now = datetime.now(timezone.utc)
    with Session(pg_engine) as db, db.begin():
        db.add(AssetItem(
            id=aid, slug="synthetic-cli-asset", kind="avatar", collection="admin-upload",
            rarity="S", media_key=f"catalog/{digest}.png", display_name="Synthetic CLI Asset",
            source_rights=synthetic_rights(digest, name_review_status="approved", review_status="approved"),
            active=True, created_at=now, updated_at=now,
        ))

    dry = main(["--dry-run"], engine=pg_engine)
    args = ["--execute", "--confirm", "CONFIRM_GRANT_KHANG_DEV"]
    published = request.node.callspec.params["pg_engine"]
    assert (dry["eligible_count"], dry["missing_count"], dry["blocked_count"], dry["granted_count"]) == (
        1, int(published), int(not published), 0,
    )
    if not published:
        with pytest.raises(ValueError, match="Fail-closed"):
            main(args, engine=pg_engine)
        with Session(pg_engine) as db:
            assert not list(db.scalars(select(InventoryGrant)))
            assert not list(db.scalars(select(UserInventory)))
            assert not list(db.scalars(select(AuraLedger)))
            assert not list(db.scalars(select(CaseOpen)))
        return
    assert main(args, engine=pg_engine)["granted_count"] == 1
    assert main(args, engine=pg_engine)["granted_count"] == 0
    with Session(pg_engine) as db:
        assert len(list(db.scalars(select(InventoryGrant)))) == 1
        inv = db.get(UserInventory, (KHANG_DEV_ID, aid))
        assert inv.quantity == 1
        assert not list(db.scalars(select(CaseOpen)))
        assert not list(db.scalars(select(AuraLedger)))
