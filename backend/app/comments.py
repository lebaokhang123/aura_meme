"""Flat P0 comments, public visibility and owner-only soft deletion."""
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.account_schemas import UserPublic
from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import page_rows, public_posts
from app.blog_schemas import Pagination, StrictInput
from app.models import Category, Comment, MediaUpload, Post, Profile, User
from app.permissions import require_account_csrf
from app.security import AuthError


router = APIRouter(prefix="/api/v1", tags=["Blog"])
NOT_FOUND = {404: {"model": ErrorResponse}}


class CommentInput(StrictInput):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Comment body must not be blank.")
        return value


class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    author: UserPublic
    body: str
    created_at: datetime


class CommentPage(BaseModel):
    items: list[CommentResponse]
    pagination: Pagination


def comment_dto(comment, user, profile):
    author = UserPublic(id=user.id, username=user.username, display_name=profile.display_name,
                        created_at=user.created_at, bio=profile.bio, avatar_url=None)
    return CommentResponse(id=comment.id, post_id=comment.post_id, author=author,
                           body=comment.body, created_at=comment.created_at)


def public_post_id(post_id):
    return public_posts().with_only_columns(Post.id).where(Post.id == post_id)


def require_public_post(db, post_id):
    if db.scalar(public_post_id(post_id)) is None:
        raise AuthError(404, "NOT_FOUND", "Post not found.")


def lock_public_post(db, post_id):
    # Same post -> category -> media order as post PATCH; SHARE blocks visibility mutations until commit.
    post = db.scalar(select(Post).where(Post.id == post_id).with_for_update(read=True))
    if post is None:
        raise AuthError(404, "NOT_FOUND", "Post not found.")
    db.scalar(select(Category.id).where(Category.id == post.category_id).with_for_update(read=True))
    if post.media_id is not None:
        db.scalar(select(MediaUpload.id).where(MediaUpload.id == post.media_id).with_for_update(read=True))
    require_public_post(db, post_id)


@router.get("/posts/{post_id}/comments", response_model=CommentPage, operation_id="listComments",
            responses={status: {"model": ErrorResponse} for status in (404, 422, 429, 500)})
def list_comments(post_id: UUID, request: Request, page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100)):
    with request.app.state.auth_session_factory() as db:
        require_public_post(db, post_id)
        statement = select(Comment, User, Profile).join(User, User.id == Comment.author_id).join(
            Profile, Profile.user_id == User.id).where(Comment.post_id == post_id,
                Comment.status == "visible", Comment.deleted_at.is_(None), User.status == "active",
                Comment.post_id.in_(public_post_id(post_id)))
        rows, pagination = page_rows(db, statement.order_by(Comment.created_at, Comment.id), page, page_size)
        return CommentPage(items=[comment_dto(*row) for row in rows], pagination=pagination)


@router.post("/posts/{post_id}/comments", status_code=201, response_model=CommentResponse,
             operation_id="addComment", responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def add_comment(post_id: UUID, payload: CommentInput, request: Request, account=Depends(require_account_csrf)):
    lock_public_post(account.db, post_id)
    now = request.app.state.auth.now()
    comment = Comment(id=uuid4(), post_id=post_id, author_id=account.user.id, body=payload.body,
                      status="visible", created_at=now, updated_at=now, deleted_at=None)
    account.db.add(comment)
    account.db.flush()
    return comment_dto(comment, account.user, account.db.get(Profile, account.user.id))


@router.delete("/comments/{comment_id}", status_code=204, operation_id="deleteComment",
               responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def delete_comment(comment_id: UUID, request: Request, account=Depends(require_account_csrf)):
    comment = account.db.scalar(select(Comment).where(Comment.id == comment_id,
        Comment.author_id == account.user.id, Comment.status != "deleted").with_for_update())
    if comment is None:
        raise AuthError(404, "NOT_FOUND", "Comment not found.")
    comment.status = "deleted"
    comment.deleted_at = comment.updated_at = request.app.state.auth.now()
    account.db.flush()
