"""Allow follow notification type and user target_type in notifications table.

Revision ID: 0020_follow_notifications
Revises: 0019_asset_lifecycle_tombstone
"""
from alembic import op
import sqlalchemy as sa


revision = '0020_follow_notifications'
down_revision = '0019_asset_lifecycle_tombstone'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_constraint('ck_notifications_notification_type', 'notifications', type_='check')
    op.create_check_constraint(
        'ck_notifications_notification_type', 'notifications',
        "type IN ('reaction','comment','moderation','announcement','follow')",
    )
    op.drop_constraint('ck_notifications_notification_target_type', 'notifications', type_='check')
    op.create_check_constraint(
        'ck_notifications_notification_target_type', 'notifications',
        "target_type IN ('post','comment','system','user')",
    )


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT 1 FROM notifications WHERE type = 'follow' OR target_type = 'user' LIMIT 1")).first() is not None:
        raise RuntimeError("Refusing downgrade: follow notifications exist; preserve data or remove follow rows first.")
    op.drop_constraint('ck_notifications_notification_type', 'notifications', type_='check')
    op.create_check_constraint(
        'ck_notifications_notification_type', 'notifications',
        "type IN ('reaction','comment','moderation','announcement')",
    )
    op.drop_constraint('ck_notifications_notification_target_type', 'notifications', type_='check')
    op.create_check_constraint(
        'ck_notifications_notification_target_type', 'notifications',
        "target_type IN ('post','comment','system')",
    )
