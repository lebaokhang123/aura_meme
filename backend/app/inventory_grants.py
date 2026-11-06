"""Internal draft item grants; no endpoint or production issuance switch."""
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import func, select
from app.aura import simulation_only
from app.inventory import ready_asset
from app.models import AssetItem, DailyCheckin, InventoryGrant, UserInventory


def inventory_state(db, owner, asset_id):
    item = db.scalar(select(UserInventory).where(UserInventory.user_id == owner, UserInventory.asset_id == asset_id).with_for_update().execution_options(populate_existing=True))
    quantity = db.scalar(select(func.coalesce(func.sum(InventoryGrant.quantity), 0)).where(InventoryGrant.user_id == owner, InventoryGrant.asset_id == asset_id))
    if quantity != (item.quantity if item else 0):
        raise ValueError('Inventory cache differs from its grants; preserve data for review.')
    return item


def grant_item(db, owner, asset_id, policy_id, key, source, now, case_open_id=None):
    now = simulation_only(db, now)
    existing = db.scalar(select(InventoryGrant).where(InventoryGrant.user_id == owner, InventoryGrant.event_key == key))
    if existing is not None:
        if existing.asset_id != asset_id or existing.source_type != source or existing.case_open_id != case_open_id:
            raise ValueError('Conflicting inventory business event.')
        inventory_state(db, owner, asset_id)
        return existing
    item = inventory_state(db, owner, asset_id)
    asset = db.scalar(select(AssetItem).where(AssetItem.id == asset_id).with_for_update(read=True).execution_options(populate_existing=True))
    if not ready_asset(asset) or asset.kind == 'generator':
        raise ValueError('An active approved cosmetic fixture is required.')
    if item is None:
        item = UserInventory(user_id=owner, asset_id=asset_id, quantity=0, acquired_at=now, updated_at=now)
        db.add(item)
    item.quantity += 1
    item.updated_at = now
    db.flush()
    grant = InventoryGrant(id=uuid4(), user_id=owner, asset_id=asset_id, event_key=key, quantity=1,
        source_type=source, case_open_id=case_open_id, policy_id=policy_id, granted_at=now)
    db.add(grant)
    db.flush()
    return grant


def weekly_grant(db, owner, asset_id, policy_id, day, now):
    monday = day - timedelta(days=day.weekday())
    count = db.scalar(select(func.count()).select_from(DailyCheckin).where(DailyCheckin.user_id == owner,
        DailyCheckin.effective_day >= monday, DailyCheckin.effective_day <= day,
        DailyCheckin.effective_day < monday + timedelta(days=7)))
    if count == 7:
        grant_item(db, owner, asset_id, policy_id, 'weekly:' + monday.isoformat(), 'weekly_streak', now)
