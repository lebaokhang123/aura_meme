"""Six standard reactions and comment reactions; no reward or data rewrite.

Revision ID: 0010_social_reactions
Revises: 0009_vault_open
"""
from alembic import op
import sqlalchemy as sa

revision="0010_social_reactions"
down_revision="0009_vault_open"
branch_labels=None
depends_on=None
SIX="reaction_type IN ('like','love','laugh','fire','sad','angry')"

def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    op.drop_constraint(op.f("ck_post_reactions_reaction_type"),"post_reactions",type_="check")
    op.create_check_constraint(op.f("ck_post_reactions_reaction_type"),"post_reactions",SIX)
    op.create_table("comment_reactions",
        sa.Column("comment_id",sa.Uuid(),nullable=False),
        sa.Column("user_id",sa.Uuid(),nullable=False),
        sa.Column("reaction_type",sa.Text(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.PrimaryKeyConstraint("comment_id","user_id",name=op.f("pk_comment_reactions")),
        sa.ForeignKeyConstraint(["comment_id"],["comments.id"],ondelete="RESTRICT",name=op.f("fk_comment_reactions_comment_id_comments")),
        sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="RESTRICT",name=op.f("fk_comment_reactions_user_id_users")),
        sa.CheckConstraint(SIX,name=op.f("ck_comment_reactions_reaction_type")))
    op.create_index("ix_comment_reactions_comment_type","comment_reactions",["comment_id","reaction_type"])
    op.create_index("ix_comment_reactions_user_id","comment_reactions",["user_id"])

def downgrade():
    connection=op.get_bind()
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql("SET LOCAL statement_timeout = '60s'")
    connection.exec_driver_sql("LOCK TABLE post_reactions, comment_reactions IN ACCESS EXCLUSIVE MODE")
    comments=connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM comment_reactions)"))
    new_kinds=connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM post_reactions WHERE reaction_type NOT IN ('like','laugh','fire'))"))
    if comments or new_kinds:
        raise RuntimeError("Refusing downgrade: comment reactions or new reaction types would be lost.")
    op.drop_table("comment_reactions")
    op.drop_constraint(op.f("ck_post_reactions_reaction_type"),"post_reactions",type_="check")
    op.create_check_constraint(op.f("ck_post_reactions_reaction_type"),"post_reactions","reaction_type IN ('like','laugh','fire')")
