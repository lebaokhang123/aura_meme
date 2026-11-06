"""checkin_wallet_ledger

Revision ID: 0005_checkin
Revises: 0004_wallet_read
"""
from alembic import op
import sqlalchemy as sa


revision = '0005_checkin'
down_revision = '0004_wallet_read'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('wallet_transactions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('event_key', sa.Text(), nullable=False),
    sa.Column('delta_khi_van', sa.BigInteger(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('policy_id', sa.Uuid(), nullable=False),
    sa.Column('reverses_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("(reason = 'reversal') = (reverses_id IS NOT NULL) AND (reverses_id IS NULL OR reverses_id <> id)", name=op.f('ck_wallet_transactions_reversal_reference')),
    sa.CheckConstraint("(reason NOT IN ('checkin','generator') OR delta_khi_van > 0) AND (reason <> 'case_open' OR delta_khi_van < 0)", name=op.f('ck_wallet_transactions_sign')),
    sa.CheckConstraint("reason IN ('checkin','case_open','generator','adjustment','reversal')", name=op.f('ck_wallet_transactions_reason')),
    sa.CheckConstraint('delta_khi_van <> 0', name=op.f('ck_wallet_transactions_nonzero')),
    sa.ForeignKeyConstraint(['policy_id'], ['reward_policy_versions.id'], name=op.f('fk_wallet_transactions_policy_id_reward_policy_versions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id', 'reverses_id'], ['wallet_transactions.user_id', 'wallet_transactions.id'], name='fk_wallet_transactions_owner_reversal', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['wallets.user_id'], name=op.f('fk_wallet_transactions_user_id_wallets'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_wallet_transactions')),
    sa.UniqueConstraint('reverses_id', name=op.f('uq_wallet_transactions_reverses_id')),
    sa.UniqueConstraint('user_id', 'event_key', name='uq_wallet_transactions_user_event'),
    sa.UniqueConstraint('user_id', 'id', name='uq_wallet_transactions_user_id_id')
    )
    op.create_index('ix_wallet_transactions_user_created_id', 'wallet_transactions', ['user_id', 'created_at', 'id'], unique=False)
    op.create_table('daily_checkins',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('effective_day', sa.Date(), nullable=False),
    sa.Column('aura_ledger_id', sa.Uuid(), nullable=False),
    sa.Column('wallet_transaction_id', sa.Uuid(), nullable=False),
    sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("effective_day = ((claimed_at AT TIME ZONE 'Asia/Ho_Chi_Minh') - interval '7 hours')::date", name=op.f('ck_daily_checkins_effective_day')),
    sa.ForeignKeyConstraint(['user_id', 'aura_ledger_id'], ['aura_ledger.user_id', 'aura_ledger.id'], name='fk_daily_checkins_owner_aura', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id', 'wallet_transaction_id'], ['wallet_transactions.user_id', 'wallet_transactions.id'], name='fk_daily_checkins_owner_wallet', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_daily_checkins_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('user_id', 'effective_day', name=op.f('pk_daily_checkins')),
    sa.UniqueConstraint('aura_ledger_id', name=op.f('uq_daily_checkins_aura_ledger_id')),
    sa.UniqueConstraint('wallet_transaction_id', name=op.f('uq_daily_checkins_wallet_transaction_id'))
    )

    op.execute("CREATE TRIGGER wallet_transactions_immutable BEFORE UPDATE OR DELETE ON wallet_transactions FOR EACH ROW EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER wallet_transactions_no_truncate BEFORE TRUNCATE ON wallet_transactions FOR EACH STATEMENT EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER daily_checkins_immutable BEFORE UPDATE OR DELETE ON daily_checkins FOR EACH ROW EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER daily_checkins_no_truncate BEFORE TRUNCATE ON daily_checkins FOR EACH STATEMENT EXECUTE FUNCTION aurameme_immutable_ledger()")


def downgrade():
    connection = op.get_bind()
    tables = sorted(("users", "roles", "user_roles", "profiles", "auth_sessions", "categories",
        "media_uploads", "posts", "comments", "contact_messages", "admin_audit_logs", "post_reactions",
        "post_bookmarks", "reward_policy_versions", "user_progress", "aura_ledger", "wallets", "wallet_transactions", "daily_checkins"))
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql("LOCK TABLE " + ", ".join("public." + name for name in tables) + " IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql("SELECT 1 FROM public." + name + " LIMIT 1").first() is not None for name in tables):
        raise RuntimeError("Refusing downgrade of nonempty tables; preserve data and review first.")
    op.execute("DROP TRIGGER wallet_transactions_immutable ON wallet_transactions")
    op.execute("DROP TRIGGER wallet_transactions_no_truncate ON wallet_transactions")
    op.execute("DROP TRIGGER daily_checkins_immutable ON daily_checkins")
    op.execute("DROP TRIGGER daily_checkins_no_truncate ON daily_checkins")
    op.drop_table('daily_checkins')
    op.drop_index('ix_wallet_transactions_user_created_id', table_name='wallet_transactions')
    op.drop_table('wallet_transactions')
