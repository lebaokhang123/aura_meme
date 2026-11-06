"""vault open grants

Revision ID: 0009_vault_open
Revises: 0008_vault_odds
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0009_vault_open'
down_revision = '0008_vault_odds'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('case_opens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('request_key', sa.Text(), nullable=False),
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('loot_table_id', sa.Uuid(), nullable=False),
    sa.Column('reward_asset_id', sa.Uuid(), nullable=False),
    sa.Column('earned_xp_at_open', sa.BigInteger(), nullable=False),
    sa.Column('cost_khi_van', sa.BigInteger(), nullable=False),
    sa.Column('wallet_transaction_id', sa.Uuid(), nullable=True),
    sa.Column('is_daily_free', sa.Boolean(), nullable=False),
    sa.Column('effective_day', sa.Date(), nullable=False),
    sa.Column('decision_trace', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("effective_day = ((created_at AT TIME ZONE 'Asia/Ho_Chi_Minh') - interval '7 hours')::date", name=op.f('ck_case_opens_effective_day')),
    sa.CheckConstraint("jsonb_typeof(decision_trace)='object'", name=op.f('ck_case_opens_trace_object')),
    sa.CheckConstraint('(cost_khi_van=0 AND wallet_transaction_id IS NULL) OR (cost_khi_van>0 AND wallet_transaction_id IS NOT NULL)', name=op.f('ck_case_opens_debit_required')),
    sa.CheckConstraint('NOT is_daily_free OR cost_khi_van=0', name=op.f('ck_case_opens_free_cost')),
    sa.CheckConstraint('earned_xp_at_open >= 0 AND cost_khi_van >= 0', name=op.f('ck_case_opens_nonnegative')),
    sa.ForeignKeyConstraint(['case_id', 'loot_table_id'], ['case_loot_tables.case_id', 'case_loot_tables.id'], name='fk_case_opens_case_pool', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['loot_table_id', 'reward_asset_id'], ['case_pool_items.loot_table_id', 'case_pool_items.asset_id'], name='fk_case_opens_pool_reward', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id', 'wallet_transaction_id'], ['wallet_transactions.user_id', 'wallet_transactions.id'], name='fk_case_opens_owner_debit', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_case_opens_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_case_opens')),
    sa.UniqueConstraint('user_id', 'id', name='uq_case_opens_user_id_id'),
    sa.UniqueConstraint('user_id', 'request_key', name='uq_case_opens_user_request'),
    sa.UniqueConstraint('wallet_transaction_id', name=op.f('uq_case_opens_wallet_transaction_id'))
    )
    op.create_index('ix_case_opens_user_created_id', 'case_opens', ['user_id', 'created_at', 'id'], unique=False)
    op.create_index('uq_case_opens_daily_free', 'case_opens', ['user_id', 'case_id', 'effective_day'], unique=True, postgresql_where=sa.text('is_daily_free'))
    op.create_table('inventory_grants',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('asset_id', sa.Uuid(), nullable=False),
    sa.Column('event_key', sa.Text(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('source_type', sa.Text(), nullable=False),
    sa.Column('case_open_id', sa.Uuid(), nullable=True),
    sa.Column('policy_id', sa.Uuid(), nullable=False),
    sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("(source_type='case_open')=(case_open_id IS NOT NULL)", name=op.f('ck_inventory_grants_case_reference')),
    sa.CheckConstraint("source_type IN ('case_open','weekly_streak','level','admin')", name=op.f('ck_inventory_grants_source_type')),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_inventory_grants_quantity_positive')),
    sa.ForeignKeyConstraint(['policy_id'], ['reward_policy_versions.id'], name=op.f('fk_inventory_grants_policy_id_reward_policy_versions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id', 'asset_id'], ['user_inventory.user_id', 'user_inventory.asset_id'], name='fk_inventory_grants_owner_inventory', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id', 'case_open_id'], ['case_opens.user_id', 'case_opens.id'], name='fk_inventory_grants_owner_open', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_inventory_grants')),
    sa.UniqueConstraint('case_open_id', name=op.f('uq_inventory_grants_case_open_id')),
    sa.UniqueConstraint('user_id', 'event_key', name='uq_inventory_grants_user_event')
    )

    op.execute("""CREATE FUNCTION aurameme_opening_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pool case_loot_tables%ROWTYPE; debit wallet_transactions%ROWTYPE;
        opening case_opens%ROWTYPE; earned bigint; current_cost bigint; case_slug text;
