"""Add user_follows table for user following system."""
from alembic import op
import sqlalchemy as sa

revision = "0017_user_follows"
down_revision = "0016_account_email_verifications"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table(
        "user_follows",
        sa.Column("follower_id", sa.Uuid(), nullable=False),
        sa.Column("followee_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("follower_id", "followee_id", name="pk_user_follows"),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE", name="fk_user_follows_follower_id"),
        sa.ForeignKeyConstraint(["followee_id"], ["users.id"], ondelete="CASCADE", name="fk_user_follows_followee_id"),
        sa.CheckConstraint("follower_id != followee_id", name="ck_user_follows_no_self"),
    )
    op.create_index("ix_user_follows_followee_id", "user_follows", ["followee_id"])


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_index("ix_user_follows_followee_id", table_name="user_follows")
    op.drop_table("user_follows")
