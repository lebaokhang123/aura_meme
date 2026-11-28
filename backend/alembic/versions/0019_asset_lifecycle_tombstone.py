"""Support H06 asset soft-delete tombstone, historical reward rarity, and mutable asset rarity.

Revision ID: 0019_asset_lifecycle_tombstone
Revises: 0018_canonical_asset_filenames
"""
from alembic import op
import sqlalchemy as sa


revision = '0019_asset_lifecycle_tombstone'
down_revision = '0018_canonical_asset_filenames'
branch_labels = None
depends_on = None


NEW_EQUIPMENT_GUARD = """
DECLARE amount integer; enabled boolean; review text; deleted_ts timestamptz;
BEGIN
  IF TG_TABLE_NAME = 'user_equipment' THEN
    SELECT i.quantity, a.active, a.source_rights->>'review_status', a.deleted_at
      INTO amount, enabled, review, deleted_ts
      FROM user_inventory i JOIN asset_items a ON a.id=i.asset_id
      WHERE i.user_id=NEW.user_id AND i.asset_id=NEW.asset_id FOR SHARE OF i,a;
    IF NOT FOUND OR amount <= 0 OR NOT enabled OR review IS DISTINCT FROM 'approved' OR deleted_ts IS NOT NULL THEN
      RAISE EXCEPTION 'Equipment requires owned active inventory' USING ERRCODE='23514';
    END IF;
  ELSIF TG_TABLE_NAME = 'user_inventory' THEN
    IF EXISTS (SELECT 1 FROM user_equipment WHERE user_id=OLD.user_id AND asset_id=OLD.asset_id) THEN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Unequip before removing inventory' USING ERRCODE='23514';
      ELSIF NEW.quantity <= 0 THEN
        RAISE EXCEPTION 'Unequip before removing inventory' USING ERRCODE='23514';
      END IF;
    END IF;
  ELSIF TG_TABLE_NAME = 'asset_items' AND TG_OP = 'UPDATE' THEN
    IF NEW.kind IS DISTINCT FROM OLD.kind
       AND EXISTS (SELECT 1 FROM user_inventory WHERE asset_id=OLD.id) THEN
      RAISE EXCEPTION 'Referenced catalog kind is immutable' USING ERRCODE='23514';
    END IF;
    IF (NOT NEW.active OR NEW.deleted_at IS NOT NULL) AND EXISTS (SELECT 1 FROM user_equipment WHERE asset_id=OLD.id) THEN
      RAISE EXCEPTION 'Unequip before deactivating asset' USING ERRCODE='23514';
    END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END
"""

OLD_EQUIPMENT_GUARD = """
DECLARE amount integer; enabled boolean; review text;
BEGIN
  IF TG_TABLE_NAME = 'user_equipment' THEN
    SELECT i.quantity, a.active, a.source_rights->>'review_status' INTO amount, enabled, review
      FROM user_inventory i JOIN asset_items a ON a.id=i.asset_id
      WHERE i.user_id=NEW.user_id AND i.asset_id=NEW.asset_id FOR SHARE OF i,a;
    IF NOT FOUND OR amount <= 0 OR NOT enabled OR review IS DISTINCT FROM 'approved' THEN
      RAISE EXCEPTION 'Equipment requires owned active inventory' USING ERRCODE='23514';
    END IF;
  ELSIF TG_TABLE_NAME = 'user_inventory' THEN
    IF EXISTS (SELECT 1 FROM user_equipment WHERE user_id=OLD.user_id AND asset_id=OLD.asset_id) THEN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Unequip before removing inventory' USING ERRCODE='23514';
      ELSIF NEW.quantity <= 0 THEN
        RAISE EXCEPTION 'Unequip before removing inventory' USING ERRCODE='23514';
      END IF;
    END IF;
  ELSIF TG_TABLE_NAME = 'asset_items' AND TG_OP = 'UPDATE' THEN
    IF (NEW.kind IS DISTINCT FROM OLD.kind OR NEW.rarity IS DISTINCT FROM OLD.rarity)
       AND EXISTS (SELECT 1 FROM user_inventory WHERE asset_id=OLD.id) THEN
      RAISE EXCEPTION 'Referenced catalog kind and rarity are immutable' USING ERRCODE='23514';
    END IF;
    IF NOT NEW.active AND EXISTS (SELECT 1 FROM user_equipment WHERE asset_id=OLD.id) THEN
      RAISE EXCEPTION 'Unequip before deactivating asset' USING ERRCODE='23514';
    END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END
"""


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column('asset_items', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('asset_items', sa.Column('deleted_by', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_asset_items_deleted_by_users', 'asset_items', 'users',
        ['deleted_by'], ['id'], ondelete='RESTRICT',
    )
    op.create_check_constraint(op.f('ck_asset_items_deleted_inactive'), 'asset_items', 'deleted_at IS NULL OR NOT active')
    op.create_index('ix_asset_items_deleted_at', 'asset_items', ['deleted_at'])

    op.add_column('case_opens', sa.Column('reward_rarity', sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f('ck_case_opens_reward_rarity'), 'case_opens',
        "reward_rarity IS NULL OR reward_rarity IN ('D','C','B','A','S')",
    )

    op.drop_constraint('fk_case_pool_items_asset_rarity', 'case_pool_items', type_='foreignkey')
    op.create_foreign_key(
        'fk_case_pool_items_asset_id', 'case_pool_items', 'asset_items',
        ['asset_id'], ['id'], ondelete='RESTRICT',
    )

    op.execute(f"CREATE OR REPLACE FUNCTION aurameme_equipment_guard() RETURNS trigger LANGUAGE plpgsql AS $${NEW_EQUIPMENT_GUARD}$$")


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT 1 FROM asset_items WHERE deleted_at IS NOT NULL LIMIT 1")).first() is not None:
        raise RuntimeError("Refusing downgrade: permanently deleted asset tombstones exist.")
    if conn.execute(sa.text("SELECT 1 FROM case_pool_items c JOIN asset_items a ON a.id = c.asset_id WHERE c.rarity <> a.rarity LIMIT 1")).first() is not None:
        raise RuntimeError("Refusing downgrade: historical case_pool_items rarity differs from current asset_items rarity.")

    op.execute(f"CREATE OR REPLACE FUNCTION aurameme_equipment_guard() RETURNS trigger LANGUAGE plpgsql AS $${OLD_EQUIPMENT_GUARD}$$")
    op.drop_constraint('fk_case_pool_items_asset_id', 'case_pool_items', type_='foreignkey')
    op.create_foreign_key(
        'fk_case_pool_items_asset_rarity', 'case_pool_items', 'asset_items',
        ['asset_id', 'rarity'], ['id', 'rarity'], ondelete='RESTRICT',
    )
    op.drop_constraint(op.f('ck_case_opens_reward_rarity'), 'case_opens', type_='check')
    op.drop_column('case_opens', 'reward_rarity')

    op.drop_index('ix_asset_items_deleted_at', table_name='asset_items')
    op.drop_constraint(op.f('ck_asset_items_deleted_inactive'), 'asset_items', type_='check')
    op.drop_constraint('fk_asset_items_deleted_by_users', 'asset_items', type_='foreignkey')
    op.drop_column('asset_items', 'deleted_by')
    op.drop_column('asset_items', 'deleted_at')
