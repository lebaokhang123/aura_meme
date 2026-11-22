"""Add notifications schema for user personal inbox and interactions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_notifications"
down_revision = "0012_aura_v1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedupe_key", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], name=op.f("fk_notifications_recipient_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name=op.f("fk_notifications_actor_user_id_users"), ondelete="SET NULL"),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_notifications_dedupe_key")),
        sa.CheckConstraint("type IN ('reaction','comment','moderation','announcement')", name=op.f("ck_notifications_notification_type")),
        sa.CheckConstraint("target_type IN ('post','comment','system')", name=op.f("ck_notifications_notification_target_type")),
    )
    op.create_index("ix_notifications_recipient_created", "notifications", ["recipient_user_id", "created_at"])
    op.create_index("ix_notifications_recipient_read", "notifications", ["recipient_user_id", "read_at"])


def downgrade():
    connection=op.get_bind()
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    tables=sorted(sa.inspect(connection).get_table_names(schema="public"))
    connection.exec_driver_sql("LOCK TABLE "+", ".join('public."'+name.replace('"','""')+'"' for name in tables)+" IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql('SELECT 1 FROM public."'+name.replace('"','""')+'" LIMIT 1').first() for name in tables if name!="alembic_version"):
        raise RuntimeError("Refusing downgrade of nonempty Aura schema; preserve data and review first.")
    op.drop_index("ix_notifications_recipient_read", table_name="notifications")
    op.drop_index("ix_notifications_recipient_created", table_name="notifications")
    op.drop_table("notifications")
