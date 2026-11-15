"""Add free Vault metadata; no seed, activation, grant or history changes.

Revision ID: 0011_vault_v1
Revises: 0010_social_reactions
"""
from alembic import op
import sqlalchemy as sa

revision = '0011_vault_v1'
down_revision = '0010_social_reactions'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column('asset_items', sa.Column('display_name', sa.Text(), nullable=True))
    op.add_column('asset_items', sa.Column('effect_key', sa.Text(), nullable=True))
    op.drop_constraint(op.f('ck_asset_items_kind'), 'asset_items', type_='check')
    op.create_check_constraint(op.f('ck_asset_items_kind'), 'asset_items', "kind IN ('avatar','frame','icon','effect','generator','background')")
    op.create_check_constraint(op.f('ck_asset_items_display_name'), 'asset_items', "display_name IS NULL OR btrim(display_name) <> ''")
    op.create_check_constraint(op.f('ck_asset_items_effect_key'), 'asset_items', "effect_key IS NULL OR (kind='background' AND effect_key IN ('violet-base','lucian-363','lucian-352-deep-sea','lucian-226','lucian-330'))")
    op.drop_constraint(op.f('ck_user_equipment_slot_kind'), 'user_equipment', type_='check')
    op.create_check_constraint(op.f('ck_user_equipment_slot_kind'), 'user_equipment', "slot_kind IN ('avatar','frame','icon','effect','background')")
    op.add_column('case_definitions', sa.Column('runtime_kind', sa.Text(), nullable=True))
    op.create_check_constraint(op.f('ck_case_definitions_runtime_kind'), 'case_definitions', "runtime_kind IS NULL OR runtime_kind IN ('avatar','background')")
    op.create_check_constraint(op.f('ck_case_definitions_runtime_free'), 'case_definitions', 'runtime_kind IS NULL OR cost_khi_van=0')
    op.create_index('uq_case_definitions_runtime_kind', 'case_definitions', ['runtime_kind'], unique=True, postgresql_where=sa.text('runtime_kind IS NOT NULL'))


    for table in ('post_reactions', 'comment_reactions'):
        op.add_column(table, sa.Column('meme_asset_id', sa.Uuid(), nullable=True))
        op.drop_constraint(op.f('ck_'+table+'_reaction_type'), table, type_='check')
        op.create_check_constraint(op.f('ck_'+table+'_reaction_type'), table, "reaction_type IN ('like','love','laugh','fire','sad','angry','meme')")
        op.create_check_constraint(op.f('ck_'+table+'_meme_reference'), table, "(reaction_type='meme')=(meme_asset_id IS NOT NULL)")
        op.create_foreign_key('fk_'+table+'_owner_meme', table, 'user_inventory', ['user_id','meme_asset_id'], ['user_id','asset_id'], ondelete='RESTRICT')
    op.execute("""CREATE FUNCTION aurameme_meme_reaction_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE amount integer; enabled boolean; review text; asset_kind text;
    BEGIN
      IF NEW.reaction_type <> 'meme' THEN NEW.meme_asset_id := NULL; END IF;
      IF NEW.meme_asset_id IS NOT NULL THEN
        SELECT i.quantity,a.active,a.source_rights->>'review_status',a.kind
          INTO amount,enabled,review,asset_kind
          FROM user_inventory i JOIN asset_items a ON a.id=i.asset_id
          WHERE i.user_id=NEW.user_id AND i.asset_id=NEW.meme_asset_id FOR SHARE OF i,a;
        IF NOT FOUND OR amount<=0 OR NOT enabled OR review IS DISTINCT FROM 'approved' OR asset_kind<>'avatar' THEN
          RAISE EXCEPTION 'Meme reactions require owned active approved avatar inventory' USING ERRCODE='23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$""")
    for table in ('post_reactions','comment_reactions'):
        op.execute('CREATE TRIGGER '+table+'_meme_guard BEFORE INSERT OR UPDATE ON '+table+' FOR EACH ROW EXECUTE FUNCTION aurameme_meme_reaction_guard()')


def downgrade():
    # Metadata and ownership must not disappear through a rollback.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute('LOCK TABLE asset_items, case_definitions, comment_reactions, post_reactions, user_equipment IN ACCESS EXCLUSIVE MODE')
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM asset_items WHERE kind='background' OR display_name IS NOT NULL OR effect_key IS NOT NULL)
         OR EXISTS (SELECT 1 FROM case_definitions WHERE runtime_kind IS NOT NULL)
         OR EXISTS (SELECT 1 FROM user_equipment WHERE slot_kind='background')
         OR EXISTS (SELECT 1 FROM post_reactions WHERE meme_asset_id IS NOT NULL)
         OR EXISTS (SELECT 1 FROM comment_reactions WHERE meme_asset_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Refusing downgrade with Vault V1 data; preserve rows and review first.';
      END IF;
    END $$""")
    for table in ('post_reactions','comment_reactions'):
        op.execute('DROP TRIGGER '+table+'_meme_guard ON '+table)
        op.drop_constraint('fk_'+table+'_owner_meme',table,type_='foreignkey')
        op.drop_constraint(op.f('ck_'+table+'_meme_reference'),table,type_='check')
        op.drop_constraint(op.f('ck_'+table+'_reaction_type'),table,type_='check')
        op.create_check_constraint(op.f('ck_'+table+'_reaction_type'),table,"reaction_type IN ('like','love','laugh','fire','sad','angry')")
        op.drop_column(table,'meme_asset_id')
    op.execute('DROP FUNCTION aurameme_meme_reaction_guard()')
    op.drop_index('uq_case_definitions_runtime_kind', table_name='case_definitions')
    op.drop_constraint(op.f('ck_case_definitions_runtime_free'), 'case_definitions', type_='check')
    op.drop_constraint(op.f('ck_case_definitions_runtime_kind'), 'case_definitions', type_='check')
    op.drop_column('case_definitions', 'runtime_kind')
    op.drop_constraint(op.f('ck_user_equipment_slot_kind'), 'user_equipment', type_='check')
    op.create_check_constraint(op.f('ck_user_equipment_slot_kind'), 'user_equipment', "slot_kind IN ('avatar','frame','icon','effect')")
    op.drop_constraint(op.f('ck_asset_items_effect_key'), 'asset_items', type_='check')
    op.drop_constraint(op.f('ck_asset_items_display_name'), 'asset_items', type_='check')
    op.drop_constraint(op.f('ck_asset_items_kind'), 'asset_items', type_='check')
    op.create_check_constraint(op.f('ck_asset_items_kind'), 'asset_items', "kind IN ('avatar','frame','icon','effect','generator')")
    op.drop_column('asset_items', 'effect_key')
    op.drop_column('asset_items', 'display_name')
