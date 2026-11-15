"""Owned Meme persistence; callers apply the shared social Aura rules once per post event."""
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import undefer

from app.models import AssetItem, User, UserInventory
from app.security import AuthError
from app.catalog_rights import reviewed_source_rights_sql


def enabled(request):
    from app.vault_runtime import runtime_enabled
    return request is not None and runtime_enabled(request)


def valid_meme_reaction(model):
    return and_(model.reaction_type == 'meme', exists(select(UserInventory.asset_id)
        .join(AssetItem, AssetItem.id == UserInventory.asset_id)
        .where(UserInventory.user_id == model.user_id, UserInventory.asset_id == model.meme_asset_id,
               UserInventory.quantity > 0, AssetItem.kind == 'avatar', AssetItem.active.is_(True),
               reviewed_source_rights_sql(AssetItem.source_rights))).correlate(model))


def reaction_statement(model, target_field, target_id, owner, payload, now, metadata):
    values = {target_field: target_id, 'user_id': owner, 'reaction_type': payload.reaction_type,
              'created_at': now, 'updated_at': now}
    updates = {'reaction_type': payload.reaction_type, 'updated_at': now}
    changed = model.reaction_type != payload.reaction_type
    if metadata:
        values['meme_asset_id'] = updates['meme_asset_id'] = payload.meme_asset_id
        changed = or_(changed, model.meme_asset_id.is_distinct_from(payload.meme_asset_id))
    return insert(model).values(**values).on_conflict_do_update(
        index_elements=[target_field, 'user_id'], set_=updates, where=changed)


def set_owned_reaction(account, request, model, target_field, target_id, payload, now):
    from app.vault_runtime import require_enabled, schema_ready
    metadata = schema_ready(account.db) if payload.reaction_type != 'meme' else enabled(request)
    if payload.reaction_type == 'meme':
        require_enabled(request, account.db)
        item = account.db.scalar(select(UserInventory).where(UserInventory.user_id == account.user.id,
            UserInventory.asset_id == payload.meme_asset_id).with_for_update().execution_options(populate_existing=True))
        asset = account.db.scalar(select(AssetItem).where(AssetItem.id == payload.meme_asset_id)
            .with_for_update(read=True).execution_options(populate_existing=True))
        from app.inventory import ready_asset
        if item is None or item.quantity <= 0 or not ready_asset(asset) or asset.kind != 'avatar':
            raise AuthError(404, 'NOT_FOUND', 'Owned approved Meme not found.')
    account.db.execute(reaction_statement(model, target_field, target_id, account.user.id, payload, now, metadata))


def meme_reaction_states(db, model, target_ids, viewer_id, request):
    """One aggregate query for a public page, never one query per asset or actor."""
    if not target_ids or not enabled(request):
        return {}
    from app.vault_runtime import require_schema
    from app.inventory import asset_dto
    require_schema(db)
    target = model.post_id if hasattr(model, 'post_id') else model.comment_id
    query = (select(target, AssetItem, func.count(), func.count().filter(model.user_id == viewer_id))
        .select_from(model).join(User, User.id == model.user_id)
        .join(AssetItem, AssetItem.id == model.meme_asset_id)
        .join(UserInventory, and_(UserInventory.user_id == model.user_id,
                                  UserInventory.asset_id == model.meme_asset_id))
        .where(target.in_(target_ids), model.reaction_type == 'meme', User.status == 'active',
               UserInventory.quantity > 0, AssetItem.kind == 'avatar', AssetItem.active.is_(True),
               reviewed_source_rights_sql(AssetItem.source_rights))
        .group_by(target, AssetItem.id).order_by(target, AssetItem.id)
        .options(undefer(AssetItem.display_name), undefer(AssetItem.effect_key)))
    states = {target_id: {'viewer_meme_asset_id': None, 'meme_reactions': []} for target_id in target_ids}
    from app.inventory import ready_asset
    for target_id, asset, count, viewer_selected in db.execute(query).all():
        if not ready_asset(asset):
            continue
        state = states[target_id]
        state['meme_reactions'].append({'asset': asset_dto(asset, request, metadata=True), 'count': count})
        if viewer_selected:
            state['viewer_meme_asset_id'] = asset.id
    return states
