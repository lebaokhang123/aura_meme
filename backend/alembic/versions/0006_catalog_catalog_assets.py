"""catalog assets

Revision ID: 0006_catalog
Revises: 0005_checkin
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0006_catalog'
down_revision = '0005_checkin'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('asset_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('slug', sa.Text(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('collection', sa.Text(), nullable=False),
    sa.Column('rarity', sa.Text(), nullable=False),
    sa.Column('media_key', sa.Text(), nullable=False),
    sa.Column('source_rights', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("NOT active OR coalesce(source_rights->>'review_status' = 'approved', false)", name=op.f('ck_asset_items_active_rights')),
    sa.CheckConstraint("btrim(slug) <> '' AND btrim(media_key) <> '' AND btrim(collection) <> ''", name=op.f('ck_asset_items_nonempty')),
    sa.CheckConstraint("jsonb_typeof(source_rights) = 'object'", name=op.f('ck_asset_items_rights_object')),
    sa.CheckConstraint("kind IN ('avatar','frame','icon','effect','generator')", name=op.f('ck_asset_items_kind')),
    sa.CheckConstraint("rarity IN ('D','C','B','A','S')", name=op.f('ck_asset_items_rarity')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_asset_items')),
    sa.UniqueConstraint('id', 'kind', name='uq_asset_items_id_kind'),
    sa.UniqueConstraint('id', 'rarity', name='uq_asset_items_id_rarity'),
    sa.UniqueConstraint('slug', name=op.f('uq_asset_items_slug'))
    )


def downgrade():
    connection = op.get_bind()
    tables = sorted(("users", "roles", "user_roles", "profiles", "auth_sessions", "categories",
        "media_uploads", "posts", "comments", "contact_messages", "admin_audit_logs", "post_reactions",
        "post_bookmarks", "reward_policy_versions", "user_progress", "aura_ledger", "wallets", "wallet_transactions", "daily_checkins", "asset_items"))
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql("LOCK TABLE " + ", ".join("public." + name for name in tables) + " IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql("SELECT 1 FROM public." + name + " LIMIT 1").first() is not None for name in tables):
        raise RuntimeError("Refusing downgrade of nonempty tables; preserve data and review first.")
    op.drop_table('asset_items')
