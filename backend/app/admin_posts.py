"""Admin post moderation and metadata-only audit browsing; no content renderer."""
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, not_, or_, select

from app.admin_users import require_admin_mutation
from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import page_rows, post_dto, validate_post
from app.blog_schemas import Pagination, PostPage, PostPatch, PostResponse
from app.models import AdminAuditLog, Category, Notification, Post, Profile, User
from app.permissions import require_role
from app.security import AuthError

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])
NOT_FOUND = {404: {"model": ErrorResponse}}


class AdminPostPatch(PostPatch):
    status: Literal["draft", "published", "hidden", "deleted"] = None
    reason: str | None = Field(default=None, max_length=500)


class AnnouncementInput(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=2000)
    is_draft: bool = False


class AnnouncementUpdateInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    body: str | None = Field(default=None, min_length=1, max_length=2000)


class AnnouncementItem(BaseModel):
    id: UUID
    title: str
    body: str
    status: Literal["draft", "published", "withdrawn"]
    actor_id: UUID
    actor_username: str | None = None
    created_at: datetime
    published_at: datetime | None = None
    recipients_count: int = 0


class AnnouncementPage(BaseModel):
    items: list[AnnouncementItem]
    pagination: Pagination


class AnnouncementResponse(BaseModel):
    success: bool
    recipients_count: int
    created_at: datetime
    id: UUID | None = None
    status: str = "published"


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
    reason = values.pop("reason", None)
    text_flags = {name + "_changed": name in values and values[name] != getattr(post, name) for name in ("title", "content")}
    if reason:
        text_flags["reason"] = reason
    if {"category_id", "media_id", "content"}.intersection(values):
        category = validate_post(account.db, post.author_id, values.get("category_id", post.category_id),
            values.get("media_id", post.media_id), values.get("content", post.content), allow_hidden_category=True)
    else:
        category = account.db.get(Category, post.category_id)
    for name, value in values.items():
        setattr(post, name, value)
    post.updated_at = request.app.state.auth.now()
    if before["status"] == "published" and (post.status != "published" or
            before["category_id"] != str(post.category_id) and category.status == "hidden"):
        from app.aura_runtime import reverse_post
        reverse_post(account.db, post.id, post.updated_at)
    audit_post(account, post, "post.update", before, post.updated_at, **text_flags)
    if post.status == "hidden" and before["status"] != "hidden":
        author_id = getattr(post, "author_id", None)
        if author_id is not None and author_id != account.user.id:
            from app.notifications import create_notification
            create_notification(
                account.db,
                recipient_user_id=author_id,
                type="moderation",
                target_type="post",
                target_id=post.id,
                actor_user_id=account.user.id,
                payload={
                    "action": "hidden",
                    "reason": reason or "Bài viết của bạn đã bị ẩn do vi phạm Tiêu chuẩn Cộng đồng.",
                    "post_title": (getattr(post, "title", None) or "")[:80],
                },
                dedupe_key=f"mod:post:{post.id}:hidden:{int(post.updated_at.timestamp())}",
                now=post.updated_at,
            )
    elif post.status == "deleted" and before["status"] != "deleted":
        post.deleted_at = post.updated_at
        author_id = getattr(post, "author_id", None)
        if author_id is not None and author_id != account.user.id:
            from app.notifications import create_notification
            create_notification(
                account.db,
                recipient_user_id=author_id,
                type="moderation",
                target_type="post",
                target_id=post.id,
                actor_user_id=account.user.id,
                payload={
                    "action": "deleted",
                    "reason": reason or "Bài viết của bạn đã bị xóa bởi Quản trị viên.",
                    "post_title": (getattr(post, "title", None) or "")[:80],
                },
                dedupe_key=f"mod:post:{post.id}:deleted",
                now=post.updated_at,
            )
    return post_dto(post, account.db.get(User, post.author_id), account.db.get(Profile, post.author_id), category)


@router.delete("/posts/{post_id}", status_code=204, operation_id="adminDeletePost", responses=ERRORS | NOT_FOUND,
               openapi_extra=CSRF_HEADER)
def delete_admin_post(post_id: UUID, request: Request, reason: str | None = Query(None, max_length=500),
                      account=Depends(require_admin_mutation, scope="function")):
    post = locked_post(account.db, post_id)
    before = post_state(post)
    post.status, post.deleted_at = "deleted", request.app.state.auth.now()
    post.updated_at = post.deleted_at
    from app.aura_runtime import reverse_post
    reverse_post(account.db, post.id, post.updated_at)
    audit_post(account, post, "post.delete", before, post.updated_at, **({"reason": reason} if reason else {}))
    author_id = getattr(post, "author_id", None)
    if author_id is not None and author_id != account.user.id:
        from app.notifications import create_notification
        create_notification(
            account.db,
            recipient_user_id=author_id,
            type="moderation",
            target_type="post",
            target_id=post.id,
            actor_user_id=account.user.id,
            payload={
                "action": "deleted",
                "reason": reason or "Bài viết của bạn đã bị xóa bởi Quản trị viên.",
                "post_title": (getattr(post, "title", None) or "")[:80],
            },
            dedupe_key=f"mod:post:{post.id}:deleted",
            now=post.updated_at,
        )


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


