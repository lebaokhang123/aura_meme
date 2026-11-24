"""Targeted unit tests for Checkpoint 3: Khang Dev exclusive Vault privilege."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
from uuid import UUID, uuid4

import pytest

from app.admin_users import KHANG_DEV_ID, KIEN_DEV_ID
from app.models import AdminAuditLog, AssetItem, InventoryGrant, User, UserInventory
from app.vault_privilege import (
    PRIVILEGE_KEY_PREFIX,
    PRIVILEGE_SOURCE_TYPE,
    assert_khang_dev_target,
    auto_grant_khang_dev_published_items,
    sync_khang_dev_vault_privilege,
)


def make_mock_asset(
    kind: str = "avatar",
    rarity: str = "S",
    name_vi: str = "Meme Thần Thoại",
    review_status: str = "approved",
):
    asset_id = uuid4()
    asset = MagicMock(spec=AssetItem)
    asset.id = asset_id
    asset.slug = f"asset-{asset_id.hex[:8]}"
    asset.kind = kind
    asset.rarity = rarity
    asset.display_name = name_vi
    asset.active = True
    asset.source_rights = {
        "review_status": review_status,
        "name_review_status": review_status,
        "sha256": "a" * 64,
        "author": "AuraMeme Team",
    }
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
    """Newly published valid items are granted (1 unit) to Khang Dev with +0 EXP."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.username = "khang_dev"
    khang_user.status = "active"

    # User query returns khang_user; inventory queries return None (not owned); grant query returns None
    def mock_scalar(query, *args, **kwargs):
        query_str = str(query).lower()
        if "from users" in query_str:
            return khang_user
        if "from user_inventory" in query_str:
            return None
        if "from inventory_grants" in query_str:
            return None
        return None

    db.scalar.side_effect = mock_scalar

    item1 = MockManifestItem(kind="avatar", rarity="S")
    item2 = MockManifestItem(kind="background", rarity="A")
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
        assert grant.source_type == PRIVILEGE_SOURCE_TYPE
        assert grant.policy_id == policy_id
        assert grant.event_key.startswith(PRIVILEGE_KEY_PREFIX)

    audit_records = [obj for obj in added_objects if isinstance(obj, AdminAuditLog)]
    assert len(audit_records) == 1
    assert audit_records[0].action == "vault.privilege.auto_grant"
    assert audit_records[0].target_id == str(KHANG_DEV_ID)


def test_auto_grant_preserves_existing_quantity_when_already_owned():
    """Already owned items preserve their existing quantity and are not re-granted."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.status = "active"

    item1 = MockManifestItem(kind="avatar", rarity="S")
    existing_inv = MagicMock(spec=UserInventory)
    existing_inv.quantity = 5  # Already owned 5 units from previous drops/chests

    def mock_scalar(query, *args, **kwargs):
        query_str = str(query).lower()
        if "from users" in query_str:
            return khang_user
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


def test_sync_khang_dev_vault_privilege_dry_run():
    """Dry-run audits differences and reports missing items without writing to DB."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.username = "khang_dev"
    khang_user.status = "active"

    asset_owned = make_mock_asset(kind="avatar", rarity="C")
    asset_missing = make_mock_asset(kind="background", rarity="S")

    # DB execute returns rows from pool query
    mock_policy_id = uuid4()
    db.execute.return_value.all.return_value = [
        (asset_owned, mock_policy_id),
        (asset_missing, mock_policy_id),
    ]
    db.scalars.return_value = []

    def mock_scalar(query, *args, **kwargs):
        query_str = str(query).lower()
        if "from users" in query_str:
            return khang_user
        if "from user_inventory" in query_str:
            if str(asset_owned.id) in query_str or asset_owned.id in getattr(query, "compile", lambda: "")():
                inv = MagicMock(spec=UserInventory)
                inv.quantity = 2
                return inv
            # We can also check by parameter binding or match
            # Return inv for first asset, None for second
            return None
        return None

    # More specific query matcher for inventory
    def dynamic_scalar(query, *args, **kwargs):
        query_str = str(query).lower()
        if "from users" in query_str:
            return khang_user
        # Look up by call count or query
        return None

    # Let's set scalar return value for user, and side_effects for user_inventory
    inv_owned = MagicMock(spec=UserInventory)
    inv_owned.quantity = 3

    # 1st call: User check
    # 2nd call: UserInventory for asset_owned
    # 3rd call: UserInventory for asset_missing
    db.scalar.side_effect = [khang_user, inv_owned, None]

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
    db.execute.return_value.all.return_value = [(asset1, mock_policy_id)]
    db.scalars.return_value = []

    # 1: User check
    # 2: UserInventory check in loop -> None (missing)
    # 3: UserInventory check in execute branch -> None
    # 4: Existing InventoryGrant check -> None
    db.scalar.side_effect = [khang_user, None, None, None]

    now = datetime.now(timezone.utc)
    report = sync_khang_dev_vault_privilege(db, now, dry_run=False)

    assert report["status"] == "success"
    assert report["dry_run"] is False
    assert report["published_count"] == 1
    assert report["already_owned_count"] == 0
    assert report["missing_count"] == 1
    assert report["granted_count"] == 1

    # Objects added: UserInventory, InventoryGrant, AdminAuditLog
    added = [call_args[0][0] for call_args in db.add.call_args_list]
    inv_objs = [o for o in added if isinstance(o, UserInventory)]
    grant_objs = [o for o in added if isinstance(o, InventoryGrant)]
    audit_objs = [o for o in added if isinstance(o, AdminAuditLog)]

    assert len(inv_objs) == 1
    assert inv_objs[0].quantity == 1
    assert len(grant_objs) == 1
    assert grant_objs[0].quantity == 1
    assert grant_objs[0].source_type == PRIVILEGE_SOURCE_TYPE
    assert len(audit_objs) == 1
    assert audit_objs[0].action == "vault.privilege.sync"


def test_zero_exp_rule_preserved():
    """Vault privilege grants NEVER emit AuraLedger entries or modify user EXP."""
    db = MagicMock()
    khang_user = MagicMock(spec=User)
    khang_user.id = KHANG_DEV_ID
    khang_user.status = "active"
    db.scalar.side_effect = [khang_user, None, None, None]

    asset1 = make_mock_asset(kind="avatar", rarity="S")
    db.execute.return_value.all.return_value = [(asset1, uuid4())]
    db.scalars.return_value = []

    now = datetime.now(timezone.utc)
    sync_khang_dev_vault_privilege(db, now, dry_run=False)

    added = [call_args[0][0] for call_args in db.add.call_args_list]
    # No AuraLedger or WalletTransaction added
    from app.models import AuraLedger, WalletTransaction
    ledger_entries = [o for o in added if isinstance(o, (AuraLedger, WalletTransaction))]
    assert ledger_entries == []
