"""Session-owned, idempotent comment reactions; no Aura/XP writes."""
from uuid import UUID

from fastapi import APIRouter,Depends,Request
from pydantic import BaseModel
from sqlalchemy import delete,func,select
from sqlalchemy.dialects.postgresql import insert

from app.auth import CSRF_HEADER
from app.comments import lock_public_post
from app.blog import public_posts
from app.interactions import ERRORS,REACTION_TYPES,ReactionCounts,ReactionInput,ReactionType,interaction_reader
from app.models import Comment,CommentReaction,User,Profile,Post
from app.permissions import require_account_csrf
from app.security import AuthError

router=APIRouter(prefix="/api/v1/comments",tags=["Blog"])

class CommentReactionResult(ReactionInput):
    comment_id: UUID

class CommentInteractions(BaseModel):
    comment_id: UUID
    reaction_counts: ReactionCounts
    viewer_reaction: ReactionType | None

def visible_comment(comment_id):
    return select(Comment.id).join(User,User.id==Comment.author_id).join(Profile,Profile.user_id==User.id).where(
        Comment.id==comment_id,Comment.status=="visible",Comment.deleted_at.is_(None),
        User.status=="active",Comment.post_id.in_(public_posts().with_only_columns(Post.id)))

def lock_visible_comment(db,comment_id):
    post_id=db.scalar(select(Comment.post_id).where(Comment.id==comment_id))
    if post_id is None:raise AuthError(404,"NOT_FOUND","Comment not found.")
    lock_public_post(db,post_id)
    db.scalar(select(Comment.id).where(Comment.id==comment_id).with_for_update())
    if db.scalar(visible_comment(comment_id)) is None:raise AuthError(404,"NOT_FOUND","Comment not found.")

@router.put("/{comment_id}/reactions",response_model=CommentReactionResult,operation_id="setCommentReaction",
            responses=ERRORS,openapi_extra=CSRF_HEADER)
def set_comment_reaction(comment_id: UUID,payload: ReactionInput,request: Request,
                         account=Depends(require_account_csrf)):
    lock_visible_comment(account.db,comment_id)
    now=request.app.state.auth.now()
    statement=insert(CommentReaction).values(comment_id=comment_id,user_id=account.user.id,
        reaction_type=payload.reaction_type,created_at=now,updated_at=now)
    account.db.execute(statement.on_conflict_do_update(index_elements=["comment_id","user_id"],
        set_={"reaction_type":payload.reaction_type,"updated_at":now},
        where=CommentReaction.reaction_type!=payload.reaction_type))
    return CommentReactionResult(comment_id=comment_id,reaction_type=payload.reaction_type)

@router.delete("/{comment_id}/reactions",status_code=204,operation_id="removeCommentReaction",
               responses=ERRORS,openapi_extra=CSRF_HEADER)
def remove_comment_reaction(comment_id: UUID,account=Depends(require_account_csrf)):
    lock_visible_comment(account.db,comment_id)
    account.db.execute(delete(CommentReaction).where(CommentReaction.comment_id==comment_id,
                                                      CommentReaction.user_id==account.user.id))

@router.get("/{comment_id}/interactions",response_model=CommentInteractions,operation_id="getCommentInteractions",
            responses={s:ERRORS[s] for s in (401,404,422,429,500)},
            openapi_extra={"security":[{},{"sessionCookie":[]}]})
def get_comment_interactions(comment_id: UUID,reader=Depends(interaction_reader,scope="function")):
    db,viewer_id=reader
    counts=[select(func.count()).select_from(CommentReaction).join(User,User.id==CommentReaction.user_id).where(
        CommentReaction.comment_id==Comment.id,CommentReaction.reaction_type==kind,User.status=="active"
    ).correlate(Comment).scalar_subquery() for kind in REACTION_TYPES]
    reaction=select(CommentReaction.reaction_type).where(CommentReaction.comment_id==Comment.id,
        CommentReaction.user_id==viewer_id).correlate(Comment).scalar_subquery()
    row=db.execute(select(Comment.id,*counts,reaction).where(Comment.id.in_(visible_comment(comment_id)))).one_or_none()
    if row is None:raise AuthError(404,"NOT_FOUND","Comment not found.")
    return CommentInteractions(comment_id=row[0],reaction_counts=ReactionCounts(**dict(zip(REACTION_TYPES,row[1:7]))),
                               viewer_reaction=row[7])