@router.get("/announcements", response_model=AnnouncementPage, operation_id="adminListAnnouncements",
            responses=ERRORS)
def list_admin_announcements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None, max_length=100),
    account=Depends(require_role("ADMIN"))
):
    statement = (
        select(Notification, User)
        .join(User, User.id == Notification.actor_user_id)
        .where(Notification.dedupe_key.like("master:%"))
    )
    rows, pagination = page_rows(account.db, statement.order_by(Notification.created_at.desc(), Notification.id.desc()), page, page_size)
    items = []
    for notif, user in rows:
        p = notif.payload or {}
        item_status = p.get("status", "published")
        if status and item_status != status:
            continue
        item_title = p.get("title", "")
        item_body = p.get("body", "")
        if search:
            s = search.lower()
            if s not in item_title.lower() and s not in item_body.lower():
                continue
        items.append(AnnouncementItem(
            id=notif.id,
            title=item_title,
            body=item_body,
            status=item_status,
            actor_id=user.id,
            actor_username=user.username,
            created_at=notif.created_at,
            published_at=datetime.fromisoformat(p["published_at"]) if p.get("published_at") else (notif.created_at if item_status == "published" else None),
            recipients_count=p.get("recipients_count", 0)
        ))
    return AnnouncementPage(items=items, pagination=pagination)


@router.post("/announcements", response_model=AnnouncementResponse, operation_id="adminCreateAnnouncement",
             responses=ERRORS, openapi_extra=CSRF_HEADER)
def create_admin_announcement(payload: AnnouncementInput, request: Request,
                              account=Depends(require_admin_mutation, scope="function")):
    now = request.app.state.auth.now()
    announcement_id = uuid4()
    is_draft = payload.is_draft

    if not is_draft:
        active_user_ids = account.db.scalars(
            select(User.id).where(User.status == "active")
        ).all()
        recipients_count = len(active_user_ids)
        if active_user_ids:
            notifications = [
                Notification(
                    id=uuid4(),
                    recipient_user_id=uid,
                    actor_user_id=account.user.id,
                    type="announcement",
                    target_type="system",
                    target_id=announcement_id,
                    payload={"title": payload.title, "body": payload.body, "announcement_id": str(announcement_id), "status": "published"},
                    created_at=now,
                    read_at=None,
                    dedupe_key=f"fanout:{announcement_id}:{uid}",
                )
                for uid in active_user_ids
            ]
            account.db.add_all(notifications)
        status_val = "published"
        published_at_val = now
    else:
        recipients_count = 0
        status_val = "draft"
        published_at_val = None

    master_notif = Notification(
        id=announcement_id,
        recipient_user_id=account.user.id,
        actor_user_id=account.user.id,
        type="announcement",
        target_type="system",
        target_id=announcement_id,
        payload={
            "title": payload.title,
            "body": payload.body,
            "status": status_val,
            "recipients_count": recipients_count,
            "created_at": now.isoformat(),
            "published_at": published_at_val.isoformat() if published_at_val else None
        },
        created_at=now,
        read_at=None,
        dedupe_key=f"master:{announcement_id}"
    )
    account.db.add(master_notif)

    account.db.add(AdminAuditLog(
        id=uuid4(),
        actor_id=account.user.id,
        action="announcement.draft" if is_draft else "announcement.create",
        target_type="system",
        target_id=str(announcement_id),
        before_json={},
        after_json={"title": payload.title, "status": status_val, "recipients_count": recipients_count},
        created_at=now
    ))
    account.db.flush()

    return AnnouncementResponse(
        success=True,
        recipients_count=recipients_count,
        created_at=now,
        id=announcement_id,
        status=status_val
    )


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementItem, operation_id="adminUpdateAnnouncement",
              responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def update_admin_announcement(announcement_id: UUID, payload: AnnouncementUpdateInput, request: Request,
                              account=Depends(require_admin_mutation, scope="function")):
    now = request.app.state.auth.now()
    master = account.db.scalar(
        select(Notification).where(
            Notification.id == announcement_id,
            Notification.dedupe_key == f"master:{announcement_id}"
        ).with_for_update()
    )
    if master is None:
        raise AuthError(404, "NOT_FOUND", "Announcement not found.")

    p = dict(master.payload or {})
    if p.get("status") != "draft":
        raise AuthError(409, "CONFLICT", "Only draft announcements can be edited.")

    before = dict(p)
    if payload.title is not None:
        p["title"] = payload.title
    if payload.body is not None:
        p["body"] = payload.body
    p["updated_at"] = now.isoformat()
    master.payload = p

    account.db.add(AdminAuditLog(
        id=uuid4(),
        actor_id=account.user.id,
        action="announcement.update",
        target_type="system",
        target_id=str(announcement_id),
        before_json=before,
        after_json=p,
        created_at=now
    ))
    account.db.flush()

    return AnnouncementItem(
        id=master.id,
        title=p.get("title", ""),
        body=p.get("body", ""),
        status="draft",
        actor_id=master.actor_user_id or account.user.id,
        actor_username=account.user.username,
        created_at=master.created_at,
        published_at=None,
        recipients_count=0
    )


