"""Implemented schema; business services live in their feature modules."""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Computed, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, MetaData, SmallInteger, Text, UniqueConstraint, Uuid, false, select, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, column_property, mapped_column
from app.catalog_rights import reviewed_source_rights_sql


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
    meme_asset_id: Mapped[UUID | None] = mapped_column(Uuid, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(['user_id', 'meme_asset_id'], ['user_inventory.user_id', 'user_inventory.asset_id'], ondelete='RESTRICT', name='fk_post_reactions_owner_meme'),
        CheckConstraint("(reaction_type='meme')=(meme_asset_id IS NOT NULL)", name='meme_reference'),
        CheckConstraint("reaction_type IN ('like','love','laugh','fire','sad','angry','meme')", name="reaction_type"),
        Index("ix_post_reactions_user_created_post", "user_id", "created_at", "post_id"),
    )


class CommentReaction(Base):
    __tablename__ = "comment_reactions"
    comment_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("comments.id", ondelete="RESTRICT"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    reaction_type: Mapped[str] = mapped_column(Text)
    meme_asset_id: Mapped[UUID | None] = mapped_column(Uuid, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(['user_id', 'meme_asset_id'], ['user_inventory.user_id', 'user_inventory.asset_id'], ondelete='RESTRICT', name='fk_comment_reactions_owner_meme'),
        CheckConstraint("(reaction_type='meme')=(meme_asset_id IS NOT NULL)", name='meme_reference'),
        CheckConstraint("reaction_type IN ('like','love','laugh','fire','sad','angry','meme')", name="reaction_type"),
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


class AuraRewardEvent(Base):
    __tablename__ = "aura_reward_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_key: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    post_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("posts.id", ondelete="RESTRICT"))
    comment_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("comments.id", ondelete="RESTRICT"))
    policy_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("reward_policy_versions.id", ondelete="RESTRICT"))
    effective_day: Mapped[date] = mapped_column(Date)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("kind IN ('post','reaction','comment')", name="kind"),
        CheckConstraint("(kind='comment')=(comment_id IS NOT NULL)", name="comment_binding"),
        CheckConstraint("effective_day = ((occurred_at AT TIME ZONE 'Asia/Ho_Chi_Minh') - interval '7 hours')::date", name="effective_day"),
        Index("ix_aura_reward_events_post_id", "post_id"),
        Index("ix_aura_reward_events_actor_id", "actor_id"),
        Index("ix_aura_reward_events_comment_id", "comment_id"),
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
    reward_rarity: Mapped[str | None] = mapped_column(Text)
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
        CheckConstraint("reward_rarity IS NULL OR reward_rarity IN ('D','C','B','A','S')", name="reward_rarity"),
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
    runtime_kind: Mapped[str | None] = mapped_column(Text, deferred=True)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("cost_khi_van >= 0", name="cost_nonnegative"),
        CheckConstraint("runtime_kind IS NULL OR runtime_kind IN ('avatar','background')", name="runtime_kind"),
        CheckConstraint("runtime_kind IS NULL OR cost_khi_van=0", name="runtime_free"),
        Index("uq_case_definitions_runtime_kind", "runtime_kind", unique=True, postgresql_where=text("runtime_kind IS NOT NULL")),
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
    asset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("asset_items.id", ondelete="RESTRICT", name="fk_case_pool_items_asset_id"), primary_key=True)
    rarity: Mapped[str] = mapped_column(Text)
    item_weight: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(["loot_table_id", "rarity"], ["case_loot_rarities.loot_table_id", "case_loot_rarities.rarity"], ondelete="RESTRICT", name="fk_case_pool_items_bucket"),
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
        CheckConstraint("slot_kind IN ('avatar','frame','icon','effect','background')", name="slot_kind"),
    )


class AssetItem(Base):
    __tablename__ = "asset_items"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    collection: Mapped[str] = mapped_column(Text)
    rarity: Mapped[str] = mapped_column(Text)
    media_key: Mapped[str] = mapped_column(Text)
    # Deferred columns preserve baseline reads before the separately approved migration.
    display_name: Mapped[str | None] = mapped_column(Text, deferred=True)
    effect_key: Mapped[str | None] = mapped_column(Text, deferred=True)
    source_rights: Mapped[dict] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT", name="fk_asset_items_deleted_by_users"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("id", "kind", name="uq_asset_items_id_kind"),
        UniqueConstraint("id", "rarity", name="uq_asset_items_id_rarity"),
        CheckConstraint("kind IN ('avatar','frame','icon','effect','generator','background')", name="kind"),
        CheckConstraint("display_name IS NULL OR btrim(display_name) <> ''", name="display_name"),
        CheckConstraint("effect_key IS NULL OR (kind='background' AND effect_key IN ('violet-base','lucian-363','lucian-352-deep-sea','lucian-226','lucian-330'))", name="effect_key"),
        CheckConstraint("rarity IN ('D','C','B','A','S')", name="rarity"),
        CheckConstraint("btrim(slug) <> '' AND btrim(media_key) <> '' AND btrim(collection) <> ''", name="nonempty"),
        CheckConstraint("jsonb_typeof(source_rights) = 'object'", name="rights_object"),
        CheckConstraint("NOT active OR coalesce(source_rights->>'review_status' = 'approved', false)", name="active_rights"),
        CheckConstraint("deleted_at IS NULL OR NOT active", name="deleted_inactive"),
        Index("ix_asset_items_deleted_at", "deleted_at"),
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
    wallet_transaction_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True)
    reward_mode: Mapped[str] = mapped_column(Text, default="legacy", server_default=text("'legacy'"))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("(reward_mode='legacy' AND wallet_transaction_id IS NOT NULL) OR (reward_mode='aura_v1' AND wallet_transaction_id IS NULL)", name="reward_mode"),
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
        reviewed_source_rights_sql(AssetItem.source_rights)).correlate_except(
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


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    recipient_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_notifications_recipient_created", "recipient_user_id", "created_at"),
        Index("ix_notifications_recipient_read", "recipient_user_id", "read_at"),
        UniqueConstraint("dedupe_key", name="uq_notifications_dedupe_key"),
        CheckConstraint("type IN ('reaction','comment','moderation','announcement')", name="notification_type"),
        CheckConstraint("target_type IN ('post','comment','system')", name="notification_target_type"),
    )


