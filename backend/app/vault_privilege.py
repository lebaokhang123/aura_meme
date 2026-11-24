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
from app.aura_lock import lock_aura_mutation
from app.catalog_rights import reviewed_source_rights, reviewed_source_rights_sql
from app.inventory import ready_asset
from app.inventory_grants import inventory_state
from app.models import (
    AdminAuditLog,
    AssetItem,
    CaseLootTable,
    CasePoolItem,
    InventoryGrant,
    RewardPolicyVersion,
    User,
    UserInventory,
)

# Schema constraint: ck_inventory_grants_source_type -> source_type IN ('case_open','weekly_streak','level','admin')
PRIVILEGE_SOURCE_TYPE = "admin"
PRIVILEGE_KEY_PREFIX = "privilege:khang_dev:"


def assert_khang_dev_target(target_user_id: UUID) -> None:
    """Strictly ensure the target is Khang Dev and never Kien Dev or any other user."""
    if target_user_id != KHANG_DEV_ID:
        raise ValueError(
            f"Vault privilege is strictly exclusive to Khang Dev ({KHANG_DEV_ID}); "
            f"forbidden for user {target_user_id}."
        )


def resolve_reward_policy_id(db: Session, asset_id: UUID | None = None, now: datetime | None = None) -> UUID:
    """Resolve a valid RewardPolicyVersion ID for foreign key constraint satisfaction.

    Strict rules:
    - Only policies with status='published' and effective_at <= now are eligible.
    - Draft or future policies are NEVER selected.
    - If asset_id is provided, prioritize published policy linked to that asset's loot table.
    - Otherwise, select the latest published policy where effective_at <= now.
    - If none found, raises ValueError (no fallback to draft/future).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if asset_id is not None:
        pool_pid = db.scalar(
            select(CaseLootTable.policy_id)
            .join(CasePoolItem, CasePoolItem.loot_table_id == CaseLootTable.id)
            .join(RewardPolicyVersion, RewardPolicyVersion.id == CaseLootTable.policy_id)
            .where(
                CasePoolItem.asset_id == asset_id,
                CaseLootTable.status == "published",
                RewardPolicyVersion.status == "published",
                RewardPolicyVersion.effective_at <= now,
            )
            .order_by(RewardPolicyVersion.version.desc())
        )
        if pool_pid is not None:
            return pool_pid

    # Latest published reward policy version effective as of now
    published_pid = db.scalar(
        select(RewardPolicyVersion.id)
        .where(
            RewardPolicyVersion.status == "published",
            RewardPolicyVersion.effective_at <= now,
        )
        .order_by(RewardPolicyVersion.version.desc())
    )
    if published_pid is not None:
        return published_pid

    raise ValueError("No valid published RewardPolicyVersion with effective_at <= now found.")


def is_asset_eligible_for_privilege(asset: AssetItem | None) -> bool:
    """Check if an asset is active, approved, and has valid source rights."""
    if asset is None or not getattr(asset, "active", False):
        return False
    if getattr(asset, "kind", None) not in ("avatar", "background"):
        return False
    if getattr(asset, "rarity", None) not in ("D", "C", "B", "A", "S"):
        return False
    rights = dict(getattr(asset, "source_rights", None) or {})
    if rights.get("review_status") != "approved":
        return False
    if rights.get("name_review_status") != "approved":
        return False
    if not reviewed_source_rights(rights):
        return False
    return True


def grant_khang_dev_single_asset_if_eligible(
    db: Session,
    asset: AssetItem,
    now: datetime,
    *,
    actor_id: UUID = KHANG_DEV_ID,
    policy_id: UUID | None = None,
    source: str = "admin_approval_hook",
) -> bool:
    """Grant 1 unit of a single newly eligible asset to Khang Dev if not already owned.

    - Called from admin approval flow, publication flow, or sync tool.
    - Idempotent: does nothing if already owned.
    - Zero EXP, safe locks, audit log recorded.
    - Returns True if granted, False if skipped.
    """
    if not is_asset_eligible_for_privilege(asset):
        return False

    khang = db.scalar(
        select(User)
        .where(User.id == KHANG_DEV_ID, User.status == "active")
        .with_for_update()
    )
    if khang is None:
        return False

    user_inv = db.scalar(
        select(UserInventory)
        .where(UserInventory.user_id == KHANG_DEV_ID, UserInventory.asset_id == asset.id)
        .with_for_update()
    )
    if user_inv is not None and user_inv.quantity > 0:
        return False

    event_key = f"{PRIVILEGE_KEY_PREFIX}{asset.id}"
    existing_grant = db.scalar(
        select(InventoryGrant).where(
            InventoryGrant.user_id == KHANG_DEV_ID,
            InventoryGrant.event_key == event_key,
        )
    )
    if existing_grant is not None:
        inventory_state(db, KHANG_DEV_ID, asset.id)
        return False

    effective_policy_id = policy_id or resolve_reward_policy_id(db, asset.id, now)

    # UserInventory must be flushed before InventoryGrant (FK dependency)
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
        policy_id=effective_policy_id,
        granted_at=now,
    )
    db.add(grant)
    db.flush()

    db.add(
        AdminAuditLog(
            id=uuid4(),
            actor_id=actor_id,
            action="vault.privilege.auto_grant",
            target_type="user_inventory",
            target_id=str(KHANG_DEV_ID),
            before_json=None,
            after_json={
                "granted_assets": [str(asset.id)],
                "policy_id": str(effective_policy_id),
                "source": source,
            },
            created_at=now,
        )
    )
    db.flush()
    inventory_state(db, KHANG_DEV_ID, asset.id)
    return True


def auto_grant_khang_dev_published_items(
    db: Session,
    manifest,
    policy_id: UUID,
    now: datetime,
    *,
    actor_id: UUID = KHANG_DEV_ID,
) -> list[UUID]:
    """Automatically grant newly published items to Khang Dev during publication.

    - Reuses grant_khang_dev_single_asset_if_eligible for unified ledger integrity.
    - Verifies actual AssetItem in database, not relying solely on manifest.
    - Applies same strict eligibility conditions.
    - Idempotent: 1 unit if not owned; preserves existing quantity if already owned.
    - +0 EXP, no fake chest openings, no wallet transactions.
    - Skips cleanly if Khang Dev does not exist in the database.
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
        item_id = UUID(str(item.id)) if isinstance(item.id, str) else item.id
        asset = db.scalar(select(AssetItem).where(AssetItem.id == item_id))
        if asset is None or not is_asset_eligible_for_privilege(asset):
            continue

        was_granted = grant_khang_dev_single_asset_if_eligible(
            db,
            asset,
            now,
            actor_id=actor_id,
            policy_id=policy_id,
            source="publication_hook",
        )
        if was_granted:
            granted.append(item_id)

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
    - Deduplicates by asset.id: each eligible asset is processed exactly once.
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

    stmt = (
        select(AssetItem)
        .where(
            AssetItem.active.is_(True),
            AssetItem.kind.in_(("avatar", "background")),
        )
        .order_by(AssetItem.kind, AssetItem.rarity, AssetItem.slug)
    )
    candidates = list(db.scalars(stmt))

    # Filter by unified eligibility check - each asset appears exactly once
    eligible_assets = [a for a in candidates if is_asset_eligible_for_privilege(a)]

    already_owned = []
    missing = []

    for asset in eligible_assets:
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
            try:
                pid = resolve_reward_policy_id(db, asset.id, now)
                missing.append((asset, pid))
            except ValueError:
                # If no valid published policy effective as of now, skip
                continue

    granted = []
    if not dry_run and missing:
        for asset, policy_id in missing:
            was_granted = grant_khang_dev_single_asset_if_eligible(
                db,
                asset,
                now,
                actor_id=actor_id,
                policy_id=policy_id,
                source="sync_tool",
            )
            if was_granted:
                granted.append(str(asset.id))

        if granted:
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
        "published_count": len(eligible_assets),
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


