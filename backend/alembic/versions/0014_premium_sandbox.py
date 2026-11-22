"""Add subscription orders and user subscriptions for Premium sandbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_premium_sandbox"
down_revision = "0013_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table(
        "subscription_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_code", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_txn_id", sa.Text(), nullable=True),
        sa.Column("provider_response_code", sa.Text(), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("payment_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_orders")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_subscription_orders_user_id_users")),
        sa.UniqueConstraint("order_code", name=op.f("uq_subscription_orders_order_code")),
        sa.CheckConstraint("tier IN ('plus', 'prime')", name=op.f("ck_subscription_orders_tier")),
        sa.CheckConstraint("status IN ('pending', 'success', 'failed', 'cancelled', 'expired')", name=op.f("ck_subscription_orders_status")),
        sa.CheckConstraint("provider IN ('sandbox_simulated', 'vnpay_sandbox', 'paypal_sandbox', 'unselected')", name=op.f("ck_subscription_orders_provider")),
    )
    op.create_index("ix_subscription_orders_user_created", "subscription_orders", ["user_id", sa.text("created_at DESC")])
    op.create_index("ix_subscription_orders_order_code", "subscription_orders", ["order_code"], unique=True)

    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_subscriptions")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_subscriptions_user_id_users")),
        sa.ForeignKeyConstraint(["order_id"], ["subscription_orders.id"], name=op.f("fk_user_subscriptions_order_id_subscription_orders")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_subscriptions_user_id")),
        sa.CheckConstraint("tier IN ('plus', 'prime')", name=op.f("ck_user_subscriptions_tier")),
        sa.CheckConstraint("status IN ('active', 'expired', 'cancelled')", name=op.f("ck_user_subscriptions_status")),
    )
    op.create_index("ix_user_subscriptions_user_id", "user_subscriptions", ["user_id"], unique=True)
    op.create_index("ix_user_subscriptions_expires", "user_subscriptions", ["expires_at"])


def downgrade():
    connection=op.get_bind()
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    tables=sorted(sa.inspect(connection).get_table_names(schema="public"))
    connection.exec_driver_sql("LOCK TABLE "+", ".join('public."'+name.replace('"','""')+'"' for name in tables)+" IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql('SELECT 1 FROM public."'+name.replace('"','""')+'" LIMIT 1').first() for name in tables if name!="alembic_version"):
        raise RuntimeError("Refusing downgrade of nonempty Aura schema; preserve data and review first.")
    op.drop_index("ix_user_subscriptions_expires", table_name="user_subscriptions")
    op.drop_index("ix_user_subscriptions_user_id", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")
    op.drop_index("ix_subscription_orders_order_code", table_name="subscription_orders")
    op.drop_index("ix_subscription_orders_user_created", table_name="subscription_orders")
    op.drop_table("subscription_orders")
