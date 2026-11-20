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


# Fixed authoritative plan definitions: Owner approved $5 (Plus) and $50 (Prime)
PLANS: dict[str, PlanDefinition] = {
    "plus": PlanDefinition(
        tier="plus",
        name="Aura Plus",
        duration_days=30,
        boost_multiplier=2,
        amount_usd_cents=500,
        amount_usd_formatted="$5",
        default_amount_vnd=125000,
    ),
    "prime": PlanDefinition(
        tier="prime",
        name="Aura Prime",
        duration_days=365,
        boost_multiplier=3,
        amount_usd_cents=5000,
        amount_usd_formatted="$50",
        default_amount_vnd=1250000,
    ),
}


def get_plan(tier: str) -> PlanDefinition:
    plan = PLANS.get(tier)
    if not plan:
        raise ValueError(f"Invalid plan tier: '{tier}'. Must be 'plus' or 'prime'.")
    return plan
