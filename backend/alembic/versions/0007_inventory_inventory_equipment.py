"""inventory equipment

Revision ID: 0007_inventory
Revises: 0006_catalog
"""
from alembic import op
import sqlalchemy as sa


revision = '0007_inventory'
down_revision = '0006_catalog'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user_inventory',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('asset_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('acquired_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('quantity >= 0', name=op.f('ck_user_inventory_quantity_nonnegative')),
    sa.ForeignKeyConstraint(['asset_id'], ['asset_items.id'], name=op.f('fk_user_inventory_asset_id_asset_items'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_inventory_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('user_id', 'asset_id', name=op.f('pk_user_inventory'))
    )
    op.create_table('user_equipment',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('slot_kind', sa.Text(), nullable=False),
    sa.Column('asset_id', sa.Uuid(), nullable=False),
    sa.Column('equipped_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("slot_kind IN ('avatar','frame','icon','effect')", name=op.f('ck_user_equipment_slot_kind')),
    sa.ForeignKeyConstraint(['asset_id', 'slot_kind'], ['asset_items.id', 'asset_items.kind'], name='fk_user_equipment_asset_kind', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id', 'asset_id'], ['user_inventory.user_id', 'user_inventory.asset_id'], name='fk_user_equipment_owner_asset', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_equipment_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('user_id', 'slot_kind', name=op.f('pk_user_equipment'))
    )

    op.execute("""CREATE FUNCTION aurameme_equipment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
$$""")
    op.execute("CREATE TRIGGER user_equipment_guard BEFORE INSERT OR UPDATE ON user_equipment FOR EACH ROW EXECUTE FUNCTION aurameme_equipment_guard()")
    op.execute("CREATE TRIGGER user_inventory_guard BEFORE UPDATE OR DELETE ON user_inventory FOR EACH ROW EXECUTE FUNCTION aurameme_equipment_guard()")
    op.execute("CREATE TRIGGER asset_items_guard BEFORE UPDATE OR DELETE ON asset_items FOR EACH ROW EXECUTE FUNCTION aurameme_equipment_guard()")


def downgrade():
    connection = op.get_bind()
    tables = sorted(("users", "roles", "user_roles", "profiles", "auth_sessions", "categories",
        "media_uploads", "posts", "comments", "contact_messages", "admin_audit_logs", "post_reactions",
        "post_bookmarks", "reward_policy_versions", "user_progress", "aura_ledger", "wallets", "wallet_transactions", "daily_checkins", "asset_items", "user_inventory", "user_equipment"))
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql("LOCK TABLE " + ", ".join("public." + name for name in tables) + " IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql("SELECT 1 FROM public." + name + " LIMIT 1").first() is not None for name in tables):
        raise RuntimeError("Refusing downgrade of nonempty tables; preserve data and review first.")
    op.execute("DROP TRIGGER user_equipment_guard ON user_equipment")
    op.execute("DROP TRIGGER user_inventory_guard ON user_inventory")
    op.execute("DROP TRIGGER asset_items_guard ON asset_items")
    op.execute("DROP FUNCTION aurameme_equipment_guard()")
    op.drop_table('user_equipment')
    op.drop_table('user_inventory')
