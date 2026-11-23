"""Standardize canonical metadata filenames for 70 Vault V1 Memes and 5 Backgrounds.

Revision ID: 0018_canonical_asset_filenames
Revises: 0017_user_follows
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0018_canonical_asset_filenames'
down_revision = '0017_user_follows'
branch_labels = None
depends_on = None

BG_MAP = {
    'violet-base': 'D_background_violet_base.png',
    'lucian-363': 'C_background_lucian_363.png',
    'lucian-352-deep-sea': 'B_background_lucian_352_deep_sea.png',
    'lucian-226': 'A_background_lucian_226.png',
    'lucian-330': 'S_background_lucian_330.png',
}


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    conn = op.get_bind()

    # 1. Backgrounds
    for ekey, fn in BG_MAP.items():
        conn.execute(sa.text("""
            UPDATE asset_items
            SET source_rights = jsonb_set(COALESCE(source_rights, '{}'::jsonb), '{canonical_filename}', :fn)
            WHERE kind = 'background' AND effect_key = :ekey
              AND NOT (COALESCE(source_rights, '{}'::jsonb) ? 'canonical_filename')
        """), {'fn': f'"{fn}"', 'ekey': ekey})

    # 2. 70 Memes by deterministic order per rarity
    for rank in ['S', 'A', 'B', 'C', 'D']:
        rows = conn.execute(sa.text("""
            SELECT id, media_key FROM asset_items
            WHERE kind = 'avatar' AND rarity = :rank
            ORDER BY created_at ASC, id ASC
        """), {'rank': rank}).fetchall()

        for idx, (asset_id, mkey) in enumerate(rows, 1):
            ext = 'png' if mkey and mkey.endswith('.png') else 'jpg'
            fn = f"{rank}_231126_{idx:03d}.{ext}"
            conn.execute(sa.text("""
                UPDATE asset_items
                SET source_rights = jsonb_set(COALESCE(source_rights, '{}'::jsonb), '{canonical_filename}', :fn)
                WHERE id = :id AND NOT (COALESCE(source_rights, '{}'::jsonb) ? 'canonical_filename')
            """), {'fn': f'"{fn}"', 'id': asset_id})


def downgrade():
    raise RuntimeError(
        "0018 cannot identify pre-existing canonical filenames. Restore a verified pre-0018 backup."
    )