class SubscriptionOrder(Base):
    __tablename__ = "subscription_orders"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    order_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_txn_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_response_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    payment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_subscription_orders_user_created", "user_id", created_at.desc()),
        Index("ix_subscription_orders_order_code", "order_code", unique=True),
        CheckConstraint("tier IN ('plus', 'prime')", name="tier"),
        CheckConstraint("status IN ('pending', 'success', 'failed', 'cancelled', 'expired')", name="status"),
        CheckConstraint("provider IN ('sandbox_simulated', 'vnpay_sandbox', 'paypal_sandbox', 'unselected')", name="provider"),
    )


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    order_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("subscription_orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_user_subscriptions_user_id", "user_id", unique=True),
        Index("ix_user_subscriptions_expires", "expires_at"),
        CheckConstraint("tier IN ('plus', 'prime')", name="tier"),
        CheckConstraint("status IN ('active', 'expired', 'cancelled')", name="status"),
    )


class UserOAuthIdentity(Base):
    __tablename__ = "user_oauth_identities"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_sub: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("provider IN ('google')", name="provider"),
        UniqueConstraint("provider", "provider_sub", name="uq_user_oauth_identities_provider_sub"),
        Index("ix_user_oauth_identities_user_id", "user_id"),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_password_reset_tokens_user_created", "user_id", "created_at"),
    )


class AccountVerification(Base):
    __tablename__ = "account_verifications"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_account_verifications_token_hash", "token_hash"),
    )


class UserFollow(Base):
    __tablename__ = "user_follows"
    follower_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    followee_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("follower_id != followee_id", name="ck_user_follows_no_self"),
        Index("ix_user_follows_followee_id", "followee_id"),
    )


DEMO_SCHEMA_HEAD = "0019_asset_lifecycle_tombstone"


def reviewed_metadata(revision):
    """Exact reviewed predecessor shapes; never mutate mapped runtime metadata."""
    if revision == DEMO_SCHEMA_HEAD:
        return Base.metadata
    if revision not in {'0009_vault_open','0010_social_reactions','0011_vault_v1','0012_aura_v1'}:
        raise ValueError('Unknown reviewed schema revision')
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    for table in Base.metadata.sorted_tables:
        if table.name in {'notifications', 'subscription_orders', 'user_subscriptions', 'user_oauth_identities', 'password_reset_tokens', 'account_verifications', 'user_follows'}:
            continue
        if revision != '0012_aura_v1' and table.name == 'aura_reward_events':
            continue
        if revision == '0009_vault_open' and table.name == 'comment_reactions':
            continue
        table.to_metadata(metadata)
    if revision == '0012_aura_v1':
        return metadata

    def remove_constraint(table, name):
        constraint = next(c for c in table.constraints if c.name == name)
        if isinstance(constraint, ForeignKeyConstraint):
            for foreign_key in constraint.elements:
                table.foreign_keys.remove(foreign_key)
                foreign_key.parent.foreign_keys.remove(foreign_key)
        table.constraints.remove(constraint)

    def remove_columns(table, names):
        # SQLAlchemy has no public removal API; only this detached clone is changed.
        for name in names:
            table._columns.remove(table.c[name])

    checkin = metadata.tables['daily_checkins']
    remove_constraint(checkin, 'ck_daily_checkins_reward_mode')
    remove_columns(checkin, ['reward_mode'])
    checkin.c.wallet_transaction_id.nullable = False
    if revision == '0011_vault_v1':
        return metadata

    for name in ('post_reactions','comment_reactions'):
        if name not in metadata.tables:
            continue
        table = metadata.tables[name]
        for constraint in ('fk_'+name+'_owner_meme','ck_'+name+'_meme_reference','ck_'+name+'_reaction_type'):
            remove_constraint(table, constraint)
        remove_columns(table, ['meme_asset_id'])
        kinds = "'like','laugh','fire'" if revision == '0009_vault_open' else "'like','love','laugh','fire','sad','angry'"
        table.append_constraint(CheckConstraint('reaction_type IN ('+kinds+')', name='reaction_type'))
    assets = metadata.tables['asset_items']
    for name in ('kind','display_name','effect_key'):
        remove_constraint(assets, 'ck_asset_items_'+name)
    remove_columns(assets, ['display_name','effect_key'])
    assets.append_constraint(CheckConstraint("kind IN ('avatar','frame','icon','effect','generator')", name='kind'))
    cases = metadata.tables['case_definitions']
    for name in ('runtime_kind','runtime_free'):
        remove_constraint(cases, 'ck_case_definitions_'+name)
    cases.indexes.remove(next(i for i in cases.indexes if i.name == 'uq_case_definitions_runtime_kind'))
    remove_columns(cases, ['runtime_kind'])
    equipment = metadata.tables['user_equipment']
    remove_constraint(equipment, 'ck_user_equipment_slot_kind')
    equipment.append_constraint(CheckConstraint("slot_kind IN ('avatar','frame','icon','effect')", name='slot_kind'))
    return metadata
