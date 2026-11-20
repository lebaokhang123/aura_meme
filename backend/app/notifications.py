"""User notifications inbox, read states, and mutation helpers."""
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, not_, or_, select, update
from sqlalchemy.orm import Session

from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import Pagination, page_rows
from app.models import Notification, Profile, User
from app.permissions import require_account_csrf, require_authenticated_user
from app.security import AuthError

NOT_FOUND = {404: {"model": ErrorResponse}}

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


class ActorSummary(BaseModel):
    id: UUID
    username: str
    display_name: str
    avatar_url: str | None = None


class NotificationItem(BaseModel):
    id: UUID
    type: str
    target_type: str
    target_id: UUID | None = None
    actor: ActorSummary | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime
    read_at: datetime | None = None
    is_read: bool


class NotificationPage(BaseModel):
    items: list[NotificationItem]
    pagination: Pagination
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkReadAllResponse(BaseModel):
    marked_read: int


def create_notification(
    db: Session,
    *,
    recipient_user_id: UUID,
    type: str,
    target_type: str,
    target_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    payload: dict | None = None,
    dedupe_key: str | None = None,
    now: datetime
) -> Notification | None:
    """Internal helper to create a notification within the caller's transaction."""
    # Self-interaction guard: users never get notified of their own actions
    if actor_user_id is not None and recipient_user_id == actor_user_id:
        return None

    # Deduplication check
    if dedupe_key:
        existing = db.scalar(select(Notification).where(Notification.dedupe_key == dedupe_key))
        if existing is not None:
            if payload is not None and existing.payload != payload:
                existing.payload = payload
                db.flush()
            return existing

    item = Notification(
        id=uuid4(),
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        type=type,
        target_type=target_type,
        target_id=target_id,
        payload=payload or {},
        created_at=now,
        read_at=None,
        dedupe_key=dedupe_key
    )
    db.add(item)
    db.flush()
    return item


@router.get("", response_model=NotificationPage, operation_id="getNotifications", responses=ERRORS)
def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    account=Depends(require_authenticated_user, scope="function")
):
    db = account.db
    user_id = account.user.id
    query = select(Notification).where(
        Notification.recipient_user_id == user_id,
        or_(Notification.dedupe_key.is_(None), not_(Notification.dedupe_key.like("master:%")))
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))

    rows, pagination = page_rows(db, query.order_by(Notification.created_at.desc(), Notification.id.desc()), page, page_size)

    actor_ids = {row[0].actor_user_id for row in rows if row[0].actor_user_id}
    actors = {}
    if actor_ids:
        actor_users = db.execute(
            select(User, Profile)
            .join(Profile, Profile.user_id == User.id)
            .where(User.id.in_(actor_ids))
        ).all()
        for u, p in actor_users:
            actors[u.id] = ActorSummary(id=u.id, username=u.username, display_name=p.display_name, avatar_url=p.avatar_url)

    unread_count = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.recipient_user_id == user_id,
            Notification.read_at.is_(None),
            or_(Notification.dedupe_key.is_(None), not_(Notification.dedupe_key.like("master:%")))
        )
    ) or 0

    items = [
        NotificationItem(
            id=notif.id,
            type=notif.type,
            target_type=notif.target_type,
            target_id=notif.target_id,
            actor=actors.get(notif.actor_user_id) if notif.actor_user_id else None,
            payload=notif.payload or {},
            created_at=notif.created_at,
            read_at=notif.read_at,
            is_read=notif.read_at is not None
        )
        for (notif,) in rows
    ]

    return NotificationPage(items=items, pagination=pagination, unread_count=unread_count)


@router.get("/unread-count", response_model=UnreadCountResponse, operation_id="getUnreadCount", responses=ERRORS)
def get_unread_count(
    account=Depends(require_authenticated_user, scope="function")
):
    count = account.db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.recipient_user_id == account.user.id,
            Notification.read_at.is_(None),
            or_(Notification.dedupe_key.is_(None), not_(Notification.dedupe_key.like("master:%")))
        )
    ) or 0
    return UnreadCountResponse(unread_count=count)


@router.patch("/{notification_id}/read", response_model=NotificationItem, operation_id="markNotificationRead",
             responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def mark_read(
    notification_id: UUID,
    request: Request,
    account=Depends(require_account_csrf)
):
    now = request.app.state.auth.now()
    notif = account.db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == account.user.id
        ).with_for_update()
    )
    if notif is None:
        raise AuthError(404, "NOT_FOUND", "Notification not found.")

    if notif.read_at is None:
        notif.read_at = now
        account.db.flush()

    actor_summary = None
    if notif.actor_user_id:
        actor_row = account.db.execute(
            select(User, Profile)
            .join(Profile, Profile.user_id == User.id)
            .where(User.id == notif.actor_user_id)
        ).one_or_none()
        if actor_row:
            u, p = actor_row
            actor_summary = ActorSummary(id=u.id, username=u.username, display_name=p.display_name, avatar_url=p.avatar_url)

    return NotificationItem(
        id=notif.id,
        type=notif.type,
        target_type=notif.target_type,
        target_id=notif.target_id,
        actor=actor_summary,
        payload=notif.payload or {},
        created_at=notif.created_at,
        read_at=notif.read_at,
        is_read=True
    )


@router.post("/read-all", response_model=MarkReadAllResponse, operation_id="markAllNotificationsRead",
             responses=ERRORS, openapi_extra=CSRF_HEADER)
def mark_all_read(
    request: Request,
    account=Depends(require_account_csrf)
):
    now = request.app.state.auth.now()
    res = account.db.execute(
        update(Notification)
        .where(
            Notification.recipient_user_id == account.user.id,
            Notification.read_at.is_(None),
            or_(Notification.dedupe_key.is_(None), not_(Notification.dedupe_key.like("master:%")))
        )
        .values(read_at=now)
    )
    return MarkReadAllResponse(marked_read=res.rowcount or 0)


@router.delete("/{notification_id}", status_code=204, operation_id="deleteNotification",
               responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def delete_notification(
    notification_id: UUID,
    request: Request,
    account=Depends(require_account_csrf)
):
    notif = account.db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == account.user.id
        ).with_for_update()
    )
    if notif is None:
        raise AuthError(404, "NOT_FOUND", "Notification not found.")

    account.db.delete(notif)
    account.db.flush()
