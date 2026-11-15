"""Aura V1 durable claims and XP-only receipts; preserve all legacy history."""
from alembic import op
import sqlalchemy as sa

revision="0012_aura_v1"
down_revision="0011_vault_v1"
branch_labels=None
depends_on=None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table("aura_reward_events",
        sa.Column("id",sa.Uuid(),nullable=False),sa.Column("event_key",sa.Text(),nullable=False),
        sa.Column("kind",sa.Text(),nullable=False),sa.Column("actor_id",sa.Uuid(),nullable=False),
        sa.Column("post_id",sa.Uuid(),nullable=False),sa.Column("comment_id",sa.Uuid(),nullable=True),
        sa.Column("policy_id",sa.Uuid(),nullable=False),sa.Column("effective_day",sa.Date(),nullable=False),
        sa.Column("occurred_at",sa.DateTime(timezone=True),nullable=False),
        sa.PrimaryKeyConstraint("id",name=op.f("pk_aura_reward_events")),
        sa.UniqueConstraint("event_key",name=op.f("uq_aura_reward_events_event_key")),
        sa.CheckConstraint("kind IN ('post','reaction','comment')",name=op.f("ck_aura_reward_events_kind")),
        sa.CheckConstraint("(kind='comment')=(comment_id IS NOT NULL)",name=op.f("ck_aura_reward_events_comment_binding")),
        sa.CheckConstraint("effective_day = ((occurred_at AT TIME ZONE 'Asia/Ho_Chi_Minh') - interval '7 hours')::date",name=op.f("ck_aura_reward_events_effective_day")),
        *[sa.ForeignKeyConstraint([column],[target],name=op.f("fk_aura_reward_events_"+column+"_"+target.split(".")[0]),ondelete="RESTRICT") for column,target in (("actor_id","users.id"),("post_id","posts.id"),("comment_id","comments.id"),("policy_id","reward_policy_versions.id"))])
    for column in ("post_id","actor_id","comment_id"):op.create_index("ix_aura_reward_events_"+column,"aura_reward_events",[column])
    for suffix,event in (("immutable","UPDATE OR DELETE"),("no_truncate","TRUNCATE")):
        mode="ROW" if suffix=="immutable" else "STATEMENT"
        op.execute(f"CREATE TRIGGER aura_reward_events_{suffix} BEFORE {event} ON aura_reward_events FOR EACH {mode} EXECUTE FUNCTION aurameme_immutable_ledger()")
    op.add_column("daily_checkins",sa.Column("reward_mode",sa.Text(),nullable=False,server_default=sa.text("'legacy'")))
    op.alter_column("daily_checkins","wallet_transaction_id",existing_type=sa.Uuid(),nullable=True)
    op.create_check_constraint(op.f("ck_daily_checkins_reward_mode"),"daily_checkins","(reward_mode='legacy' AND wallet_transaction_id IS NOT NULL) OR (reward_mode='aura_v1' AND wallet_transaction_id IS NULL)")


def downgrade():
    connection=op.get_bind()
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    tables=sorted(sa.inspect(connection).get_table_names(schema="public"))
    connection.exec_driver_sql("LOCK TABLE "+", ".join('public."'+name.replace('"','""')+'"' for name in tables)+" IN ACCESS EXCLUSIVE MODE")
    if any(connection.exec_driver_sql('SELECT 1 FROM public."'+name.replace('"','""')+'" LIMIT 1').first() for name in tables if name!="alembic_version"):
        raise RuntimeError("Refusing downgrade of nonempty Aura schema; preserve data and review first.")
    op.drop_constraint(op.f("ck_daily_checkins_reward_mode"),"daily_checkins",type_="check")
    op.alter_column("daily_checkins","wallet_transaction_id",existing_type=sa.Uuid(),nullable=False)
    op.drop_column("daily_checkins","reward_mode")
    op.execute("DROP TRIGGER aura_reward_events_no_truncate ON aura_reward_events")
    op.execute("DROP TRIGGER aura_reward_events_immutable ON aura_reward_events")
    for column in ("post_id","actor_id","comment_id"):op.drop_index("ix_aura_reward_events_"+column,table_name="aura_reward_events")
    op.drop_table("aura_reward_events")
