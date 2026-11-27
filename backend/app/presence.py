"""Single-process in-memory presence tracking (Heartbeat + TTL) and Admin summary API."""
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from threading import Lock
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth import origin_guard, set_cookie
from app.auth_schemas import ErrorResponse
from app.models import AuthSession, User
from app.permissions import require_role
from app.security import ABSOLUTE_SECONDS, AuthError, TOKEN, digest

HEARTBEAT_INTERVAL_SECONDS = 30
PRESENCE_TTL_SECONDS = 90
MAX_PRESENCE_ENTRIES = 16384

router = APIRouter(prefix="/api/v1", tags=["Presence"])


class HeartbeatAck(BaseModel):
    status: Literal["ok"] = "ok"
    interval_seconds: int = Field(ge=1)
    window_seconds: int = Field(ge=1)


class PresenceSummary(BaseModel):
    active_total: int = Field(ge=0)
    active_users: int = Field(ge=0)
    active_guests: int = Field(ge=0)
    window_seconds: int = Field(ge=1)
    generated_at: datetime


class PresenceStore:
    """Thread-safe, bounded-capacity, single-process TTL store for user sessions and guest tokens."""

    def __init__(
        self,
        ttl_seconds: int = PRESENCE_TTL_SECONDS,
        max_entries: int = MAX_PRESENCE_ENTRIES,
        mono_clock=None,
        wall_clock=None,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.mono_clock = mono_clock or time.monotonic
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self._lock = Lock()
        self._user_sessions: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._guest_tokens: OrderedDict[str, float] = OrderedDict()

    def _prune_locked(self, now: float) -> None:
        while self._user_sessions:
            _, (_, expiry) = next(iter(self._user_sessions.items()))
            if expiry > now:
                break
            self._user_sessions.popitem(last=False)
        while self._guest_tokens:
            _, expiry = next(iter(self._guest_tokens.items()))
            if expiry > now:
                break
            self._guest_tokens.popitem(last=False)

    def record_user_session(self, session_id: str, user_id: str, guest_digest: str | None = None) -> None:
        now = self.mono_clock()
        expiry = now + self.ttl_seconds
        with self._lock:
            self._prune_locked(now)
            if guest_digest:
                self._guest_tokens.pop(guest_digest, None)
            if session_id in self._user_sessions:
                self._user_sessions.move_to_end(session_id)
            elif len(self._user_sessions) >= self.max_entries:
                self._user_sessions.popitem(last=False)
            self._user_sessions[session_id] = (user_id, expiry)

    def record_guest(self, guest_digest: str) -> None:
        now = self.mono_clock()
        expiry = now + self.ttl_seconds
        with self._lock:
            self._prune_locked(now)
            if guest_digest in self._guest_tokens:
                self._guest_tokens.move_to_end(guest_digest)
            elif len(self._guest_tokens) >= self.max_entries:
                self._guest_tokens.popitem(last=False)
            self._guest_tokens[guest_digest] = expiry

    def remove_session(self, session_id: str) -> None:
        with self._lock:
            self._user_sessions.pop(session_id, None)

    def remove_guest(self, guest_digest: str) -> None:
        with self._lock:
            self._guest_tokens.pop(guest_digest, None)

    def snapshot(self) -> PresenceSummary:
        now = self.mono_clock()
        with self._lock:
            self._prune_locked(now)
            distinct_users = len({uid for uid, _ in self._user_sessions.values()})
            active_guests = len(self._guest_tokens)
        return PresenceSummary(
            active_total=distinct_users + active_guests,
            active_users=distinct_users,
            active_guests=active_guests,
            window_seconds=self.ttl_seconds,
            generated_at=self.wall_clock(),
        )


def _guest_cookie_name(runtime) -> str:
    return "__Host-am_guest" if runtime.secure else "am_guest"


def _session_cookie_name(runtime) -> str:
    return "__Host-am_session" if runtime.secure else "am_session"


@router.post(
    "/presence/heartbeat",
    response_model=HeartbeatAck,
    operation_id="presenceHeartbeat",
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
def heartbeat(request: Request, response: Response) -> HeartbeatAck:
    origin_guard(request)
    runtime = request.app.state.auth
    store: PresenceStore = request.app.state.presence
    raw_session = request.cookies.get(_session_cookie_name(runtime)) or request.cookies.get("am_session")
    guest_cookie = _guest_cookie_name(runtime)
    raw_guest = request.cookies.get(guest_cookie) or request.cookies.get("am_guest")
    guest_hash = digest(raw_guest) if raw_guest and TOKEN.fullmatch(raw_guest) else None

    if raw_session is not None:
        if not TOKEN.fullmatch(raw_session):
            raise AuthError(401, "UNAUTHORIZED", "Invalid or expired session.")
        token_hash = digest(raw_session)
        now_utc = runtime.now()
        # Read-only lookup: never lock or mutate session/user rows on presence heartbeat.
        with request.app.state.auth_session_factory() as db:
            row = db.execute(
                select(
                    AuthSession.id,
                    AuthSession.user_id,
                    AuthSession.created_at,
                    AuthSession.expires_at,
                    AuthSession.revoked_at,
                    User.status,
                )
                .join(User, User.id == AuthSession.user_id)
                .where(AuthSession.token_hash == token_hash)
            ).one_or_none()
        if (
            row is None
            or row.revoked_at is not None
            or row.expires_at <= now_utc
            or row.created_at > now_utc
            or row.created_at + timedelta(seconds=ABSOLUTE_SECONDS) <= now_utc
            or row.status != "active"
        ):
            raise AuthError(401, "UNAUTHORIZED", "Invalid or expired session.")
        runtime.limiter.check(f"presence-hb:user:{row.user_id}", 12, 60)
        store.record_user_session(str(row.id), str(row.user_id), guest_digest=guest_hash)
    else:
        if not guest_hash:
            peer = request.client.host if request.client else "unknown"
            runtime.limiter.check(f"presence-hb:guest-new:{peer}", 30, 60)
            raw_guest = secrets.token_urlsafe(32)
            guest_hash = digest(raw_guest)
            set_cookie(response, runtime, guest_cookie, raw_guest, 86400 * 7)
        runtime.limiter.check(f"presence-hb:guest:{guest_hash}", 12, 60)
        store.record_guest(guest_hash)

    return HeartbeatAck(
        status="ok",
        interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
        window_seconds=store.ttl_seconds,
    )


@router.get(
    "/admin/presence",
    response_model=PresenceSummary,
    operation_id="getAdminPresence",
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
def admin_presence(request: Request, response: Response, account=Depends(require_role("ADMIN"), scope="function")) -> PresenceSummary:
    response.headers["Cache-Control"] = "no-store"
    return request.app.state.presence.snapshot()
