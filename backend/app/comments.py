"""Flat P0 comments, public visibility and owner-only soft deletion."""
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app.account_schemas import UserPublic
from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import page_rows, public_posts
from app.blog_schemas import CommentInteractions, Pagination, ReactionCounts, REACTION_TYPES, StrictInput
from app.models import AdminAuditLog, Category, Comment, CommentReaction, MediaUpload, Post, Profile, User
from app.permissions import optional_account_reader as interaction_reader, require_account_csrf
from app.admin_users import require_admin_mutation
from app.security import AuthError


router = APIRouter(prefix="/api/v1", tags=["Blog"])
NOT_FOUND = {404: {"model": ErrorResponse}}


class CommentInput(StrictInput):
    body: str = Field(min_length=1, max_length=4000)
    request_id: UUID | None = None
    parent_comment_id: UUID | None = None

    @field_validator("body")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Comment body must not be blank.")
        return value


class ReplyTargetUser(BaseModel):
    id: UUID
    username: str
    display_name: str


class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    author: UserPublic
    body: str
    created_at: datetime
    parent_comment_id: UUID | None = None
    reply_to_comment_id: UUID | None = None
    reply_to_user: ReplyTargetUser | None = None
    reply_count: int = 0
    interactions: CommentInteractions | None = Field(default=None, exclude_if=lambda value: value is None)


class CommentPage(BaseModel):
    items: list[CommentResponse]
    pagination: Pagination


class CommentLocateResponse(BaseModel):
    post_id: UUID
    comment_id: UUID
    root_comment_id: UUID
    is_reply: bool
    root_comment: CommentResponse | None = None


def comment_dto(
    comment,
    user,
    profile,
    level=None,
    is_admin=False,
    membership_tier="free",
    *,
    reply_to_user: ReplyTargetUser | None = None,
    reply_count: int = 0,
    interactions=None,
):
    author = UserPublic(id=user.id, username=user.username, display_name=profile.display_name,
                        created_at=user.created_at, bio=profile.bio, avatar_url=profile.avatar_url, level=level,
                        membership_tier=membership_tier if membership_tier in {"plus", "prime"} else "free",
                        is_admin_title=bool(is_admin))
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author=author,
        body=comment.body,
        created_at=comment.created_at,
        parent_comment_id=getattr(comment, "parent_comment_id", None),
        reply_to_comment_id=getattr(comment, "reply_to_comment_id", None),
        reply_to_user=reply_to_user,
        reply_count=reply_count,
        interactions=interactions,
    )


