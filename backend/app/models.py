"""Implemented schema; business services live in their feature modules."""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Computed, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, MetaData, SmallInteger, Text, UniqueConstraint, Uuid, false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "pk": "pk_%(table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "ix": "ix_%(table_name)s_%(column_0_name)s",
    })


class PostReaction(Base):
    __tablename__ = "post_reactions"
    post_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("posts.id", ondelete="RESTRICT"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    reaction_type: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("reaction_type IN ('like','laugh','fire')", name="reaction_type"),
        Index("ix_post_reactions_user_created_post", "user_id", "created_at", "post_id"),
    )


class PostBookmark(Base):
    __tablename__ = "post_bookmarks"
    post_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("posts.id", ondelete="RESTRICT"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_post_bookmarks_user_created_post", "user_id", created_at.desc(), "post_id"),)


class RewardPolicyVersion(Base):
    __tablename__ = "reward_policy_versions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    config_json: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("version > 0", name="version"),
        CheckConstraint("jsonb_typeof(config_json) = 'object'", name="config_object"),
        CheckConstraint("status IN ('draft','published','retired')", name="status"),
    )


class UserProgress(Base):
    __tablename__ = "user_progress"
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    aura_xp_earned: Mapped[int] = mapped_column(BigInteger)
    aura_xp_bonus: Mapped[int] = mapped_column(BigInteger)
    aura_xp_total: Mapped[int] = mapped_column(BigInteger, Computed("aura_xp_earned + aura_xp_bonus", persisted=True))
    level_cached: Mapped[int] = mapped_column(Integer)
    fair_level_cached: Mapped[int] = mapped_column(Integer)
    streak_days: Mapped[int] = mapped_column(Integer)
    last_checkin_day: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("aura_xp_earned >= 0 AND aura_xp_bonus >= 0", name="xp_nonnegative"),
        CheckConstraint("level_cached >= 1 AND fair_level_cached >= 1 AND streak_days >= 0", name="progress_bounds"),
        Index("ix_user_progress_earned_user", aura_xp_earned.desc(), "user_id"),
    )


