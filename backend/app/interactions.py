"""P1 interactions only: stable per-user rows, no reward issuance."""
from typing import Literal, get_args
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.auth import CSRF_HEADER, ERRORS, session_cookie
from app.auth_schemas import ErrorResponse
from app.blog import page_rows, post_dto, public_posts
from app.blog_schemas import PostPage, ReactionType, REACTION_TYPES, ReactionCounts, PostInteractions
from app.comments import lock_public_post, public_post_id
from app.models import Category, Comment, Post, PostBookmark, PostReaction, Profile, User
from app.permissions import optional_account_reader as interaction_reader, authenticated_account, require_account_csrf, require_authenticated_user
from app.security import AuthError

router = APIRouter(prefix="/api/v1", tags=["Aura"])
ERRORS = ERRORS | {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}


class ReactionInput(BaseModel):
    model_config = ConfigDict(extra='ignore')
    reaction_type: ReactionType | Literal['meme']
    meme_asset_id: UUID | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode='after')
    def matching_asset(self):
        if (self.reaction_type == 'meme') != (self.meme_asset_id is not None):
            raise ValueError('Only meme reactions require an owned meme_asset_id.')
        return self


class ReactionResult(ReactionInput):
    post_id: UUID




@router.get("/posts/{post_id}/interactions", response_model=PostInteractions,
            operation_id="getPostInteractions", responses={s: ERRORS[s] for s in (401, 404, 422, 429, 500)},
            openapi_extra={"security": [{}, {"sessionCookie": []}]})
def get_post_interactions(post_id: UUID, request: Request = None, reader=Depends(interaction_reader, scope="function")):
    db, viewer_id = reader
    return read_post_state(post_id, db, viewer_id, request)


def read_post_state(post_id, db, viewer_id, request, meme_state=None):
    counts = [select(func.count()).select_from(PostReaction).join(User, User.id == PostReaction.user_id).where(
        PostReaction.post_id == Post.id, PostReaction.reaction_type == kind, User.status == "active"
    ).correlate(Post).scalar_subquery() for kind in REACTION_TYPES]
    comments = select(func.count()).select_from(Comment).join(User, User.id == Comment.author_id).join(
        Profile, Profile.user_id == User.id).where(Comment.post_id == Post.id, Comment.status == "visible",
        Comment.deleted_at.is_(None), User.status == "active").correlate(Post).scalar_subquery()
    reaction = select(PostReaction.reaction_type).where(PostReaction.post_id == Post.id,
        PostReaction.user_id == viewer_id).correlate(Post).scalar_subquery()
    bookmarked = exists(select(PostBookmark.post_id).where(PostBookmark.post_id == Post.id,
        PostBookmark.user_id == viewer_id)).correlate(Post)
    row = db.execute(select(Post.id, *counts, comments, reaction, bookmarked).where(
        Post.id == post_id, Post.id.in_(public_post_id(post_id)))).one_or_none()
    if row is None:
        raise AuthError(404, "NOT_FOUND", "Post not found.")
    from app.meme_reactions import meme_reaction_states
    meme = (meme_reaction_states(db, PostReaction, [post_id], viewer_id, request).get(post_id, {})
            if meme_state is None else meme_state)
    return PostInteractions(post_id=row[0], reaction_counts=ReactionCounts(**dict(zip(REACTION_TYPES, row[1:7]))),
                            comments_count=row[7], viewer_reaction=row[8], bookmarked=row[9], **meme)


def read_post_states(post_ids: list[UUID], db, viewer_id, request, meme_states=None) -> dict[UUID, PostInteractions]:
    """Batch-load PostInteractions for a page of posts in O(1) SQL queries."""
    unique_ids = list(dict.fromkeys(post_ids))
    if not unique_ids:
        return {}
    reaction_rows = db.execute(
        select(PostReaction.post_id, PostReaction.reaction_type, func.count())
        .join(User, User.id == PostReaction.user_id)
        .where(
            PostReaction.post_id.in_(unique_ids),
            PostReaction.reaction_type.in_(REACTION_TYPES),
            User.status == "active",
        )
        .group_by(PostReaction.post_id, PostReaction.reaction_type)
    ).all()
    comment_rows = db.execute(
        select(Comment.post_id, func.count())
        .join(User, User.id == Comment.author_id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            Comment.post_id.in_(unique_ids),
            Comment.status == "visible",
            Comment.deleted_at.is_(None),
            User.status == "active",
        )
        .group_by(Comment.post_id)
    ).all()
    if viewer_id is not None:
        viewer_reactions = dict(
            db.execute(
                select(PostReaction.post_id, PostReaction.reaction_type)
                .where(PostReaction.post_id.in_(unique_ids), PostReaction.user_id == viewer_id)
            ).all()
        )
        bookmarked_ids = set(
            db.scalars(
                select(PostBookmark.post_id)
                .where(PostBookmark.post_id.in_(unique_ids), PostBookmark.user_id == viewer_id)
            ).all()
        )
    else:
        viewer_reactions = {}
        bookmarked_ids = set()
    if meme_states is None:
        from app.meme_reactions import meme_reaction_states
        meme_states = meme_reaction_states(db, PostReaction, unique_ids, viewer_id, request)
    counts_by_post = {pid: {kind: 0 for kind in REACTION_TYPES} for pid in unique_ids}
    for pid, kind, count in reaction_rows:
        counts_by_post[pid][kind] = int(count)
    comments_by_post = {pid: int(count) for pid, count in comment_rows}
    return {
        pid: PostInteractions(
            post_id=pid,
            reaction_counts=ReactionCounts(**counts_by_post[pid]),
            comments_count=comments_by_post.get(pid, 0),
            viewer_reaction=viewer_reactions.get(pid),
            bookmarked=pid in bookmarked_ids,
            **meme_states.get(pid, {}),
        )
        for pid in unique_ids
    }


