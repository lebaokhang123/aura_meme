"""P0 initial schema

Revision ID: 0001_p0
Revises: None
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_p0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('categories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('slug', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f('ck_categories_name_nonempty')),
        sa.CheckConstraint("slug = btrim(slug) AND slug = lower(slug) AND slug <> ''", name=op.f('ck_categories_slug_normalized')),
        sa.CheckConstraint("status IN ('active','hidden')", name=op.f('ck_categories_status')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_categories')),
        sa.UniqueConstraint('slug', name=op.f('uq_categories_slug'))
    )
    op.create_table('roles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.CheckConstraint("code IN ('USER','ADMIN')", name=op.f('ck_roles_code')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
        sa.UniqueConstraint('code', name=op.f('uq_roles_code'))
    )
    op.create_table('users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('username', sa.Text(), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("(status = 'deleted') = (deleted_at IS NOT NULL)", name=op.f('ck_users_deleted_at')),
        sa.CheckConstraint("email = btrim(email) AND email = lower(email) AND email <> ''", name=op.f('ck_users_email_normalized')),
        sa.CheckConstraint("status IN ('active','locked','deleted')", name=op.f('ck_users_status')),
        sa.CheckConstraint("username ~ '^[a-z0-9_]{3,32}$'", name=op.f('ck_users_username_format')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email')),
        sa.UniqueConstraint('username', name=op.f('uq_users_username'))
    )
    op.create_table('admin_audit_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('target_type', sa.Text(), nullable=False),
        sa.Column('target_id', sa.Text(), nullable=False),
        sa.Column('before_json', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
        sa.Column('after_json', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("btrim(action) <> '' AND btrim(target_type) <> '' AND btrim(target_id) <> ''", name=op.f('ck_admin_audit_logs_identity_nonempty')),
        sa.CheckConstraint('before_json IS NOT NULL OR after_json IS NOT NULL', name=op.f('ck_admin_audit_logs_snapshot_present')),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_admin_audit_logs_actor_id_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_admin_audit_logs'))
    )
    op.create_index(op.f('ix_admin_audit_logs_actor_id'), 'admin_audit_logs', ['actor_id'], unique=False)
    op.create_table('auth_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('expires_at > created_at', name=op.f('ck_auth_sessions_expires_after_created')),
        sa.CheckConstraint('revoked_at IS NULL OR revoked_at >= created_at', name=op.f('ck_auth_sessions_revoked_after_created')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_auth_sessions_user_id_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_sessions')),
        sa.UniqueConstraint('token_hash', name=op.f('uq_auth_sessions_token_hash'))
    )
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False)
    op.create_table('contact_messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("btrim(name) <> '' AND btrim(email) <> '' AND btrim(subject) <> '' AND btrim(body) <> ''", name=op.f('ck_contact_messages_fields_nonempty')),
        sa.CheckConstraint("status IN ('new','in_review','resolved')", name=op.f('ck_contact_messages_status')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_contact_messages_user_id_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_contact_messages'))
    )
    op.create_index(op.f('ix_contact_messages_user_id'), 'contact_messages', ['user_id'], unique=False)
    op.create_table('media_uploads',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('object_key', sa.Text(), nullable=False),
        sa.Column('mime', sa.Text(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mime IN ('image/jpeg','image/png','image/webp','image/gif')", name=op.f('ck_media_uploads_mime')),
        sa.CheckConstraint("status IN ('pending','ready','rejected','deleted')", name=op.f('ck_media_uploads_status')),
        sa.CheckConstraint('size_bytes > 0', name=op.f('ck_media_uploads_size_positive')),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_media_uploads_owner_id_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_media_uploads')),
        sa.UniqueConstraint('object_key', name=op.f('uq_media_uploads_object_key')),
        sa.UniqueConstraint('owner_id', 'id', name=op.f('uq_media_uploads_owner_id'))
    )
    op.create_table('user_roles',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('role_id', sa.Uuid(), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_user_roles_role_id_roles'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_roles_user_id_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('user_id', 'role_id', name=op.f('pk_user_roles'))
    )
    op.create_index(op.f('ix_user_roles_role_id'), 'user_roles', ['role_id'], unique=False)
    op.create_table('posts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.Column('category_id', sa.Uuid(), nullable=False),
        sa.Column('media_id', sa.Uuid(), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("(status = 'deleted') = (deleted_at IS NOT NULL)", name=op.f('ck_posts_deleted_at')),
        sa.CheckConstraint("btrim(content) <> '' OR media_id IS NOT NULL", name=op.f('ck_posts_content_or_media')),
        sa.CheckConstraint("btrim(title) <> ''", name=op.f('ck_posts_title_nonempty')),
        sa.CheckConstraint("status IN ('draft','published','hidden','deleted')", name=op.f('ck_posts_status')),
        sa.ForeignKeyConstraint(['author_id', 'media_id'], ['media_uploads.owner_id', 'media_uploads.id'], name='fk_posts_media_owner', ondelete='RESTRICT', match='SIMPLE'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('fk_posts_author_id_users'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], name=op.f('fk_posts_category_id_categories'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_posts'))
    )
    op.create_index('ix_posts_author_media', 'posts', ['author_id', 'media_id'], unique=False)
    op.create_index(op.f('ix_posts_category_id'), 'posts', ['category_id'], unique=False)
    op.create_table('profiles',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('birth_year', sa.SmallInteger(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('phone', sa.Text(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('avatar_media_id', sa.Uuid(), nullable=True),
        sa.Column('cover_media_id', sa.Uuid(), nullable=True),
        sa.Column('show_streak', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('birth_year IS NULL OR birth_year BETWEEN 1900 AND 9999', name=op.f('ck_profiles_birth_year')),
        sa.ForeignKeyConstraint(['user_id', 'avatar_media_id'], ['media_uploads.owner_id', 'media_uploads.id'], name='fk_profiles_avatar_owner', ondelete='RESTRICT', match='SIMPLE'),
        sa.ForeignKeyConstraint(['user_id', 'cover_media_id'], ['media_uploads.owner_id', 'media_uploads.id'], name='fk_profiles_cover_owner', ondelete='RESTRICT', match='SIMPLE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_profiles_user_id_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('user_id', name=op.f('pk_profiles'))
    )
    op.create_table('comments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('post_id', sa.Uuid(), nullable=False),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("(status = 'deleted') = (deleted_at IS NOT NULL)", name=op.f('ck_comments_deleted_at')),
        sa.CheckConstraint("btrim(body) <> ''", name=op.f('ck_comments_body_nonempty')),
        sa.CheckConstraint("status IN ('visible','hidden','deleted')", name=op.f('ck_comments_status')),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('fk_comments_author_id_users'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], name=op.f('fk_comments_post_id_posts'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_comments'))
    )
    op.create_index(op.f('ix_comments_author_id'), 'comments', ['author_id'], unique=False)
    op.create_index(op.f('ix_comments_post_id'), 'comments', ['post_id'], unique=False)


def downgrade():
    # Lock this revision's tables before checking rows so a concurrent write cannot be lost.
    tables = (
        'admin_audit_logs', 'auth_sessions', 'categories', 'comments', 'contact_messages',
        'media_uploads', 'posts', 'profiles', 'roles', 'user_roles', 'users',
    )
    connection = op.get_bind()
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql(
        'LOCK TABLE ' + ', '.join('public.' + table for table in tables) + ' IN ACCESS EXCLUSIVE MODE'
    )
    for table in tables:
        if connection.exec_driver_sql('SELECT 1 FROM public.' + table + ' LIMIT 1').first() is not None:
            raise RuntimeError('Refusing downgrade of nonempty P0 tables; preserve data and review first.')
    op.drop_index(op.f('ix_comments_post_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_author_id'), table_name='comments')
    op.drop_table('comments')
    op.drop_table('profiles')
    op.drop_index(op.f('ix_posts_category_id'), table_name='posts')
    op.drop_index('ix_posts_author_media', table_name='posts')
    op.drop_table('posts')
    op.drop_index(op.f('ix_user_roles_role_id'), table_name='user_roles')
    op.drop_table('user_roles')
    op.drop_table('media_uploads')
    op.drop_index(op.f('ix_contact_messages_user_id'), table_name='contact_messages')
    op.drop_table('contact_messages')
    op.drop_index(op.f('ix_auth_sessions_user_id'), table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_index(op.f('ix_admin_audit_logs_actor_id'), table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('categories')