class AuraLedger(Base):
    __tablename__ = "aura_ledger"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    event_key: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    source_actor_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    source_post_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("posts.id", ondelete="RESTRICT"))
    source_comment_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("comments.id", ondelete="RESTRICT"))
    policy_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("reward_policy_versions.id", ondelete="RESTRICT"))
    base_xp: Mapped[int] = mapped_column(BigInteger)
    bonus_xp: Mapped[int] = mapped_column(BigInteger)
    tier_at_event: Mapped[str] = mapped_column(Text)
    multiplier_at_event: Mapped[int] = mapped_column(SmallInteger)
    reverses_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_aura_ledger_user_event"),
        UniqueConstraint("user_id", "id", name="uq_aura_ledger_user_id_id"),
        ForeignKeyConstraint(["user_id", "reverses_id"], ["aura_ledger.user_id", "aura_ledger.id"], ondelete="RESTRICT", name="fk_aura_ledger_owner_reversal"),
        CheckConstraint("event_type IN ('post','reaction','comment','checkin','adjustment','reversal')", name="event_type"),
        CheckConstraint("tier_at_event IN ('FREE','PLUS','PRIME') AND multiplier_at_event IN (1,2,3)", name="tier"),
        CheckConstraint("(event_type = 'reversal') = (reverses_id IS NOT NULL) AND (reverses_id IS NULL OR reverses_id <> id)", name="reversal_reference"),
        CheckConstraint("base_xp <> 0 OR bonus_xp <> 0", name="nonzero"),
        CheckConstraint("(event_type IN ('post','reaction','comment','checkin') AND base_xp >= 0 AND bonus_xp = base_xp * (multiplier_at_event - 1) AND ((tier_at_event='FREE' AND multiplier_at_event=1) OR (tier_at_event='PLUS' AND multiplier_at_event=2) OR (tier_at_event='PRIME' AND multiplier_at_event=3))) OR (event_type='adjustment' AND base_xp >= 0 AND bonus_xp=0 AND multiplier_at_event=1) OR (event_type='reversal' AND base_xp <= 0 AND bonus_xp <= 0)", name="deltas"),
        Index("ix_aura_ledger_user_occurred_id", "user_id", "occurred_at", "id"),
        Index("ix_aura_ledger_occurred_user", "occurred_at", "user_id", postgresql_include=["base_xp"]),
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("username ~ '^[a-z0-9_]{3,32}$'", name="username_format"),
        CheckConstraint("email = btrim(email) AND email = lower(email) AND email <> ''", name="email_normalized"),
        CheckConstraint("status IN ('active','locked','deleted')", name="status"),
        CheckConstraint("(status = 'deleted') = (deleted_at IS NOT NULL)", name="deleted_at"),
    )


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str] = mapped_column(Text)
    __table_args__ = (CheckConstraint("code IN ('USER','ADMIN')", name="code"),)


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True, index=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MediaUpload(Base):
    __tablename__ = "media_uploads"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    object_key: Mapped[str] = mapped_column(Text, unique=True)
    mime: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("mime IN ('image/jpeg','image/png','image/webp','image/gif')", name="mime"),
        CheckConstraint("status IN ('pending','ready','rejected','deleted')", name="status"),
    )


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    birth_year: Mapped[int | None] = mapped_column(SmallInteger)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    avatar_media_id: Mapped[UUID | None] = mapped_column(Uuid)
    cover_media_id: Mapped[UUID | None] = mapped_column(Uuid)
    show_streak: Mapped[bool] = mapped_column(Boolean, server_default=false())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "avatar_media_id"], ["media_uploads.owner_id", "media_uploads.id"],
                             name="fk_profiles_avatar_owner", ondelete="RESTRICT", match="SIMPLE"),
        ForeignKeyConstraint(["user_id", "cover_media_id"], ["media_uploads.owner_id", "media_uploads.id"],
                             name="fk_profiles_cover_owner", ondelete="RESTRICT", match="SIMPLE"),
        CheckConstraint("birth_year IS NULL OR birth_year BETWEEN 1900 AND 9999", name="birth_year"),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="revoked_after_created"),
    )


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("slug = btrim(slug) AND slug = lower(slug) AND slug <> ''", name="slug_normalized"),
        CheckConstraint("btrim(name) <> ''", name="name_nonempty"),
        CheckConstraint("status IN ('active','hidden')", name="status"),
    )


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    media_id: Mapped[UUID | None] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["author_id", "media_id"], ["media_uploads.owner_id", "media_uploads.id"],
                             name="fk_posts_media_owner", ondelete="RESTRICT", match="SIMPLE"),
        Index("ix_posts_author_media", "author_id", "media_id"),
        CheckConstraint("btrim(title) <> ''", name="title_nonempty"),
        CheckConstraint("btrim(content) <> '' OR media_id IS NOT NULL", name="content_or_media"),
        CheckConstraint("status IN ('draft','published','hidden','deleted')", name="status"),
        CheckConstraint("(status = 'deleted') = (deleted_at IS NOT NULL)", name="deleted_at"),
    )


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    post_id: Mapped[UUID] = mapped_column(ForeignKey("posts.id", ondelete="RESTRICT"), index=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("btrim(body) <> ''", name="body_nonempty"),
        CheckConstraint("status IN ('visible','hidden','deleted')", name="status"),
        CheckConstraint("(status = 'deleted') = (deleted_at IS NOT NULL)", name="deleted_at"),
    )


class ContactMessage(Base):
    __tablename__ = "contact_messages"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("btrim(name) <> '' AND btrim(email) <> '' AND btrim(subject) <> '' AND btrim(body) <> ''", name="fields_nonempty"),
        CheckConstraint("status IN ('new','in_review','resolved')", name="status"),
    )


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str] = mapped_column(Text)
    target_id: Mapped[str] = mapped_column(Text)
    before_json: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    after_json: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("btrim(action) <> '' AND btrim(target_type) <> '' AND btrim(target_id) <> ''", name="identity_nonempty"),
        CheckConstraint("before_json IS NOT NULL OR after_json IS NOT NULL", name="snapshot_present"),
    )