BEGIN
  IF TG_TABLE_NAME = 'case_opens' THEN
    SELECT * INTO pool FROM case_loot_tables WHERE id=NEW.loot_table_id;
    IF NOT FOUND OR NEW.earned_xp_at_open < pool.min_earned_xp
       OR (pool.max_earned_xp IS NOT NULL AND NEW.earned_xp_at_open >= pool.max_earned_xp) THEN
      RAISE EXCEPTION 'Opening must match its earned XP band' USING ERRCODE='23514';
    END IF;
    SELECT coalesce(sum(base_xp),0) INTO earned FROM aura_ledger WHERE user_id=NEW.user_id AND occurred_at<=NEW.created_at;
    IF NEW.earned_xp_at_open <> earned THEN
      RAISE EXCEPTION 'Opening earned XP snapshot must match signed base ledger' USING ERRCODE='23514';
    END IF;
    SELECT cost_khi_van,slug INTO current_cost,case_slug FROM case_definitions WHERE id=NEW.case_id;
    IF (NEW.is_daily_free AND case_slug <> 'common') OR (NOT NEW.is_daily_free AND NEW.cost_khi_van <> current_cost) THEN
      RAISE EXCEPTION 'Opening cost must match its server case' USING ERRCODE='23514';
    END IF;
    IF NEW.cost_khi_van > 0 THEN
      SELECT * INTO debit FROM wallet_transactions WHERE id=NEW.wallet_transaction_id;
      IF NOT FOUND OR debit.user_id<>NEW.user_id OR debit.policy_id<>pool.policy_id
         OR debit.reason<>'case_open' OR debit.delta_khi_van<>-NEW.cost_khi_van
         OR debit.event_key<>'case:'||NEW.id::text OR debit.created_at<>NEW.created_at THEN
        RAISE EXCEPTION 'Opening debit must match its owner cost policy and receipt' USING ERRCODE='23514';
      END IF;
    END IF;
  ELSIF NEW.source_type = 'case_open' THEN
    SELECT * INTO opening FROM case_opens WHERE id=NEW.case_open_id;
    IF NOT FOUND OR NEW.user_id<>opening.user_id OR NEW.asset_id<>opening.reward_asset_id
       OR NEW.quantity<>1 OR NEW.event_key<>'case:'||opening.id::text
       OR NEW.policy_id<>(SELECT policy_id FROM case_loot_tables WHERE id=opening.loot_table_id)
       OR NEW.granted_at<>opening.created_at THEN
      RAISE EXCEPTION 'Case grant must match its opening result' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END
$$""")
    op.execute("CREATE TRIGGER case_opens_immutable BEFORE UPDATE OR DELETE ON case_opens FOR EACH ROW EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER case_opens_no_truncate BEFORE TRUNCATE ON case_opens FOR EACH STATEMENT EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER case_opens_binding BEFORE INSERT ON case_opens FOR EACH ROW EXECUTE FUNCTION aurameme_opening_guard()")
    op.execute("CREATE TRIGGER inventory_grants_immutable BEFORE UPDATE OR DELETE ON inventory_grants FOR EACH ROW EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER inventory_grants_no_truncate BEFORE TRUNCATE ON inventory_grants FOR EACH STATEMENT EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER inventory_grants_binding BEFORE INSERT ON inventory_grants FOR EACH ROW EXECUTE FUNCTION aurameme_opening_guard()")


def downgrade():
    connection = op.get_bind()
    tables = sorted(("users", "roles", "user_roles", "profiles", "auth_sessions", "categories",
        "media_uploads", "posts", "comments", "contact_messages", "admin_audit_logs", "post_reactions",
        "post_bookmarks", "reward_policy_versions", "user_progress", "aura_ledger", "wallets", "wallet_transactions", "daily_checkins", "asset_items", "user_inventory", "user_equipment", "case_definitions", "case_loot_tables", "case_loot_rarities", "case_pool_items", "case_opens", "inventory_grants"))
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql("LOCK TABLE " + ", ".join("public." + name for name in tables) + " IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql("SELECT 1 FROM public." + name + " LIMIT 1").first() is not None for name in tables):
        raise RuntimeError("Refusing downgrade of nonempty tables; preserve data and review first.")
    op.execute("DROP TRIGGER case_opens_immutable ON case_opens")
    op.execute("DROP TRIGGER case_opens_no_truncate ON case_opens")
    op.execute("DROP TRIGGER case_opens_binding ON case_opens")
    op.execute("DROP TRIGGER inventory_grants_immutable ON inventory_grants")
    op.execute("DROP TRIGGER inventory_grants_no_truncate ON inventory_grants")
    op.execute("DROP TRIGGER inventory_grants_binding ON inventory_grants")
    op.execute("DROP FUNCTION aurameme_opening_guard()")
    op.drop_table('inventory_grants')
    op.drop_index('uq_case_opens_daily_free',table_name='case_opens')
    op.drop_index('ix_case_opens_user_created_id',table_name='case_opens')
    op.drop_table('case_opens')
