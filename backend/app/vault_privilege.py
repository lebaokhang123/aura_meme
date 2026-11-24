"""Exclusive Vault privilege grants for Khang Dev; strictly idempotent and zero-EXP."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.admin_users import KHANG_DEV_ID, KIEN_DEV_ID
from app.catalog_rights import reviewed_source_rights, reviewed_source_rights_sql
from app.inventory import ready_asset
from app.inventory_grants import inventory_state
from app.models import (
    AdminAuditLog,
    AssetItem,
    CaseLootTable,
    CasePoolItem,
    InventoryGrant,
    User,
    UserInventory,
)

PRIVILEGE_SOURCE_TYPE = "privilege"
PRIVILEGE_KEY_PREFIX = "privilege:khang_dev:"


def assert_khang_dev_target(target_user_id: UUID) -> None:
    """Strictly ensure the target is Khang Dev and never Kien Dev or any other user."""
    if target_user_id != KHANG_DEV_ID:
        raise ValueError(
            f"Vault privilege is strictly exclusive to Khang Dev ({KHANG_DEV_ID}); "
            f"forbidden for user {target_user_id}."
        )


def auto_grant_khang_dev_published_items(
    db: Session,
    manifest,
    policy_id: UUID,
    now: datetime,
    *,
    actor_id: UUID = KHANG_DEV_ID,
) -> list[UUID]:
    """Automatically grant newly published items to Khang Dev during publication.

    - Strictly idempotent: 1 unit if not owned; preserves existing quantity if already owned.
    - +0 EXP, no fake chest openings, no wallet transactions.
    - Skips cleanly if Khang Dev does not exist in the database (e.g. synthetic publication test).
    """
    khang = db.scalar(
        select(User)
        .where(User.id == KHANG_DEV_ID, User.status == "active")
        .with_for_update()
    )
    if khang is None:
        return []

    granted: list[UUID] = []
    for item in manifest.items:
        if item.kind not in ("avatar", "background"):
            continue
        if getattr(item, "name_review_status", None) != "approved":
            continue
        source_rights = getattr(item, "source_rights", None)
        if hasattr(source_rights, "review_status") and source_rights.review_status != "approved":
            continue

        item_id = UUID(str(item.id)) if isinstance(item.id, str) else item.id

        # Lock inventory row
        user_inv = db.scalar(
            select(UserInventory)
            .where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == item_id)
            .with_for_update()
        )
        if user_inv is not None and user_inv.quantity > 0:
            # Already owned: preserve existing quantity without changes
            continue

        event_key = f"{PRIVILEGE_KEY_PREFIX}{item_id}"
        existing_grant = db.scalar(
            select(InventoryGrant).where(
                InventoryGrant.user_id == KHANG_DEV_ID,
                InventoryGrant.event_key == event_key,
            )
        )
        if existing_grant is not None:
            # Grant record already exists, ensure inventory cache matches
            inventory_state(db, KHANG_DEV_ID, item_id)
            continue

        # Grant 1 unit
        if user_inv is None:
            user_inv = UserInventory(
                user_id=KHANG_DEV_ID,
                asset_id=item_id,
                quantity=1,
                acquired_at=now,
                updated_at=now,
            )
            db.add(user_inv)
        else:
            user_inv.quantity = 1
            user_inv.updated_at = now
        db.flush()

        grant = InventoryGrant(
            id=uuid4(),
            user_id=KHANG_DEV_ID,
            asset_id=item_id,
            event_key=event_key,
            quantity=1,
            source_type=PRIVILEGE_SOURCE_TYPE,
            case_open_id=None,
            policy_id=policy_id,
            granted_at=now,
        )
        db.add(grant)
        db.flush()
        granted.append(item_id)

    if granted:
        db.add(
            AdminAuditLog(
                id=uuid4(),
                actor_id=actor_id,
                action="vault.privilege.auto_grant",
                target_type="user_inventory",
                target_id=str(KHANG_DEV_ID),
                before_json=None,
                after_json={
                    "granted_assets": [str(gid) for gid in granted],
                    "policy_id": str(policy_id),
                    "source": "publication_hook",
                },
                created_at=now,
            )
        )
        db.flush()

    return granted


def sync_khang_dev_vault_privilege(
    db: Session,
    now: datetime,
    *,
    dry_run: bool = True,
    actor_id: UUID = KHANG_DEV_ID,
    target_user_id: UUID = KHANG_DEV_ID,
) -> dict:
    """Audit or backfill all currently published Vault items for Khang Dev.

    - Target is strictly validated to be Khang Dev.
    - Dry-run mode reports differences without mutating database state.
    - Idempotent: missing items receive 1 unit, existing items keep their current quantity.
    """
    assert_khang_dev_target(target_user_id)

    khang = db.scalar(
        select(User)
        .where(User.id == KHANG_DEV_ID, User.status == "active")
        .with_for_update()
    )
    if khang is None:
        return {
            "status": "user_not_found",
            "target_user_id": str(KHANG_DEV_ID),
            "dry_run": dry_run,
            "message": "Khang Dev account not found or not active in this database.",
            "published_count": 0,
            "already_owned_count": 0,
            "missing_count": 0,
            "granted_count": 0,
            "missing_assets": [],
            "already_owned": [],
        }

    # Query published assets from published loot tables
    pool_query = (
        select(AssetItem, CaseLootTable.policy_id)
        .join(CasePoolItem, CasePoolItem.asset_id == AssetItem.id)
        .join(CaseLootTable, CaseLootTable.id == CasePoolItem.loot_table_id)
        .where(
            CaseLootTable.status == "published",
            AssetItem.active.is_(True),
            reviewed_source_rights_sql(AssetItem.source_rights),
            AssetItem.kind.in_(("avatar", "background")),
        )
        .distinct()
        .order_by(AssetItem.kind, AssetItem.rarity, AssetItem.slug)
    )
    rows = list(db.execute(pool_query).all())

    # If no loot tables exist yet, also inspect approved active catalog assets
    seen_ids = {asset.id for asset, _ in rows}
    fallback_query = select(AssetItem).where(
        AssetItem.active.is_(True),
        reviewed_source_rights_sql(AssetItem.source_rights),
        AssetItem.kind.in_(("avatar", "background")),
    ).order_by(AssetItem.kind, AssetItem.rarity, AssetItem.slug)
    for asset in db.scalars(fallback_query):
        if asset.id not in seen_ids and ready_asset(asset):
            if asset.source_rights.get("name_review_status") == "approved":
                rows.append((asset, None))
                seen_ids.add(asset.id)

    already_owned = []
    missing = []

    for asset, policy_id in rows:
        user_inv = db.scalar(
            select(UserInventory)
            .where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == asset.id)
            .with_for_update()
        )
        if user_inv is not None and user_inv.quantity > 0:
            already_owned.append({
                "id": str(asset.id),
                "slug": asset.slug,
                "kind": asset.kind,
                "rarity": asset.rarity,
                "quantity": user_inv.quantity,
            })
        else:
            missing.append((asset, policy_id))

    granted = []
    if not dry_run and missing:
        for asset, policy_id in missing:
            event_key = f"{PRIVILEGE_KEY_PREFIX}{asset.id}"
            user_inv = db.scalar(
                select(UserInventory)
                .where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == asset.id)
                .with_for_update()
            )
            existing_grant = db.scalar(
                select(InventoryGrant).where(
                    InventoryGrant.user_id == KHANG_DEV_ID,
                    InventoryGrant.event_key == event_key,
                )
            )
            if existing_grant is not None:
                inventory_state(db, KHANG_DEV_ID, asset.id)
                continue

            if user_inv is None:
                user_inv = UserInventory(
                    user_id=KHANG_DEV_ID,
                    asset_id=asset.id,
                    quantity=1,
                    acquired_at=now,
                    updated_at=now,
                )
                db.add(user_inv)
            else:
                user_inv.quantity = 1
                user_inv.updated_at = now
            db.flush()

            grant = InventoryGrant(
                id=uuid4(),
                user_id=KHANG_DEV_ID,
                asset_id=asset.id,
                event_key=event_key,
                quantity=1,
                source_type=PRIVILEGE_SOURCE_TYPE,
                case_open_id=None,
                policy_id=policy_id,
                granted_at=now,
            )
            db.add(grant)
            db.flush()
            granted.append(str(asset.id))

        db.add(
            AdminAuditLog(
                id=uuid4(),
                actor_id=actor_id,
                action="vault.privilege.sync",
                target_type="user_inventory",
                target_id=str(KHANG_DEV_ID),
                before_json={"missing_count": len(missing)},
                after_json={
                    "granted_assets": granted,
                    "target_username": khang.username,
                    "source": "sync_tool",
                },
                created_at=now,
            )
        )
        db.flush()

    return {
        "status": "success",
        "dry_run": dry_run,
        "target_user_id": str(KHANG_DEV_ID),
        "target_username": khang.username,
        "published_count": len(rows),
        "already_owned_count": len(already_owned),
        "missing_count": len(missing),
        "granted_count": len(granted),
        "missing_assets": [
            {
                "id": str(a.id),
                "slug": a.slug,
                "kind": a.kind,
                "rarity": a.rarity,
            }
            for a, _ in missing
        ],
        "already_owned": already_owned,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Khang Dev Vault Privilege Tool")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate without applying changes",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Explicitly execute and commit changes",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database connection URL (must be validated dedicated loopback demo/test)",
    )
    args = parser.parse_args(argv)

    is_dry_run = True
    if args.execute:
        is_dry_run = False
    elif args.dry_run:
        is_dry_run = True

    from app.catalog_activation import validate_target
    from app.config import load_settings
    from app.db import create_db_engine

    db_url = args.database_url or load_settings().database_url
    target_db = validate_target(db_url, allow_demo=True)

    engine = create_db_engine(db_url)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        if not is_dry_run:
            with db.begin():
                result = sync_khang_dev_vault_privilege(db, now, dry_run=False)
        else:
            result = sync_khang_dev_vault_privilege(db, now, dry_run=True)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
