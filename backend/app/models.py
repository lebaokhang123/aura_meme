"""Implemented schema; business services live in their feature modules."""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Computed, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, MetaData, SmallInteger, Text, UniqueConstraint, Uuid, false, select, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, column_property, mapped_column


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
        CheckConstraint("reaction_type IN ('like','love','laugh','fire','sad','angry')", name="reaction_type"),
        Index("ix_post_reactions_user_created_post", "user_id", "created_at", "post_id"),
    )


class CommentReaction(Base):
    __tablename__ = "comment_reactions"
    comment_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("comments.id", ondelete="RESTRICT"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    reaction_type: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("reaction_type IN ('like','love','laugh','fire','sad','angry')", name="reaction_type"),
        Index("ix_comment_reactions_comment_type", "comment_id", "reaction_type"),
        Index("ix_comment_reactions_user_id", "user_id"),
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


class Wallet(Base):
    __tablename__ = "wallets"
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    khi_van_balance: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("khi_van_balance >= 0", name="balance_nonnegative"),)


class CaseOpen(Base):
    __tablename__ = "case_opens"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    request_key: Mapped[str] = mapped_column(Text)
    case_id: Mapped[UUID] = mapped_column(Uuid)
    loot_table_id: Mapped[UUID] = mapped_column(Uuid)
    reward_asset_id: Mapped[UUID] = mapped_column(Uuid)
    earned_xp_at_open: Mapped[int] = mapped_column(BigInteger)
    cost_khi_van: Mapped[int] = mapped_column(BigInteger)
    wallet_transaction_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True)
    is_daily_free: Mapped[bool] = mapped_column(Boolean)
    effective_day: Mapped[date] = mapped_column(Date)
    decision_trace: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "request_key", name="uq_case_opens_user_request"),
        UniqueConstraint("user_id", "id", name="uq_case_opens_user_id_id"),
        ForeignKeyConstraint(["case_id", "loot_table_id"], ["case_loot_tables.case_id", "case_loot_tables.id"], ondelete="RESTRICT", name="fk_case_opens_case_pool"),
        ForeignKeyConstraint(["loot_table_id", "reward_asset_id"], ["case_pool_items.loot_table_id", "case_pool_items.asset_id"], ondelete="RESTRICT", name="fk_case_opens_pool_reward"),
        ForeignKeyConstraint(["user_id", "wallet_transaction_id"], ["wallet_transactions.user_id", "wallet_transactions.id"], ondelete="RESTRICT", name="fk_case_opens_owner_debit"),
        CheckConstraint("earned_xp_at_open >= 0 AND cost_khi_van >= 0", name="nonnegative"),
        CheckConstraint("(cost_khi_van=0 AND wallet_transaction_id IS NULL) OR (cost_khi_van>0 AND wallet_transaction_id IS NOT NULL)", name="debit_required"),
        CheckConstraint("NOT is_daily_free OR cost_khi_van=0", name="free_cost"),
        CheckConstraint("effective_day = ((created_at AT TIME ZONE 'Asia/Ho_Chi_Minh') - interval '7 hours')::date", name="effective_day"),
        CheckConstraint("jsonb_typeof(decision_trace)='object'", name="trace_object"),
        Index("uq_case_opens_daily_free", "user_id", "case_id", "effective_day", unique=True, postgresql_where=text("is_daily_free")),
        Index("ix_case_opens_user_created_id", "user_id", "created_at", "id"),
    )