def privilege_guard(db: Session, actor_id: UUID) -> None:
    """Safety guard for Khang Dev privilege operations:
    - Validates target connection against loopback demo/test/e2e allowlist.
    - Verifies current database, role, and public schema.
    - Verifies alembic schema revision 0018.
    - Verifies actor is active ADMIN and strictly Khang Dev.
    - Acquires global aura mutation advisory lock.
    """
    from app.aura_lock import lock_aura_mutation
    from app.catalog_activation import validate_target
    from app.demo import reviewed_demo_schema
    from app.models import Role, UserRole

    conn = db.connection()
    db_url = conn.engine.url.render_as_string(hide_password=False)
    database = validate_target(db_url, allow_demo=True)
    role = {
        "aurameme_test": "aurameme_test",
        "aurameme_e2e": "aurameme_e2e_app",
        "aurameme_demo": "aurameme_demo",
    }[database]

    current_id = tuple(db.execute(text("SELECT current_database(), current_user, current_schema()")).one())
    if current_id != (database, role, "public"):
        raise ValueError(f"Unsafe database identity: {current_id}")

    reviewed_demo_schema(conn)

    if db.scalar(text("SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname=current_user")):
        raise ValueError("Privilege operations forbid superuser or privileged application roles.")

    lock_aura_mutation(db)

    assert_khang_dev_target(actor_id)
    actor = db.scalar(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(User.id == actor_id, User.status == "active", Role.code == "ADMIN")
        .with_for_update(of=User, read=True)
    )
    if actor is None:
        raise ValueError("Khang Dev must exist as an active ADMIN user.")


def main(argv=None, *, engine=None):
    parser = argparse.ArgumentParser(description="Khang Dev Vault Privilege Tool")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate without applying changes (default mode)",
    )
    mode_group.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute and commit changes (requires --confirm CONFIRM_GRANT_KHANG_DEV)",
    )
    parser.add_argument(
        "--confirm",
        type=str,
        default=None,
        help="Confirmation phrase required for --execute ('CONFIRM_GRANT_KHANG_DEV')",
    )
    args = parser.parse_args(argv)

    if args.execute and args.confirm != "CONFIRM_GRANT_KHANG_DEV":
        raise ValueError("--execute requires explicit confirmation: --confirm CONFIRM_GRANT_KHANG_DEV")

    is_dry_run = not args.execute

    from app.config import load_settings
    from app.db import create_db_engine

    created_engine = False
    if engine is None:
        settings = load_settings()
        engine = create_db_engine(settings)
        created_engine = True

    try:
        now = datetime.now(timezone.utc)
        with Session(engine) as db:
            privilege_guard(db, KHANG_DEV_ID)
            if not is_dry_run:
                result = sync_khang_dev_vault_privilege(db, now, dry_run=False, actor_id=KHANG_DEV_ID)
                db.commit()
            else:
                result = sync_khang_dev_vault_privilege(db, now, dry_run=True, actor_id=KHANG_DEV_ID)

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    finally:
        if created_engine and engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
