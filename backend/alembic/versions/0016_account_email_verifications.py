"""Add account_verifications table for registration email verification."""
from alembic import op
import sqlalchemy as sa

revision = "0016_account_email_verifications"
down_revision = "0015_google_auth_and_password_reset"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table(
        "account_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_account_verifications"),
        sa.UniqueConstraint("token_hash", name="uq_account_verifications_token_hash"),
        sa.UniqueConstraint("email", name="uq_account_verifications_email"),
        sa.UniqueConstraint("username", name="uq_account_verifications_username"),
    )
    op.create_index("ix_account_verifications_token_hash", "account_verifications", ["token_hash"])


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_index("ix_account_verifications_token_hash", table_name="account_verifications")
    op.drop_table("account_verifications")
