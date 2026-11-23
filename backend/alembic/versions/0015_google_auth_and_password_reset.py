"""Add OAuth identities (Google) and one-time password reset tokens."""
from alembic import op
import sqlalchemy as sa

revision = "0015_google_auth_and_password_reset"
down_revision = "0014_premium_sandbox"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    # Alembic's default VARCHAR(32) cannot store this revision identifier.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE text")
    op.create_table(
        "user_oauth_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_sub", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider IN ('google')", name=op.f("ck_user_oauth_identities_provider")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_oauth_identities_user_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_user_oauth_identities"),
        sa.UniqueConstraint("provider", "provider_sub", name="uq_user_oauth_identities_provider_sub"),
    )
    op.create_index("ix_user_oauth_identities_user_id", "user_oauth_identities", ["user_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_password_reset_tokens_user_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_created", "password_reset_tokens", ["user_id", "created_at"])


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_index("ix_password_reset_tokens_user_created", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_user_oauth_identities_user_id", table_name="user_oauth_identities")
    op.drop_table("user_oauth_identities")