@router.get("/users/me/bookmarks", response_model=PostPage, operation_id="listSavedPosts", responses=ERRORS)
def list_saved_posts(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                     search: str | None = Query(None, max_length=100), category: str | None = None,
                     sort: Literal["created_desc", "created_asc", "title_asc"] = "created_desc",
                     account=Depends(require_authenticated_user, scope="function")):
    if any(value is not None and "\x00" in value for value in (search, category)):
        raise AuthError(422, "VALIDATION_ERROR", "Invalid query text.")
    statement = public_posts().join(PostBookmark, PostBookmark.post_id == Post.id).where(
        PostBookmark.user_id == account.user.id)
    if search is not None:
        statement = statement.where(or_(Post.title.icontains(search, autoescape=True), Post.content.icontains(search, autoescape=True)))
    if category is not None:
        statement = statement.where(Category.slug == category)
    ordering = {"created_desc": (Post.created_at.desc(), Post.id.desc()),
                "created_asc": (Post.created_at, Post.id), "title_asc": (Post.title, Post.id)}
    rows, pagination = page_rows(account.db, statement.order_by(*ordering[sort]), page, page_size)
    return PostPage(items=[post_dto(*row) for row in rows], pagination=pagination)


@router.put("/posts/{post_id}/reactions", response_model=ReactionResult, operation_id="setReaction",
            responses=ERRORS, openapi_extra=CSRF_HEADER)
def set_reaction(post_id: UUID, payload: ReactionInput, request: Request, account=Depends(require_account_csrf)):
    lock_public_post(account.db, post_id)
    first = account.db.get(PostReaction, (post_id, account.user.id)) is None
    now = request.app.state.auth.now()
    from app.meme_reactions import set_owned_reaction
    set_owned_reaction(account, request, PostReaction, 'post_id', post_id, payload, now)
    if first:
        from app.aura_runtime import award_reaction
        award_reaction(account.db, post_id, account.user.id, now)
    post = account.db.get(Post, post_id)
    author_id = getattr(post, "author_id", None)
    if author_id is not None and author_id != account.user.id:
        from app.notifications import create_notification
        create_notification(
            account.db,
            recipient_user_id=author_id,
            type="reaction",
            target_type="post",
            target_id=post_id,
            actor_user_id=account.user.id,
            payload={
                "reaction_type": payload.reaction_type,
                "post_title": (getattr(post, "title", None) or "")[:80],
            },
            dedupe_key=f"reaction:{post_id}:{account.user.id}",
            now=now,
        )
    return ReactionResult(post_id=post_id, **payload.model_dump())


@router.delete("/posts/{post_id}/reactions", status_code=204, operation_id="removeReaction",
               responses=ERRORS, openapi_extra=CSRF_HEADER)
def remove_reaction(post_id: UUID, request: Request, account=Depends(require_account_csrf)):
    lock_public_post(account.db, post_id)
    account.db.execute(delete(PostReaction).where(PostReaction.post_id == post_id, PostReaction.user_id == account.user.id))
    from app.aura_runtime import reverse_reaction
    reverse_reaction(account.db, post_id, account.user.id, request.app.state.auth.now())


@router.put("/posts/{post_id}/bookmark", status_code=204, operation_id="savePost",
            responses=ERRORS, openapi_extra=CSRF_HEADER)
def save_post(post_id: UUID, request: Request, account=Depends(require_account_csrf)):
    lock_public_post(account.db, post_id)
    account.db.execute(insert(PostBookmark).values(post_id=post_id, user_id=account.user.id,
        created_at=request.app.state.auth.now()).on_conflict_do_nothing(index_elements=["post_id", "user_id"]))


@router.delete("/posts/{post_id}/bookmark", status_code=204, operation_id="unsavePost",
               responses=ERRORS, openapi_extra=CSRF_HEADER)
def unsave_post(post_id: UUID, account=Depends(require_account_csrf)):
    lock_public_post(account.db, post_id)
    account.db.execute(delete(PostBookmark).where(PostBookmark.post_id == post_id, PostBookmark.user_id == account.user.id))
