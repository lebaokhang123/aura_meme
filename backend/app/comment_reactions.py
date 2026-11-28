"""Session-owned, idempotent comment reactions; no Aura/XP writes."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter,Depends,Query,Request
from pydantic import BaseModel
from sqlalchemy import and_,delete,exists,func,or_,select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased

from app.auth import CSRF_HEADER
from app.comments import lock_public_post
from app.blog import public_posts
from app.interactions import ERRORS,REACTION_TYPES,ReactionCounts,ReactionInput,ReactionType,interaction_reader,list_target_reactions
from app.models import Comment,CommentReaction,User,Profile,Post
from app.permissions import require_account_csrf
from app.security import AuthError
from app.blog_schemas import CommentInteractions,ReactionListPage,ReactionState

router=APIRouter(prefix="/api/v1/comments",tags=["Blog"])

class CommentReactionResult(ReactionInput):
    comment_id: UUID

def visible_comment(comment_id):
    parent = aliased(Comment)
    parent_user = aliased(User)
    parent_ok = or_(
        Comment.parent_comment_id.is_(None),
        exists(
            select(parent.id)
            .join(parent_user, parent_user.id == parent.author_id)
            .where(
                parent.id == Comment.parent_comment_id,
                parent.status == "visible",
                parent.deleted_at.is_(None),
                parent_user.status == "active",
            )
        ),
    )
    return select(Comment.id).join(User,User.id==Comment.author_id).join(Profile,Profile.user_id==User.id).where(
        Comment.id==comment_id,Comment.status=="visible",Comment.deleted_at.is_(None),
        User.status=="active",parent_ok,Comment.post_id.in_(public_posts().with_only_columns(Post.id)))

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
    from app.meme_reactions import set_owned_reaction
    set_owned_reaction(account,request,CommentReaction,'comment_id',comment_id,payload,now)
    comment=account.db.get(Comment,comment_id)
    if comment is not None and comment.author_id!=account.user.id:
        from app.notifications import create_notification
        create_notification(
            account.db,
            recipient_user_id=comment.author_id,
            type="reaction",
            target_type="comment",
            target_id=comment_id,
            actor_user_id=account.user.id,
            payload={
                "reaction_type": payload.reaction_type,
                "post_id": str(comment.post_id),
                "comment_body": (comment.body or "")[:120],
            },
            dedupe_key=f"comment-reaction:{comment_id}:{account.user.id}",
            now=now,
        )
    return CommentReactionResult(comment_id=comment_id,**payload.model_dump())

@router.delete("/{comment_id}/reactions",status_code=204,operation_id="removeCommentReaction",
               responses=ERRORS,openapi_extra=CSRF_HEADER)
def remove_comment_reaction(comment_id: UUID,account=Depends(require_account_csrf)):
    lock_visible_comment(account.db,comment_id)
    account.db.execute(delete(CommentReaction).where(CommentReaction.comment_id==comment_id,
                                                      CommentReaction.user_id==account.user.id))

@router.get("/{comment_id}/reactions",response_model=ReactionListPage,operation_id="listCommentReactions",
            responses={s:ERRORS[s] for s in (404,422,429,500)})
def list_comment_reactions(
    comment_id: UUID,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    reaction_type: ReactionType | Literal["meme"] | None = Query(None),
    meme_asset_id: UUID | None = Query(None),
):
    with request.app.state.auth_session_factory() as db:
        if db.scalar(visible_comment(comment_id)) is None:
            raise AuthError(404, "NOT_FOUND", "Comment not found.")
        return list_target_reactions(
            db,
            CommentReaction,
            comment_id,
            page=page,
            page_size=page_size,
            reaction_type=reaction_type,
            meme_asset_id=meme_asset_id,
            request=request,
        )


def read_comment_states(comment_ids: list[UUID], db, viewer_id, request) -> dict[UUID, CommentInteractions]:
    """Batch-load CommentInteractions for a page of comments/replies in O(1) SQL queries."""
    unique_ids = list(dict.fromkeys(comment_ids))
    if not unique_ids:
        return {}
    reaction_rows = db.execute(
        select(CommentReaction.comment_id, CommentReaction.reaction_type, func.count())
        .join(User, User.id == CommentReaction.user_id)
        .where(
            CommentReaction.comment_id.in_(unique_ids),
            CommentReaction.reaction_type.in_(REACTION_TYPES),
            User.status == "active",
        )
        .group_by(CommentReaction.comment_id, CommentReaction.reaction_type)
    ).all()
    if viewer_id is not None:
        viewer_reactions = dict(
            db.execute(
                select(CommentReaction.comment_id, CommentReaction.reaction_type)
                .where(CommentReaction.comment_id.in_(unique_ids), CommentReaction.user_id == viewer_id)
            ).all()
        )
    else:
        viewer_reactions = {}
    from app.meme_reactions import meme_reaction_states
    meme_states = meme_reaction_states(db, CommentReaction, unique_ids, viewer_id, request)
    counts_by_comment = {cid: {kind: 0 for kind in REACTION_TYPES} for cid in unique_ids}
    for cid, kind, count in reaction_rows:
        counts_by_comment[cid][kind] = int(count)
    return {
        cid: CommentInteractions(
            comment_id=cid,
            reaction_counts=ReactionCounts(**counts_by_comment[cid]),
            viewer_reaction=viewer_reactions.get(cid),
            **meme_states.get(cid, {}),
        )
        for cid in unique_ids
    }


@router.get("/{comment_id}/interactions",response_model=CommentInteractions,operation_id="getCommentInteractions",
            responses={s:ERRORS[s] for s in (401,404,422,429,500)},
            openapi_extra={"security":[{},{"sessionCookie":[]}]})
def get_comment_interactions(comment_id: UUID,request: Request=None,reader=Depends(interaction_reader,scope="function")):
    db,viewer_id=reader
    counts=[select(func.count()).select_from(CommentReaction).join(User,User.id==CommentReaction.user_id).where(
        CommentReaction.comment_id==Comment.id,CommentReaction.reaction_type==kind,User.status=="active"
    ).correlate(Comment).scalar_subquery() for kind in REACTION_TYPES]
    reaction=select(CommentReaction.reaction_type).where(CommentReaction.comment_id==Comment.id,
        CommentReaction.user_id==viewer_id).correlate(Comment).scalar_subquery()
    row=db.execute(select(Comment.id,*counts,reaction).where(Comment.id.in_(visible_comment(comment_id)))).one_or_none()
    if row is None:raise AuthError(404,"NOT_FOUND","Comment not found.")
    from app.meme_reactions import meme_reaction_states
    meme=meme_reaction_states(db,CommentReaction,[comment_id],viewer_id,request).get(comment_id,{})
    return CommentInteractions(comment_id=row[0],reaction_counts=ReactionCounts(**dict(zip(REACTION_TYPES,row[1:7]))),
                               viewer_reaction=row[7],**meme)
