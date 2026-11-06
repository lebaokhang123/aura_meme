"""P1 reaction and bookmark mechanics, without rewards.

Revision ID: 0002_interactions
Revises: 0001_p0
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_interactions"
down_revision = "0001_p0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("post_reactions",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reaction_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("reaction_type IN ('like','laugh','fire')", name=op.f("ck_post_reactions_reaction_type")),
        sa.PrimaryKeyConstraint("post_id", "user_id", name=op.f("pk_post_reactions")),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="RESTRICT", name=op.f("fk_post_reactions_post_id_posts")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name=op.f("fk_post_reactions_user_id_users")))
    op.create_index("ix_post_reactions_user_created_post", "post_reactions", ["user_id", "created_at", "post_id"])
    op.create_table("post_bookmarks",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("post_id", "user_id", name=op.f("pk_post_bookmarks")),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="RESTRICT", name=op.f("fk_post_bookmarks_post_id_posts")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name=op.f("fk_post_bookmarks_user_id_users")))
    op.create_index("ix_post_bookmarks_user_created_post", "post_bookmarks", ["user_id", sa.text("created_at DESC"), "post_id"])


def downgrade():
    # Refuse before dropping anything, including when a later P0 downgrade would refuse.
    connection = op.get_bind()
    tables = sorted(("users", "roles", "user_roles", "profiles", "auth_sessions", "categories",
        "media_uploads", "posts", "comments", "contact_messages", "admin_audit_logs",
        "post_reactions", "post_bookmarks"))
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql("LOCK TABLE " + ", ".join("public." + name for name in tables) + " IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql("SELECT 1 FROM public." + name + " LIMIT 1").first() is not None for name in tables):
        raise RuntimeError("Refusing downgrade of nonempty tables; preserve data and review first.")
    op.drop_table("post_bookmarks")
    op.drop_table("post_reactions")
