"""Authoritative AuraMeme Premium plan tiers and sandbox configurations."""
from dataclasses import dataclass
from typing import Literal

TierCode = Literal["plus", "prime"]
ProviderCode = Literal["sandbox_simulated", "vnpay_sandbox"]
OrderStatus = Literal["pending", "success", "failed", "cancelled", "expired"]
SubscriptionStatus = Literal["active", "expired", "cancelled"]


@dataclass(frozen=True)
class PlanDefinition:
    tier: TierCode
    name: str
    duration_days: int
    boost_multiplier: int
    amount_usd_cents: int
    amount_usd_formatted: str
    default_amount_vnd: int


def round_vnd_to_nearest_10k(amount: int | float) -> int:
    """Round VND amount to the nearest 10,000 VND (e.g., 156,345.333 -> 160,000, 125,000 -> 130,000)."""
    val = float(amount)
    remainder = val % 10000.0
    if remainder >= 5000.0:
        return int((val - remainder) + 10000)
    return int(val - remainder)


# Fixed authoritative plan definitions: Owner approved $5 (Plus) and $50 (Prime).
# VND pricing strictly adheres to the 10,000 VND rounding policy.
PLANS: dict[str, PlanDefinition] = {
    "plus": PlanDefinition(
        tier="plus",
        name="Aura Plus",
        duration_days=30,
        boost_multiplier=2,
        amount_usd_cents=500,
        amount_usd_formatted="$5",
        default_amount_vnd=round_vnd_to_nearest_10k(125000),  # 130,000 VND
    ),
    "prime": PlanDefinition(
        tier="prime",
        name="Aura Prime",
        duration_days=365,
        boost_multiplier=3,
        amount_usd_cents=5000,
        amount_usd_formatted="$50",
        default_amount_vnd=round_vnd_to_nearest_10k(1250000),  # 1,250,000 VND
    ),
}


def get_plan(tier: str) -> PlanDefinition:
    plan = PLANS.get(tier)
    if not plan:
        raise ValueError(f"Invalid plan tier: '{tier}'. Must be 'plus' or 'prime'.")
    return plan

