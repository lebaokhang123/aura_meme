"""Wallet read model required by the existing AuraProgress response, without issuance.

Revision ID: 0004_wallet_read
Revises: 0003_aura_draft
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_wallet_read"
down_revision = "0003_aura_draft"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("wallets",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("khi_van_balance", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("khi_van_balance >= 0", name=op.f("ck_wallets_balance_nonnegative")),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_wallets")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name=op.f("fk_wallets_user_id_users")))


def downgrade():
    connection = op.get_bind()
    tables = sorted(("users", "roles", "user_roles", "profiles", "auth_sessions", "categories",
        "media_uploads", "posts", "comments", "contact_messages", "admin_audit_logs", "post_reactions",
        "post_bookmarks", "reward_policy_versions", "user_progress", "aura_ledger", "wallets"))
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql("LOCK TABLE " + ", ".join("public." + name for name in tables) + " IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql("SELECT 1 FROM public." + name + " LIMIT 1").first() is not None for name in tables):
        raise RuntimeError("Refusing downgrade of nonempty tables; preserve data and review first.")
    op.drop_table("wallets")
