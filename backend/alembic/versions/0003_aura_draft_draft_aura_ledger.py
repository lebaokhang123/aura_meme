"""draft_aura_ledger

Revision ID: 0003_aura_draft
Revises: 0002_interactions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003_aura_draft'
down_revision = '0002_interactions'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('reward_policy_versions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('effective_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("jsonb_typeof(config_json) = 'object'", name=op.f('ck_reward_policy_versions_config_object')),
    sa.CheckConstraint("status IN ('draft','published','retired')", name=op.f('ck_reward_policy_versions_status')),
    sa.CheckConstraint('version > 0', name=op.f('ck_reward_policy_versions_version')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_reward_policy_versions_created_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reward_policy_versions')),
    sa.UniqueConstraint('version', name=op.f('uq_reward_policy_versions_version'))
    )
    op.create_table('user_progress',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('aura_xp_earned', sa.BigInteger(), nullable=False),
    sa.Column('aura_xp_bonus', sa.BigInteger(), nullable=False),
    sa.Column('aura_xp_total', sa.BigInteger(), sa.Computed('aura_xp_earned + aura_xp_bonus', persisted=True), nullable=False),
    sa.Column('level_cached', sa.Integer(), nullable=False),
    sa.Column('fair_level_cached', sa.Integer(), nullable=False),
    sa.Column('streak_days', sa.Integer(), nullable=False),
    sa.Column('last_checkin_day', sa.Date(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('aura_xp_earned >= 0 AND aura_xp_bonus >= 0', name=op.f('ck_user_progress_xp_nonnegative')),
    sa.CheckConstraint('level_cached >= 1 AND fair_level_cached >= 1 AND streak_days >= 0', name=op.f('ck_user_progress_progress_bounds')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_progress_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_user_progress'))
    )
    op.create_index('ix_user_progress_earned_user', 'user_progress', [sa.literal_column('aura_xp_earned DESC'), 'user_id'], unique=False)
    op.create_table('aura_ledger',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('event_key', sa.Text(), nullable=False),
    sa.Column('event_type', sa.Text(), nullable=False),
    sa.Column('source_actor_id', sa.Uuid(), nullable=True),
    sa.Column('source_post_id', sa.Uuid(), nullable=True),
    sa.Column('source_comment_id', sa.Uuid(), nullable=True),
    sa.Column('policy_id', sa.Uuid(), nullable=False),
    sa.Column('base_xp', sa.BigInteger(), nullable=False),
    sa.Column('bonus_xp', sa.BigInteger(), nullable=False),
    sa.Column('tier_at_event', sa.Text(), nullable=False),
    sa.Column('multiplier_at_event', sa.SmallInteger(), nullable=False),
    sa.Column('reverses_id', sa.Uuid(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("(event_type = 'reversal') = (reverses_id IS NOT NULL) AND (reverses_id IS NULL OR reverses_id <> id)", name=op.f('ck_aura_ledger_reversal_reference')),
    sa.CheckConstraint("(event_type IN ('post','reaction','comment','checkin') AND base_xp >= 0 AND bonus_xp = base_xp * (multiplier_at_event - 1) AND ((tier_at_event='FREE' AND multiplier_at_event=1) OR (tier_at_event='PLUS' AND multiplier_at_event=2) OR (tier_at_event='PRIME' AND multiplier_at_event=3))) OR (event_type='adjustment' AND base_xp >= 0 AND bonus_xp=0 AND multiplier_at_event=1) OR (event_type='reversal' AND base_xp <= 0 AND bonus_xp <= 0)", name=op.f('ck_aura_ledger_deltas')),
    sa.CheckConstraint("event_type IN ('post','reaction','comment','checkin','adjustment','reversal')", name=op.f('ck_aura_ledger_event_type')),
    sa.CheckConstraint("tier_at_event IN ('FREE','PLUS','PRIME') AND multiplier_at_event IN (1,2,3)", name=op.f('ck_aura_ledger_tier')),
    sa.CheckConstraint('base_xp <> 0 OR bonus_xp <> 0', name=op.f('ck_aura_ledger_nonzero')),
    sa.ForeignKeyConstraint(['policy_id'], ['reward_policy_versions.id'], name=op.f('fk_aura_ledger_policy_id_reward_policy_versions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['source_actor_id'], ['users.id'], name=op.f('fk_aura_ledger_source_actor_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['source_comment_id'], ['comments.id'], name=op.f('fk_aura_ledger_source_comment_id_comments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['source_post_id'], ['posts.id'], name=op.f('fk_aura_ledger_source_post_id_posts'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id', 'reverses_id'], ['aura_ledger.user_id', 'aura_ledger.id'], name='fk_aura_ledger_owner_reversal', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_aura_ledger_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_aura_ledger')),
    sa.UniqueConstraint('reverses_id', name=op.f('uq_aura_ledger_reverses_id')),
    sa.UniqueConstraint('user_id', 'event_key', name='uq_aura_ledger_user_event'),
    sa.UniqueConstraint('user_id', 'id', name='uq_aura_ledger_user_id_id')
    )
    op.create_index('ix_aura_ledger_occurred_user', 'aura_ledger', ['occurred_at', 'user_id'], unique=False, postgresql_include=['base_xp'])
    op.create_index('ix_aura_ledger_user_occurred_id', 'aura_ledger', ['user_id', 'occurred_at', 'id'], unique=False)

    op.execute("CREATE FUNCTION aurameme_immutable_ledger() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Committed reward history is append-only.' USING ERRCODE = '23514'; END $$")
    op.execute("CREATE FUNCTION aurameme_immutable_policy() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF OLD.status = 'draft' THEN IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW; END IF; IF TG_OP = 'UPDATE' AND OLD.status = 'published' AND NEW.status = 'retired' AND (to_jsonb(NEW) - 'status') = (to_jsonb(OLD) - 'status') THEN RETURN NEW; END IF; RAISE EXCEPTION 'Published policy snapshots are immutable.' USING ERRCODE = '23514'; END $$")
    op.execute("CREATE TRIGGER aura_ledger_immutable BEFORE UPDATE OR DELETE ON aura_ledger FOR EACH ROW EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER reward_policy_immutable BEFORE UPDATE OR DELETE ON reward_policy_versions FOR EACH ROW EXECUTE FUNCTION aurameme_immutable_policy()")

    op.execute("CREATE TRIGGER aura_ledger_no_truncate BEFORE TRUNCATE ON aura_ledger FOR EACH STATEMENT EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.execute("CREATE TRIGGER reward_policy_no_truncate BEFORE TRUNCATE ON reward_policy_versions FOR EACH STATEMENT EXECUTE FUNCTION aurameme_immutable_ledger()")


def downgrade():
    connection = op.get_bind()
    tables = sorted(("users", "roles", "user_roles", "profiles", "auth_sessions", "categories",
        "media_uploads", "posts", "comments", "contact_messages", "admin_audit_logs", "post_reactions",
        "post_bookmarks", "reward_policy_versions", "user_progress", "aura_ledger"))
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql("LOCK TABLE " + ", ".join("public." + name for name in tables) + " IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql("SELECT 1 FROM public." + name + " LIMIT 1").first() is not None for name in tables):
        raise RuntimeError("Refusing downgrade of nonempty tables; preserve data and review first.")
    op.execute("DROP TRIGGER aura_ledger_no_truncate ON aura_ledger")
    op.execute("DROP TRIGGER reward_policy_no_truncate ON reward_policy_versions")
    op.execute("DROP TRIGGER aura_ledger_immutable ON aura_ledger")
    op.execute("DROP TRIGGER reward_policy_immutable ON reward_policy_versions")
    op.execute("DROP FUNCTION aurameme_immutable_ledger()")
    op.execute("DROP FUNCTION aurameme_immutable_policy()")
    op.drop_index('ix_aura_ledger_user_occurred_id', table_name='aura_ledger')
    op.drop_index('ix_aura_ledger_occurred_user', table_name='aura_ledger', postgresql_include=['base_xp'])
    op.drop_table('aura_ledger')
    op.drop_index('ix_user_progress_earned_user', table_name='user_progress')
    op.drop_table('user_progress')
    op.drop_table('reward_policy_versions')