class InventoryGrant(Base):
    __tablename__ = "inventory_grants"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    asset_id: Mapped[UUID] = mapped_column(Uuid)
    event_key: Mapped[str] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(Text)
    case_open_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True)
    policy_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("reward_policy_versions.id", ondelete="RESTRICT"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_inventory_grants_user_event"),
        ForeignKeyConstraint(["user_id", "asset_id"], ["user_inventory.user_id", "user_inventory.asset_id"], ondelete="RESTRICT", name="fk_inventory_grants_owner_inventory"),
        ForeignKeyConstraint(["user_id", "case_open_id"], ["case_opens.user_id", "case_opens.id"], ondelete="RESTRICT", name="fk_inventory_grants_owner_open"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("source_type IN ('case_open','weekly_streak','level','admin')", name="source_type"),
        CheckConstraint("(source_type='case_open')=(case_open_id IS NOT NULL)", name="case_reference"),
    )


class CaseDefinition(Base):
    __tablename__ = "case_definitions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    label: Mapped[str] = mapped_column(Text)
    cost_khi_van: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("cost_khi_van >= 0", name="cost_nonnegative"),
        CheckConstraint("status IN ('draft','active','retired')", name="status"),
        CheckConstraint("btrim(slug) <> '' AND btrim(label) <> ''", name="nonempty"),
    )


class CaseLootTable(Base):
    __tablename__ = "case_loot_tables"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    case_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("case_definitions.id", ondelete="RESTRICT"))
    odds_version: Mapped[int] = mapped_column(Integer)
    band_no: Mapped[int] = mapped_column(SmallInteger)
    min_earned_xp: Mapped[int] = mapped_column(BigInteger)
    max_earned_xp: Mapped[int | None] = mapped_column(BigInteger)
    policy_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("reward_policy_versions.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(Text)
    active_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("case_id", "odds_version", "band_no", name="uq_case_loot_tables_case_version_band"),
        UniqueConstraint("case_id", "id", name="uq_case_loot_tables_case_id_id"),
        CheckConstraint("odds_version > 0 AND band_no > 0 AND min_earned_xp >= 0", name="positive_version_band"),
        CheckConstraint("max_earned_xp IS NULL OR max_earned_xp > min_earned_xp", name="range"),
        CheckConstraint("status IN ('draft','published','retired')", name="status"),
        Index("ix_case_loot_tables_case_status_from", "case_id", "status", "active_from"),
    )


class CaseLootRarity(Base):
    __tablename__ = "case_loot_rarities"
    loot_table_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("case_loot_tables.id", ondelete="RESTRICT"), primary_key=True)
    rarity: Mapped[str] = mapped_column(Text, primary_key=True)
    weight_bps: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint("rarity IN ('D','C','B','A','S')", name="rarity"),
        CheckConstraint("weight_bps BETWEEN 0 AND 10000", name="weight_bps"),
    )


class CasePoolItem(Base):
    __tablename__ = "case_pool_items"
    loot_table_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    asset_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    rarity: Mapped[str] = mapped_column(Text)
    item_weight: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(["loot_table_id", "rarity"], ["case_loot_rarities.loot_table_id", "case_loot_rarities.rarity"], ondelete="RESTRICT", name="fk_case_pool_items_bucket"),
        ForeignKeyConstraint(["asset_id", "rarity"], ["asset_items.id", "asset_items.rarity"], ondelete="RESTRICT", name="fk_case_pool_items_asset_rarity"),
        CheckConstraint("item_weight > 0", name="item_weight"),
    )


class UserInventory(Base):
    __tablename__ = "user_inventory"
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    asset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("asset_items.id", ondelete="RESTRICT"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("quantity >= 0", name="quantity_nonnegative"),)


class UserEquipment(Base):
    __tablename__ = "user_equipment"
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    slot_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    asset_id: Mapped[UUID] = mapped_column(Uuid)
    equipped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "asset_id"], ["user_inventory.user_id", "user_inventory.asset_id"], ondelete="RESTRICT", name="fk_user_equipment_owner_asset"),
        ForeignKeyConstraint(["asset_id", "slot_kind"], ["asset_items.id", "asset_items.kind"], ondelete="RESTRICT", name="fk_user_equipment_asset_kind"),
        CheckConstraint("slot_kind IN ('avatar','frame','icon','effect')", name="slot_kind"),
    )


