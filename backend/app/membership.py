from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from app.models import UserSubscription


def read_users_membership_tiers(db: Session, user_ids: set[UUID] | list[UUID], now: datetime) -> dict[UUID, str]:
    """Batch-reads active membership tiers for a set of user IDs without N+1 queries.
    Safely returns empty dict if table does not exist or has schema mismatch.
    """
    if not user_ids:
        return {}
    try:
        with db.begin_nested():
            rows = db.execute(
                select(UserSubscription.user_id, UserSubscription.tier)
                .where(
                    UserSubscription.user_id.in_(list(user_ids)),
                    UserSubscription.status == "active",
                    UserSubscription.expires_at > now,
                )
            ).all()
        return {uid: tier for uid, tier in rows if tier in {"plus", "prime"}}
    except ProgrammingError as exc:
        if getattr(exc.orig, "sqlstate", None) not in {"42P01", "42703"}:
            raise
        return {}
