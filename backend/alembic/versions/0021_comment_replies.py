"""Add single-level comment replies (parent_comment_id, reply_to_comment_id, reply_to_user_id).

Revision ID: 0021_comment_replies
Revises: 0020_follow_notifications
"""
from alembic import op
import sqlalchemy as sa


revision = '0021_comment_replies'
down_revision = '0020_follow_notifications'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column('comments', sa.Column('parent_comment_id', sa.Uuid(), nullable=True))
    op.add_column('comments', sa.Column('reply_to_comment_id', sa.Uuid(), nullable=True))
    op.add_column('comments', sa.Column('reply_to_user_id', sa.Uuid(), nullable=True))

    op.create_foreign_key(
        'fk_comments_parent_comment_id_comments', 'comments', 'comments',
        ['parent_comment_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_comments_reply_to_comment_id_comments', 'comments', 'comments',
        ['reply_to_comment_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_comments_reply_to_user_id_users', 'comments', 'users',
        ['reply_to_user_id'], ['id'], ondelete='SET NULL',
    )

    op.create_check_constraint(
        op.f('ck_comments_no_self_parent'), 'comments',
        'parent_comment_id IS NULL OR parent_comment_id <> id',
    )
    op.create_check_constraint(
        op.f('ck_comments_no_self_reply_to'), 'comments',
        'reply_to_comment_id IS NULL OR reply_to_comment_id <> id',
    )
    op.create_check_constraint(
        op.f('ck_comments_reply_parent_pair'), 'comments',
        '(parent_comment_id IS NULL) = (reply_to_comment_id IS NULL)',
    )

    op.create_index('ix_comments_parent_comment_id', 'comments', ['parent_comment_id'])
    op.create_index(
        'ix_comments_post_parent_created', 'comments',
        ['post_id', 'parent_comment_id', 'created_at', 'id'],
    )


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT 1 FROM comments WHERE parent_comment_id IS NOT NULL LIMIT 1")).first() is not None:
        raise RuntimeError("Refusing downgrade: comment replies exist; preserve data or remove replies first.")

    op.drop_index('ix_comments_post_parent_created', table_name='comments')
    op.drop_index('ix_comments_parent_comment_id', table_name='comments')

    op.drop_constraint(op.f('ck_comments_reply_parent_pair'), 'comments', type_='check')
    op.drop_constraint(op.f('ck_comments_no_self_reply_to'), 'comments', type_='check')
    op.drop_constraint(op.f('ck_comments_no_self_parent'), 'comments', type_='check')

    op.drop_constraint('fk_comments_reply_to_user_id_users', 'comments', type_='foreignkey')
    op.drop_constraint('fk_comments_reply_to_comment_id_comments', 'comments', type_='foreignkey')
    op.drop_constraint('fk_comments_parent_comment_id_comments', 'comments', type_='foreignkey')

    op.drop_column('comments', 'reply_to_user_id')
    op.drop_column('comments', 'reply_to_comment_id')
    op.drop_column('comments', 'parent_comment_id')