class AssetItem(Base):
    __tablename__ = "asset_items"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    collection: Mapped[str] = mapped_column(Text)
    rarity: Mapped[str] = mapped_column(Text)
    media_key: Mapped[str] = mapped_column(Text)
    source_rights: Mapped[dict] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("id", "kind", name="uq_asset_items_id_kind"),
        UniqueConstraint("id", "rarity", name="uq_asset_items_id_rarity"),
        CheckConstraint("kind IN ('avatar','frame','icon','effect','generator')", name="kind"),
        CheckConstraint("rarity IN ('D','C','B','A','S')", name="rarity"),
        CheckConstraint("btrim(slug) <> '' AND btrim(media_key) <> '' AND btrim(collection) <> ''", name="nonempty"),
        CheckConstraint("jsonb_typeof(source_rights) = 'object'", name="rights_object"),
        CheckConstraint("NOT active OR coalesce(source_rights->>'review_status' = 'approved', false)", name="active_rights"),
    )


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("wallets.user_id", ondelete="RESTRICT"))
    event_key: Mapped[str] = mapped_column(Text)
    delta_khi_van: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text)
    policy_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("reward_policy_versions.id", ondelete="RESTRICT"))
    reverses_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_wallet_transactions_user_event"),
        UniqueConstraint("user_id", "id", name="uq_wallet_transactions_user_id_id"),
        ForeignKeyConstraint(["user_id", "reverses_id"], ["wallet_transactions.user_id", "wallet_transactions.id"], ondelete="RESTRICT", name="fk_wallet_transactions_owner_reversal"),
        CheckConstraint("delta_khi_van <> 0", name="nonzero"),
        CheckConstraint("reason IN ('checkin','case_open','generator','adjustment','reversal')", name="reason"),
        CheckConstraint("(reason = 'reversal') = (reverses_id IS NOT NULL) AND (reverses_id IS NULL OR reverses_id <> id)", name="reversal_reference"),
        CheckConstraint("(reason NOT IN ('checkin','generator') OR delta_khi_van > 0) AND (reason <> 'case_open' OR delta_khi_van < 0)", name="sign"),
        Index("ix_wallet_transactions_user_created_id", "user_id", "created_at", "id"),
    )


class DailyCheckin(Base):
    __tablename__ = "daily_checkins"
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    effective_day: Mapped[date] = mapped_column(Date, primary_key=True)
    aura_ledger_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    wallet_transaction_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "aura_ledger_id"], ["aura_ledger.user_id", "aura_ledger.id"], ondelete="RESTRICT", name="fk_daily_checkins_owner_aura"),
        ForeignKeyConstraint(["user_id", "wallet_transaction_id"], ["wallet_transactions.user_id", "wallet_transactions.id"], ondelete="RESTRICT", name="fk_daily_checkins_owner_wallet"),
        CheckConstraint("effective_day = ((claimed_at AT TIME ZONE 'Asia/Ho_Chi_Minh') - interval '7 hours')::date", name="effective_day"),
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
    # Read with the profile so author lists do not issue one inventory query per row.
    equipped_avatar_id = column_property(select(AssetItem.id).join(
        UserEquipment, UserEquipment.asset_id == AssetItem.id).join(UserInventory,
        (UserInventory.asset_id == AssetItem.id) & (UserInventory.user_id == UserEquipment.user_id)).where(
        UserEquipment.user_id == user_id, UserEquipment.slot_kind == "avatar", AssetItem.kind == "avatar",
        UserInventory.quantity > 0, AssetItem.active.is_(True),
        AssetItem.source_rights["review_status"].astext == "approved").correlate_except(
        AssetItem, UserEquipment, UserInventory).scalar_subquery())

    show_streak: Mapped[bool] = mapped_column(Boolean, server_default=false())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "avatar_media_id"], ["media_uploads.owner_id", "media_uploads.id"],
                             name="fk_profiles_avatar_owner", ondelete="RESTRICT", match="SIMPLE"),
        ForeignKeyConstraint(["user_id", "cover_media_id"], ["media_uploads.owner_id", "media_uploads.id"],
                             name="fk_profiles_cover_owner", ondelete="RESTRICT", match="SIMPLE"),
        CheckConstraint("birth_year IS NULL OR birth_year BETWEEN 1900 AND 9999", name="birth_year"),
    )

    @property
    def avatar_url(self):
        return f"/api/v1/catalog/assets/{self.equipped_avatar_id}" if self.equipped_avatar_id is not None else None


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
