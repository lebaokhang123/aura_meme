"""Admin post moderation and metadata-only audit browsing; no content renderer."""
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import String, cast, or_, select

from app.admin_users import require_admin_mutation
from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import page_rows, post_dto, validate_post
from app.blog_schemas import Pagination, PostPage, PostPatch, PostResponse
from app.models import AdminAuditLog, Category, Post, Profile, User
from app.permissions import require_role
from app.security import AuthError

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])
NOT_FOUND = {404: {"model": ErrorResponse}}


class AdminPostPatch(PostPatch):
    status: Literal["draft", "published", "hidden"] = None


class AdminAuditEvent(BaseModel):
    id: UUID
    actor_id: UUID
    action: str
    target_type: str
    target_id: str
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AdminAuditEvent]
    pagination: Pagination


def post_state(post):
    return {"status": post.status, "category_id": str(post.category_id),
            "media_id": str(post.media_id) if post.media_id else None}


def audit_post(account, post, action, before, now, **flags):
    account.db.add(AdminAuditLog(id=uuid4(), actor_id=account.user.id, action=action, target_type="post",
        target_id=str(post.id), before_json=before, after_json=post_state(post) | flags, created_at=now))
    account.db.flush()


def locked_post(db, post_id):
    post = db.scalar(select(Post).where(Post.id == post_id, Post.status != "deleted")
                     .with_for_update().execution_options(populate_existing=True))
    if post is None:
        raise AuthError(404, "NOT_FOUND", "Post not found.")
    return post


@router.get("/posts", response_model=PostPage, operation_id="adminListPosts",
            responses={code: ERRORS[code] for code in (401, 403, 422, 429, 500)})
def list_admin_posts(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                      search: str | None = Query(None, max_length=100), status: str | None = None,
                      category: str | None = None,
                      sort: Literal["created_desc", "created_asc", "title_asc"] = "created_desc",
                      account=Depends(require_role("ADMIN"))):
    if any(value is not None and "\x00" in value for value in (search, status, category)):
        raise AuthError(422, "VALIDATION_ERROR", "Invalid query text.")
    statement = select(Post, User, Profile, Category).join(User, User.id == Post.author_id).join(
        Profile, Profile.user_id == User.id).join(Category, Category.id == Post.category_id)
    if search is not None:
        statement = statement.where(or_(Post.title.icontains(search, autoescape=True), Post.content.icontains(search, autoescape=True)))
    if status is not None:
        statement = statement.where(Post.status == status)
    if category is not None:
        statement = statement.where(Category.slug == category)
    ordering = {"created_desc": (Post.created_at.desc(), Post.id.desc()),
                "created_asc": (Post.created_at, Post.id), "title_asc": (Post.title, Post.id)}
    rows, pagination = page_rows(account.db, statement.order_by(*ordering[sort]), page, page_size)
    return PostPage(items=[post_dto(*row) for row in rows], pagination=pagination)


@router.patch("/posts/{post_id}", response_model=PostResponse, operation_id="adminModeratePost",
              responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def moderate_post(post_id: UUID, payload: AdminPostPatch, request: Request,
                   account=Depends(require_admin_mutation, scope="function")):
    post = locked_post(account.db, post_id)
    before = post_state(post)
    values = payload.model_dump(exclude_unset=True)
    text_flags = {name + "_changed": name in values and values[name] != getattr(post, name) for name in ("title", "content")}
    if {"category_id", "media_id", "content"}.intersection(values):
        category = validate_post(account.db, post.author_id, values.get("category_id", post.category_id),
            values.get("media_id", post.media_id), values.get("content", post.content), allow_hidden_category=True)
    else:
        category = account.db.get(Category, post.category_id)
    for name, value in values.items():
        setattr(post, name, value)
    post.updated_at = request.app.state.auth.now()
    audit_post(account, post, "post.update", before, post.updated_at, **text_flags)
    return post_dto(post, account.db.get(User, post.author_id), account.db.get(Profile, post.author_id), category)


@router.delete("/posts/{post_id}", status_code=204, operation_id="adminDeletePost", responses=ERRORS | NOT_FOUND,
               openapi_extra=CSRF_HEADER)
def delete_admin_post(post_id: UUID, request: Request, account=Depends(require_admin_mutation, scope="function")):
    post = locked_post(account.db, post_id)
    before = post_state(post)
    post.status, post.deleted_at = "deleted", request.app.state.auth.now()
    post.updated_at = post.deleted_at
    audit_post(account, post, "post.delete", before, post.updated_at)


@router.get("/audit-logs", response_model=AuditPage, operation_id="adminListAudit",
            responses={code: ERRORS[code] for code in (401, 403, 422, 429, 500)})
def list_audit(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                search: str | None = Query(None, max_length=100), action: str | None = Query(None, max_length=100),
                target_type: str | None = Query(None, max_length=100), actor_id: UUID | None = None,
                sort: Literal["created_desc", "created_asc", "action_asc"] = "created_desc",
                account=Depends(require_role("ADMIN"))):
    if any(value is not None and "\x00" in value for value in (search, action, target_type)):
        raise AuthError(422, "VALIDATION_ERROR", "Invalid query text.")
    statement = select(AdminAuditLog)
    if search is not None:
        statement = statement.where(or_(*(column.icontains(search, autoescape=True) for column in (
            AdminAuditLog.action, AdminAuditLog.target_type, AdminAuditLog.target_id, cast(AdminAuditLog.actor_id, String)))))
    if action is not None:
        statement = statement.where(AdminAuditLog.action == action)
    if target_type is not None:
        statement = statement.where(AdminAuditLog.target_type == target_type)
    if actor_id is not None:
        statement = statement.where(AdminAuditLog.actor_id == actor_id)
    ordering = {"created_desc": (AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc()),
                "created_asc": (AdminAuditLog.created_at, AdminAuditLog.id), "action_asc": (AdminAuditLog.action, AdminAuditLog.id)}
    rows, pagination = page_rows(account.db, statement.order_by(*ordering[sort]), page, page_size)
    return AuditPage(items=[AdminAuditEvent.model_validate(row[0], from_attributes=True) for row in rows], pagination=pagination)