@router.delete("/announcements/{announcement_id}", status_code=204, operation_id="adminDeleteAnnouncement",
               responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def delete_admin_announcement(announcement_id: UUID, request: Request,
                              account=Depends(require_admin_mutation, scope="function")):
    now = request.app.state.auth.now()
    master = account.db.scalar(
        select(Notification).where(
            Notification.id == announcement_id,
            Notification.dedupe_key == f"master:{announcement_id}"
        ).with_for_update()
    )
    if master is None:
        raise AuthError(404, "NOT_FOUND", "Announcement not found.")

    p = master.payload or {}
    if p.get("status") != "draft":
        raise AuthError(409, "CONFLICT", "Only draft announcements can be deleted.")

    account.db.add(AdminAuditLog(
        id=uuid4(),
        actor_id=account.user.id,
        action="announcement.delete",
        target_type="system",
        target_id=str(announcement_id),
        before_json=p,
        after_json={},
        created_at=now
    ))
    account.db.delete(master)
    account.db.flush()


@router.post("/announcements/{announcement_id}/publish", response_model=AnnouncementItem, operation_id="adminPublishAnnouncement",
             responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def publish_admin_announcement(announcement_id: UUID, request: Request,
                               account=Depends(require_admin_mutation, scope="function")):
    now = request.app.state.auth.now()
    master = account.db.scalar(
        select(Notification).where(
            Notification.id == announcement_id,
            Notification.dedupe_key == f"master:{announcement_id}"
        ).with_for_update()
    )
    if master is None:
        raise AuthError(404, "NOT_FOUND", "Announcement not found.")

    p = dict(master.payload or {})
    if p.get("status") != "draft":
        raise AuthError(409, "CONFLICT", "Only draft announcements can be published.")

    active_user_ids = account.db.scalars(
        select(User.id).where(User.status == "active")
    ).all()

    if active_user_ids:
        notifications = [
            Notification(
                id=uuid4(),
                recipient_user_id=uid,
                actor_user_id=account.user.id,
                type="announcement",
                target_type="system",
                target_id=announcement_id,
                payload={"title": p.get("title", ""), "body": p.get("body", ""), "announcement_id": str(announcement_id), "status": "published"},
                created_at=now,
                read_at=None,
                dedupe_key=f"fanout:{announcement_id}:{uid}",
            )
            for uid in active_user_ids
        ]
        account.db.add_all(notifications)

    p["status"] = "published"
    p["published_at"] = now.isoformat()
    p["recipients_count"] = len(active_user_ids)
    master.payload = p

    account.db.add(AdminAuditLog(
        id=uuid4(),
        actor_id=account.user.id,
        action="announcement.publish",
        target_type="system",
        target_id=str(announcement_id),
        before_json={"status": "draft"},
        after_json=p,
        created_at=now
    ))
    account.db.flush()

    return AnnouncementItem(
        id=master.id,
        title=p.get("title", ""),
        body=p.get("body", ""),
        status="published",
        actor_id=master.actor_user_id or account.user.id,
        actor_username=account.user.username,
        created_at=master.created_at,
        published_at=now,
        recipients_count=len(active_user_ids)
    )


@router.post("/announcements/{announcement_id}/withdraw", response_model=AnnouncementItem, operation_id="adminWithdrawAnnouncement",
             responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def withdraw_admin_announcement(announcement_id: UUID, request: Request,
                                account=Depends(require_admin_mutation, scope="function")):
    now = request.app.state.auth.now()
    master = account.db.scalar(
        select(Notification).where(
            Notification.id == announcement_id,
            Notification.dedupe_key == f"master:{announcement_id}"
        ).with_for_update()
    )
    if master is None:
        raise AuthError(404, "NOT_FOUND", "Announcement not found.")

    p = dict(master.payload or {})
    if p.get("status") != "published":
        raise AuthError(409, "CONFLICT", "Only published announcements can be withdrawn.")

    p["status"] = "withdrawn"
    p["withdrawn_at"] = now.isoformat()
    master.payload = p

    fanouts = account.db.scalars(
        select(Notification).where(
            Notification.target_id == announcement_id,
            Notification.type == "announcement"
        ).with_for_update()
    ).all()
    for f in fanouts:
        fp = dict(f.payload or {})
        fp["status"] = "withdrawn"
        f.payload = fp

    account.db.add(AdminAuditLog(
        id=uuid4(),
        actor_id=account.user.id,
        action="announcement.withdraw",
        target_type="system",
        target_id=str(announcement_id),
        before_json={"status": "published"},
        after_json=p,
        created_at=now
    ))
    account.db.flush()

    return AnnouncementItem(
        id=master.id,
        title=p.get("title", ""),
        body=p.get("body", ""),
        status="withdrawn",
        actor_id=master.actor_user_id or account.user.id,
        actor_username=account.user.username,
        created_at=master.created_at,
        published_at=datetime.fromisoformat(p["published_at"]) if p.get("published_at") else master.created_at,
        recipients_count=p.get("recipients_count", 0)
    )
