"""Free Vault V1 Exp award, atomic with its inventory grant and receipt.

The published free-Vault loot policy is the policy source for this award;
publication of a *separate* Aura social/check-in policy is not a prerequisite
for opening a valid chest. Never introduce XP bands into loot selection.

The caller already holds the shared Aura mutation advisory lock and the user
row lock via require_authenticated_user. Do not call this on receipt replays.
"""
from uuid import uuid4

from sqlalchemy import func, select

from app.aura_runtime import _state, _updated, unavailable
from app.aura_v1 import day_window
from app.models import AuraLedger, RewardPolicyVersion

VAULT_EXP_PER_OPEN = 2
VAULT_REWARDED_OPENS_PER_DAY = 100
VAULT_KEY_PREFIX = "vault-v1:case:"


def reward_amount(rewarded_today: int) -> int:
    """The first 100 successful openings *per effective day* earn +2 Exp."""
    if type(rewarded_today) is not int or rewarded_today < 0:
        raise ValueError("Rewarded openings must be a nonnegative integer.")
    return VAULT_EXP_PER_OPEN if rewarded_today < VAULT_REWARDED_OPENS_PER_DAY else 0


def award_vault_open(db, owner, opening, now, vault_policy_id) -> int:
    """Award Exp once for a NEW, committed-with-grant Vault V1 open.

    Invoked after _grant_item but before request transaction commit. Failures
    roll back CaseOpen, InventoryGrant, inventory balance and Exp together.
    Existing idempotency-key requests must bypass this function entirely.

    `vault_policy_id` comes from the validated, *published* DrawPool; no Aura
    social/check-in policy lookup is required or appropriate here.
    """
    if (opening.user_id != owner or opening.decision_trace.get("runtime") != "free-vault-v1"
            or opening.cost_khi_van != 0 or opening.created_at != now):
        unavailable("Vault reward identity or timestamp is inconsistent.")

    policy = db.get(RewardPolicyVersion, vault_policy_id)
    if (policy is None or policy.status != "published" or policy.effective_at > now
            or not isinstance(policy.config_json, dict)
            or policy.config_json.get("type") != "free-vault-v1"):
        unavailable("Published Vault policy is inconsistent.")

    event_key = VAULT_KEY_PREFIX + str(opening.id)
    existing = db.scalar(select(AuraLedger).where(AuraLedger.user_id == owner,
                                                 AuraLedger.event_key == event_key))
    if existing is not None:
        # Defensive: the request dispatcher avoids this branch for receipt
        # replays. An existing, malformed ledger row is never silently trusted.
        if (existing.event_type != "adjustment" or existing.base_xp != VAULT_EXP_PER_OPEN
                or existing.bonus_xp != 0 or existing.policy_id != vault_policy_id):
            unavailable("Stored Vault Exp award is inconsistent.")
        return 0

    _, start, end = day_window(now)  # 07:00 Asia/Ho_Chi_Minh boundary
    rewarded_today = int(db.scalar(select(func.count(AuraLedger.id)).where(
        AuraLedger.user_id == owner,
        AuraLedger.event_type == "adjustment",
        AuraLedger.event_key.startswith(VAULT_KEY_PREFIX),
        AuraLedger.base_xp > 0,
        AuraLedger.occurred_at >= start,
        AuraLedger.occurred_at < end,
    )) or 0)
    delta = reward_amount(rewarded_today)
    if delta == 0:
        # Opening and inventory still succeed. Do not create a zero-delta
        # ledger row; AuraLedger has a nonzero CHECK constraint.
        return 0

    # Do not call active_policy(): the Vault policy is already reviewed and
    # published, while Aura publication is independent. Preserve stringent
    # ledger/cache consistency checks and fail closed on corruption.
    state = _state(db, owner, now, initialize=True, locked=True)
    db.add(AuraLedger(
        id=uuid4(), user_id=owner, event_key=event_key,
        event_type="adjustment", source_actor_id=owner,
        source_post_id=None, source_comment_id=None,
        policy_id=vault_policy_id, base_xp=delta, bonus_xp=0,
        tier_at_event="FREE", multiplier_at_event=1,
        reverses_id=None, occurred_at=now,
    ))
    db.flush()
    _updated(db, state, delta, 0, now)
    return delta
