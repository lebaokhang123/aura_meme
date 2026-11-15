"""Serialize reward mutations before authentication acquires user locks."""
from sqlalchemy import text

AURA_MUTATION_LOCK = 4707471486433248581


def lock_aura_mutation(db):
    # shortcut: global gate limits write throughput; use ordered participant locks when measured load requires it.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": AURA_MUTATION_LOCK})