def _visible_parent_guard():
    parent = aliased(Comment)
    parent_user = aliased(User)
    return or_(
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


def _hydrate_comments(
    db,
    rows,
    viewer_id,
    request: Request,
    *,
    include_interactions: bool = False,
    include_reply_counts: bool = True,
) -> list[CommentResponse]:
    if not rows:
        return []
    now = request.app.state.auth.now()
    user_ids = {row[1].id for row in rows}
    comment_ids = [row[0].id for row in rows]
    reply_to_ids = {row[0].reply_to_user_id for row in rows if row[0].reply_to_user_id is not None}

    from app.membership import read_users_membership_tiers
    tiers = read_users_membership_tiers(db, user_ids, now)

    reply_targets: dict[UUID, ReplyTargetUser] = {}
    if reply_to_ids:
        for uid, uname, dname in db.execute(
            select(User.id, User.username, Profile.display_name)
            .join(Profile, Profile.user_id == User.id)
            .where(User.id.in_(reply_to_ids))
        ).all():
            reply_targets[uid] = ReplyTargetUser(id=uid, username=uname, display_name=dname)

    reply_counts: dict[UUID, int] = {}
    if include_reply_counts:
        root_ids = [row[0].id for row in rows if row[0].parent_comment_id is None]
        if root_ids:
            for pid, cnt in db.execute(
                select(Comment.parent_comment_id, func.count())
                .join(User, User.id == Comment.author_id)
                .where(
                    Comment.parent_comment_id.in_(root_ids),
                    Comment.status == "visible",
                    Comment.deleted_at.is_(None),
                    User.status == "active",
                )
                .group_by(Comment.parent_comment_id)
            ).all():
                reply_counts[pid] = int(cnt)

    interactions_by_id: dict[UUID, object] = {}
    if include_interactions:
        from app.comment_reactions import read_comment_states
        interactions_by_id = read_comment_states(comment_ids, db, viewer_id, request)

    return [
        comment_dto(
            *row,
            membership_tier=tiers.get(row[1].id, "free"),
            reply_to_user=reply_targets.get(row[0].reply_to_user_id) if row[0].reply_to_user_id else None,
            reply_count=reply_counts.get(row[0].id, 0),
            interactions=interactions_by_id.get(row[0].id),
        )
        for row in rows
    ]


def public_post_id(post_id):
    return public_posts().with_only_columns(Post.id).where(Post.id == post_id)


def require_public_post(db, post_id):
    if db.scalar(public_post_id(post_id)) is None:
        raise AuthError(404, "NOT_FOUND", "Post not found.")


def lock_public_post(db, post_id):
    # Same post -> category -> media order as post PATCH; SHARE blocks visibility mutations until commit.
    post = db.scalar(select(Post).where(Post.id == post_id).with_for_update(read=True).execution_options(populate_existing=True))
    if post is None:
        raise AuthError(404, "NOT_FOUND", "Post not found.")
    db.scalar(select(Category.id).where(Category.id == post.category_id).with_for_update(read=True))
    if post.media_id is not None:
        db.scalar(select(MediaUpload.id).where(MediaUpload.id == post.media_id).with_for_update(read=True))
    require_public_post(db, post_id)


@router.get("/posts/{post_id}/comments", response_model=CommentPage, operation_id="listComments",
            responses={status: {"model": ErrorResponse} for status in (404, 422, 429, 500)},
            openapi_extra={"security": [{}, {"sessionCookie": []}]})
def list_comments(
    post_id: UUID,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    author: str | None = Query(None, max_length=32),
    sort: Literal["created_asc", "created_desc", "reaction_desc"] = "created_asc",
    include_interactions: bool = Query(False),
    reader=Depends(interaction_reader, scope="function"),
):
    if any(value is not None and "\x00" in value for value in (search, author)):
        raise AuthError(422, "VALIDATION_ERROR", "Invalid query text.")
    db, viewer_id = reader
    require_public_post(db, post_id)
    from app.aura_runtime import public_is_admin_column, public_level_column
    statement = (
        select(Comment, User, Profile, public_level_column(request.app.state.auth.now()), public_is_admin_column())
        .join(User, User.id == Comment.author_id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            Comment.post_id == post_id,
            Comment.status == "visible",
            Comment.deleted_at.is_(None),
            User.status == "active",
            Comment.post_id.in_(public_post_id(post_id)),
        )
    )
    if search is not None:
        statement = statement.where(Comment.body.icontains(search, autoescape=True), _visible_parent_guard())
    else:
        statement = statement.where(Comment.parent_comment_id.is_(None))
    if author is not None:
        statement = statement.where(User.username == author)

    if sort == "reaction_desc":
        from app.meme_reactions import enabled as meme_enabled, valid_meme_reaction
        valid_rx = (
            or_(CommentReaction.reaction_type.in_(REACTION_TYPES), valid_meme_reaction(CommentReaction))
            if meme_enabled(request)
            else CommentReaction.reaction_type.in_(REACTION_TYPES)
        )
        reaction_count_sq = (
            select(func.count())
            .select_from(CommentReaction)
            .join(User, User.id == CommentReaction.user_id)
            .where(CommentReaction.comment_id == Comment.id, User.status == "active", valid_rx)
            .correlate(Comment)
            .scalar_subquery()
        )
        ordering = (func.coalesce(reaction_count_sq, 0).desc(), Comment.created_at.desc(), Comment.id.desc())
    elif sort == "created_desc":
        ordering = (Comment.created_at.desc(), Comment.id.desc())
    else:
        ordering = (Comment.created_at, Comment.id)

    rows, pagination = page_rows(db, statement.order_by(*ordering), page, page_size)
    items = _hydrate_comments(db, rows, viewer_id, request, include_interactions=include_interactions, include_reply_counts=True)
    return CommentPage(items=items, pagination=pagination)


@router.get("/comments/{comment_id}/replies", response_model=CommentPage, operation_id="listCommentReplies",
            responses={status: {"model": ErrorResponse} for status in (404, 422, 429, 500)})
def list_comment_replies(
    comment_id: UUID,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    include_interactions: bool = Query(False),
    reader=Depends(interaction_reader, scope="function"),
):
    db, viewer_id = reader
    root_ok = db.scalar(
        select(Comment.id)
        .join(User, User.id == Comment.author_id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            Comment.id == comment_id,
            Comment.parent_comment_id.is_(None),
            Comment.status == "visible",
            Comment.deleted_at.is_(None),
            User.status == "active",
            Comment.post_id.in_(public_posts().with_only_columns(Post.id)),
        )
    )
    if root_ok is None:
        raise AuthError(404, "NOT_FOUND", "Comment not found.")
    from app.aura_runtime import public_is_admin_column, public_level_column
    statement = (
        select(Comment, User, Profile, public_level_column(request.app.state.auth.now()), public_is_admin_column())
        .join(User, User.id == Comment.author_id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            Comment.parent_comment_id == comment_id,
            Comment.status == "visible",
            Comment.deleted_at.is_(None),
            User.status == "active",
        )
    )
    rows, pagination = page_rows(db, statement.order_by(Comment.created_at, Comment.id), page, page_size)
    items = _hydrate_comments(db, rows, viewer_id, request, include_interactions=include_interactions, include_reply_counts=False)
    return CommentPage(items=items, pagination=pagination)


@router.get("/posts/{post_id}/comments/{comment_id}/locate", response_model=CommentLocateResponse, operation_id="locateComment",
            responses={status: {"model": ErrorResponse} for status in (404, 422, 429, 500)},
            openapi_extra={"security": [{}, {"sessionCookie": []}]})
def locate_comment(post_id: UUID, comment_id: UUID, request: Request, reader=Depends(interaction_reader, scope="function")):
    db, viewer_id = reader
    require_public_post(db, post_id)
    row = db.execute(
        select(Comment)
        .join(User, User.id == Comment.author_id)
        .where(
            Comment.id == comment_id,
            Comment.post_id == post_id,
            Comment.status == "visible",
            Comment.deleted_at.is_(None),
            User.status == "active",
            _visible_parent_guard(),
        )
    ).scalar_one_or_none()
    if row is None:
        raise AuthError(404, "NOT_FOUND", "Comment not found.")
    root_id = row.parent_comment_id or row.id
    from app.aura_runtime import public_is_admin_column, public_level_column
    root_row = db.execute(
        select(Comment, User, Profile, public_level_column(request.app.state.auth.now()), public_is_admin_column())
        .join(User, User.id == Comment.author_id)
        .join(Profile, Profile.user_id == User.id)
        .where(Comment.id == root_id)
    ).one_or_none()
    hydrated = _hydrate_comments(db, [root_row], viewer_id, request, include_interactions=True, include_reply_counts=True)[0] if root_row else None
    return CommentLocateResponse(
        post_id=post_id,
        comment_id=row.id,
        root_comment_id=root_id,
        is_reply=row.parent_comment_id is not None,
        root_comment=hydrated,
    )


@router.post("/posts/{post_id}/comments", status_code=201, response_model=CommentResponse,
             operation_id="addComment", responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def add_comment(post_id: UUID, payload: CommentInput, request: Request, account=Depends(require_account_csrf)):
    lock_public_post(account.db, post_id)
    now = request.app.state.auth.now()
    from app.aura_runtime import award_comment, read_public_is_admin, read_public_level

    resolved_parent_id: UUID | None = None
    resolved_reply_to_id: UUID | None = None
    resolved_reply_to_user_id: UUID | None = None
    if payload.parent_comment_id is not None:
        target = account.db.scalar(
            select(Comment).where(Comment.id == payload.parent_comment_id).with_for_update()
        )
        if target is None or target.post_id != post_id:
            raise AuthError(404 if target is None else 422, "NOT_FOUND" if target is None else "VALIDATION_ERROR",
                            "Parent comment not found." if target is None else "Parent comment belongs to another post.")
        target_author = account.db.get(User, target.author_id)
        if target.status != "visible" or target.deleted_at is not None or target_author is None or target_author.status != "active":
            raise AuthError(404, "NOT_FOUND", "Parent comment not found.")
        if target.parent_comment_id is not None:
            root = account.db.scalar(
                select(Comment).where(Comment.id == target.parent_comment_id).with_for_update()
            )
            root_author = account.db.get(User, root.author_id) if root is not None else None
            if root is None or root.post_id != post_id or root.status != "visible" or root.deleted_at is not None or root_author is None or root_author.status != "active":
                raise AuthError(404, "NOT_FOUND", "Parent comment not found.")
            resolved_parent_id = root.id
        else:
            resolved_parent_id = target.id
        resolved_reply_to_id = target.id
        resolved_reply_to_user_id = target.author_id

    if payload.request_id is not None:
        existing = account.db.get(Comment, payload.request_id)
        if existing is not None:
            if (
                existing.author_id != account.user.id
                or existing.post_id != post_id
                or existing.body != payload.body
                or existing.status != "visible"
                or existing.deleted_at is not None
                or existing.parent_comment_id != resolved_parent_id
                or existing.reply_to_comment_id != resolved_reply_to_id
            ):
                raise AuthError(409, "CONFLICT", "Request ID already used.")
            from app.membership import read_users_membership_tiers
            tiers = read_users_membership_tiers(account.db, {account.user.id}, now)
            rt_user = None
            if existing.reply_to_user_id:
                u_rt = account.db.get(User, existing.reply_to_user_id)
                p_rt = account.db.get(Profile, existing.reply_to_user_id)
                if u_rt and p_rt:
                    rt_user = ReplyTargetUser(id=u_rt.id, username=u_rt.username, display_name=p_rt.display_name)
            return comment_dto(
                existing, account.user, account.db.get(Profile, account.user.id),
                read_public_level(account.db, account.user.id, now),
                is_admin=read_public_is_admin(account.db, account.user.id),
                membership_tier=tiers.get(account.user.id, "free"),
                reply_to_user=rt_user,
            )

    comment = Comment(
        id=payload.request_id or uuid4(),
        post_id=post_id,
        author_id=account.user.id,
        body=payload.body,
        status="visible",
        created_at=now,
        updated_at=now,
        deleted_at=None,
        parent_comment_id=resolved_parent_id,
        reply_to_comment_id=resolved_reply_to_id,
        reply_to_user_id=resolved_reply_to_user_id,
    )
    account.db.add(comment)
    try:
        account.db.flush()
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise AuthError(409, "CONFLICT", "Request ID already used.") from None
        raise
    award_comment(account.db, comment, now)
    post = account.db.get(Post, post_id)
    author_id = getattr(post, "author_id", None)
    post_title = (getattr(post, "title", None) or "")[:80]
    from app.notifications import create_notification

    if resolved_reply_to_user_id is not None and resolved_reply_to_user_id != account.user.id:
        create_notification(
            account.db,
            recipient_user_id=resolved_reply_to_user_id,
            type="comment",
            target_type="comment",
            target_id=comment.id,
            actor_user_id=account.user.id,
            payload={
                "action": "reply",
                "post_id": str(post_id),
                "post_title": post_title,
                "comment_id": str(comment.id),
                "parent_comment_id": str(resolved_parent_id),
                "comment_body": (comment.body or "")[:120],
            },
            dedupe_key=f"reply:{comment.id}:{resolved_reply_to_user_id}",
            now=now,
        )

    if author_id is not None and author_id != account.user.id and author_id != resolved_reply_to_user_id:
        create_notification(
            account.db,
            recipient_user_id=author_id,
            type="comment",
            target_type="comment",
            target_id=comment.id,
            actor_user_id=account.user.id,
            payload={
                "post_id": str(post_id),
                "post_title": post_title,
                "comment_id": str(comment.id),
                "comment_body": (comment.body or "")[:120],
            },
            dedupe_key=f"comment:{comment.id}",
            now=now,
        )

    from app.membership import read_users_membership_tiers
    tiers = read_users_membership_tiers(account.db, {account.user.id}, now)
    rt_user = None
    if resolved_reply_to_user_id is not None:
        u_rt = account.db.get(User, resolved_reply_to_user_id)
        p_rt = account.db.get(Profile, resolved_reply_to_user_id)
        if u_rt and p_rt:
            rt_user = ReplyTargetUser(id=u_rt.id, username=u_rt.username, display_name=p_rt.display_name)
    return comment_dto(
        comment, account.user, account.db.get(Profile, account.user.id),
        read_public_level(account.db, account.user.id, now),
        is_admin=read_public_is_admin(account.db, account.user.id),
        membership_tier=tiers.get(account.user.id, "free"),
        reply_to_user=rt_user,
    )


@router.delete("/comments/{comment_id}", status_code=204, operation_id="deleteComment",
               responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def delete_comment(comment_id: UUID, request: Request, account=Depends(require_account_csrf)):
    comment = account.db.scalar(select(Comment).where(Comment.id == comment_id,
        Comment.author_id == account.user.id, Comment.status != "deleted").with_for_update())
    if comment is None:
        raise AuthError(404, "NOT_FOUND", "Comment not found.")
    comment.status = "deleted"
    comment.deleted_at = comment.updated_at = request.app.state.auth.now()
    from app.aura_runtime import reverse_comment
    reverse_comment(account.db, comment.id, comment.updated_at)
    account.db.flush()


class CommentModeration(StrictInput):
    status: Literal["visible", "hidden", "deleted"]
    reason: str | None = Field(default=None, max_length=500)

def moderate_comment_record(comment_id, request, account, status, reason=None):
    comment = account.db.scalar(select(Comment).where(Comment.id == comment_id, Comment.deleted_at.is_(None)).with_for_update())
    if comment is None:
        raise AuthError(404, "NOT_FOUND", "Comment not found.")
    before = {"status": comment.status}
    comment.status = status
    comment.updated_at = request.app.state.auth.now()
    if status == "deleted":
        comment.deleted_at = comment.updated_at
    if status in {"hidden", "deleted"}:
        from app.aura_runtime import reverse_comment
        reverse_comment(account.db, comment.id, comment.updated_at)
    account.db.add(AdminAuditLog(id=uuid4(), actor_id=account.user.id, action="comment." + status, target_type="comment",
        target_id=str(comment.id), before_json=before, after_json={"status": status, **({"reason": reason} if reason else {})}, created_at=comment.updated_at))
    account.db.flush()
    if status in {"hidden", "deleted"}:
        author_id = getattr(comment, "author_id", None)
        if author_id is not None and author_id != account.user.id:
            from app.notifications import create_notification
            create_notification(
                account.db,
                recipient_user_id=author_id,
                type="moderation",
                target_type="comment",
                target_id=comment.id,
                actor_user_id=account.user.id,
                payload={
                    "action": status,
                    "reason": reason or ("Bình luận của bạn đã bị ẩn do vi phạm Tiêu chuẩn Cộng đồng." if status == "hidden" else "Bình luận của bạn đã bị xóa bởi Quản trị viên."),
                    "comment_body": (getattr(comment, "body", None) or "")[:120],
                    "post_id": str(comment.post_id) if getattr(comment, "post_id", None) else None,
                },
                dedupe_key=f"mod:comment:{comment.id}:{status}",
                now=comment.updated_at,
            )

@router.patch("/admin/comments/{comment_id}", status_code=204, operation_id="adminModerateComment", tags=["Admin"],
              responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def moderate_comment(comment_id: UUID, payload: CommentModeration, request: Request, account=Depends(require_admin_mutation, scope="function")):
    moderate_comment_record(comment_id, request, account, payload.status, payload.reason)

@router.delete("/admin/comments/{comment_id}", status_code=204, operation_id="adminDeleteComment", tags=["Admin"],
               responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def admin_delete_comment(comment_id: UUID, request: Request, reason: str | None = Query(None, max_length=500),
                         account=Depends(require_admin_mutation, scope="function")):
    moderate_comment_record(comment_id, request, account, "deleted", reason)


@router.get("/users/{username}/comments", response_model=CommentPage, operation_id="listUserComments",
            responses={status: {"model": ErrorResponse} for status in (404, 422, 429, 500)})
def list_user_comments(request: Request, username: str = Path(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$"),
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    with request.app.state.auth_session_factory() as db:
        if db.scalar(select(User.id).where(User.username == username, User.status == "active")) is None:
            raise AuthError(404, "NOT_FOUND", "Profile not found.")
        from app.aura_runtime import public_is_admin_column, public_level_column
        statement = select(Comment, User, Profile, public_level_column(request.app.state.auth.now()), public_is_admin_column()).join(User, User.id == Comment.author_id).join(
            Profile, Profile.user_id == User.id).where(User.username == username, User.status == "active",
                Comment.status == "visible", Comment.deleted_at.is_(None),
                _visible_parent_guard(),
                Comment.post_id.in_(public_posts().with_only_columns(Post.id)))
        rows, pagination = page_rows(db, statement.order_by(Comment.created_at.desc(), Comment.id.desc()), page, page_size)
        return CommentPage(items=[comment_dto(*row) for row in rows], pagination=pagination)
