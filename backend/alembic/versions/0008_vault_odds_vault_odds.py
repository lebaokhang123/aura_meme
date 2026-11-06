"""vault odds

Revision ID: 0008_vault_odds
Revises: 0007_inventory
"""
from alembic import op
import sqlalchemy as sa


revision = '0008_vault_odds'
down_revision = '0007_inventory'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('case_definitions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('slug', sa.Text(), nullable=False),
    sa.Column('label', sa.Text(), nullable=False),
    sa.Column('cost_khi_van', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("btrim(slug) <> '' AND btrim(label) <> ''", name=op.f('ck_case_definitions_nonempty')),
    sa.CheckConstraint("status IN ('draft','active','retired')", name=op.f('ck_case_definitions_status')),
    sa.CheckConstraint('cost_khi_van >= 0', name=op.f('ck_case_definitions_cost_nonnegative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_case_definitions')),
    sa.UniqueConstraint('slug', name=op.f('uq_case_definitions_slug'))
    )
    op.create_table('case_loot_tables',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('odds_version', sa.Integer(), nullable=False),
    sa.Column('band_no', sa.SmallInteger(), nullable=False),
    sa.Column('min_earned_xp', sa.BigInteger(), nullable=False),
    sa.Column('max_earned_xp', sa.BigInteger(), nullable=True),
    sa.Column('policy_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('active_from', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('draft','published','retired')", name=op.f('ck_case_loot_tables_status')),
    sa.CheckConstraint('max_earned_xp IS NULL OR max_earned_xp > min_earned_xp', name=op.f('ck_case_loot_tables_range')),
    sa.CheckConstraint('odds_version > 0 AND band_no > 0 AND min_earned_xp >= 0', name=op.f('ck_case_loot_tables_positive_version_band')),
    sa.ForeignKeyConstraint(['case_id'], ['case_definitions.id'], name=op.f('fk_case_loot_tables_case_id_case_definitions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['policy_id'], ['reward_policy_versions.id'], name=op.f('fk_case_loot_tables_policy_id_reward_policy_versions'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_case_loot_tables')),
    sa.UniqueConstraint('case_id', 'id', name='uq_case_loot_tables_case_id_id'),
    sa.UniqueConstraint('case_id', 'odds_version', 'band_no', name='uq_case_loot_tables_case_version_band')
    )
    op.create_index('ix_case_loot_tables_case_status_from', 'case_loot_tables', ['case_id', 'status', 'active_from'], unique=False)
    op.create_table('case_loot_rarities',
    sa.Column('loot_table_id', sa.Uuid(), nullable=False),
    sa.Column('rarity', sa.Text(), nullable=False),
    sa.Column('weight_bps', sa.Integer(), nullable=False),
    sa.CheckConstraint("rarity IN ('D','C','B','A','S')", name=op.f('ck_case_loot_rarities_rarity')),
    sa.CheckConstraint('weight_bps BETWEEN 0 AND 10000', name=op.f('ck_case_loot_rarities_weight_bps')),
    sa.ForeignKeyConstraint(['loot_table_id'], ['case_loot_tables.id'], name=op.f('fk_case_loot_rarities_loot_table_id_case_loot_tables'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('loot_table_id', 'rarity', name=op.f('pk_case_loot_rarities'))
    )
    op.create_table('case_pool_items',
    sa.Column('loot_table_id', sa.Uuid(), nullable=False),
    sa.Column('asset_id', sa.Uuid(), nullable=False),
    sa.Column('rarity', sa.Text(), nullable=False),
    sa.Column('item_weight', sa.Integer(), nullable=False),
    sa.CheckConstraint('item_weight > 0', name=op.f('ck_case_pool_items_item_weight')),
    sa.ForeignKeyConstraint(['asset_id', 'rarity'], ['asset_items.id', 'asset_items.rarity'], name='fk_case_pool_items_asset_rarity', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['loot_table_id', 'rarity'], ['case_loot_rarities.loot_table_id', 'case_loot_rarities.rarity'], name='fk_case_pool_items_bucket', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('loot_table_id', 'asset_id', name=op.f('pk_case_pool_items'))
    )

    op.execute("""CREATE FUNCTION aurameme_odds_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_pool uuid; new_pool uuid; current_status text;
BEGIN
  IF TG_TABLE_NAME = 'case_loot_tables' THEN
    IF TG_OP <> 'INSERT' AND OLD.status <> 'draft' THEN
      IF TG_OP = 'UPDATE' AND OLD.status = 'published' AND NEW.status = 'retired'
         AND (to_jsonb(NEW)-'status') = (to_jsonb(OLD)-'status') THEN RETURN NEW; END IF;
      RAISE EXCEPTION 'Published odds versions are immutable' USING ERRCODE='23514';
    END IF;
  ELSE
    IF TG_OP <> 'INSERT' THEN old_pool := OLD.loot_table_id; END IF;
    IF TG_OP <> 'DELETE' THEN new_pool := NEW.loot_table_id; END IF;
    FOR current_status IN SELECT status FROM case_loot_tables
      WHERE id=old_pool OR id=new_pool ORDER BY id FOR SHARE LOOP
      IF current_status <> 'draft' THEN
        RAISE EXCEPTION 'Published odds children are immutable' USING ERRCODE='23514';
      END IF;
    END LOOP;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END
$$""")
    op.execute("CREATE TRIGGER case_loot_tables_guard BEFORE INSERT OR UPDATE OR DELETE ON case_loot_tables FOR EACH ROW EXECUTE FUNCTION aurameme_odds_guard()")
    op.execute("CREATE TRIGGER case_loot_tables_no_truncate BEFORE TRUNCATE ON case_loot_tables FOR EACH STATEMENT EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER case_loot_rarities_guard BEFORE INSERT OR UPDATE OR DELETE ON case_loot_rarities FOR EACH ROW EXECUTE FUNCTION aurameme_odds_guard()")
    op.execute("CREATE TRIGGER case_loot_rarities_no_truncate BEFORE TRUNCATE ON case_loot_rarities FOR EACH STATEMENT EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER case_pool_items_guard BEFORE INSERT OR UPDATE OR DELETE ON case_pool_items FOR EACH ROW EXECUTE FUNCTION aurameme_odds_guard()")
    op.execute("CREATE TRIGGER case_pool_items_no_truncate BEFORE TRUNCATE ON case_pool_items FOR EACH STATEMENT EXECUTE FUNCTION aurameme_immutable_ledger()")


def downgrade():
    connection = op.get_bind()
    tables = sorted(("users", "roles", "user_roles", "profiles", "auth_sessions", "categories",
        "media_uploads", "posts", "comments", "contact_messages", "admin_audit_logs", "post_reactions",
        "post_bookmarks", "reward_policy_versions", "user_progress", "aura_ledger", "wallets", "wallet_transactions", "daily_checkins", "asset_items", "user_inventory", "user_equipment", "case_definitions", "case_loot_tables", "case_loot_rarities", "case_pool_items"))
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql("LOCK TABLE " + ", ".join("public." + name for name in tables) + " IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql("SELECT 1 FROM public." + name + " LIMIT 1").first() is not None for name in tables):
        raise RuntimeError("Refusing downgrade of nonempty tables; preserve data and review first.")
    op.execute("DROP TRIGGER case_loot_tables_guard ON case_loot_tables")
    op.execute("DROP TRIGGER case_loot_tables_no_truncate ON case_loot_tables")
    op.execute("DROP TRIGGER case_loot_rarities_guard ON case_loot_rarities")
    op.execute("DROP TRIGGER case_loot_rarities_no_truncate ON case_loot_rarities")
    op.execute("DROP TRIGGER case_pool_items_guard ON case_pool_items")
    op.execute("DROP TRIGGER case_pool_items_no_truncate ON case_pool_items")
    op.execute("DROP FUNCTION aurameme_odds_guard()")
    op.drop_table('case_pool_items')
    op.drop_table('case_loot_rarities')
    op.drop_index('ix_case_loot_tables_case_status_from',table_name='case_loot_tables')
    op.drop_table('case_loot_tables')
    op.drop_table('case_definitions')
