"""Bounded single-process abuse protection and session-bound CSRF primitives."""
from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import math
import re
import secrets
from threading import Lock
import time
from starlette.responses import JSONResponse
from uuid import uuid4

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError


TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
PRE_TTL = 600
IDLE_SECONDS = 1800
ABSOLUTE_SECONDS = 43200


class AuthError(Exception):
    def __init__(self, status, code, message, retry_after=None):
        self.status, self.code, self.message = status, code, message
        self.retry_after = retry_after


def digest(token):
    return sha256(token.encode()).hexdigest()


class RateLimiter:
    """Single process only; fail closed when all bounded slots are occupied."""
    def __init__(self):
        self.entries = {}
        self.lock = Lock()
        self.clock = time.monotonic

    def check(self, key, limit, window):
        now = self.clock()
        with self.lock:
            for item in list(self.entries):
                queue, lifetime = self.entries[item]
                while queue and queue[0] <= now - lifetime:
                    queue.popleft()
                if not queue:
                    del self.entries[item]
            if key not in self.entries:
                if len(self.entries) >= 4096:
                    raise AuthError(429, "RATE_LIMITED", "Too many requests.", 60)
                self.entries[key] = (deque(), window)
            queue, _ = self.entries[key]
            if len(queue) >= limit:
                raise AuthError(429, "RATE_LIMITED", "Too many requests.", max(1, math.ceil(queue[0] + window - now)))
            queue.append(now)


class AuthRuntime:
    def __init__(self, settings):
        self.settings = settings
        self.key = settings.auth_signing_key.get_secret_value().encode()
        self.hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, type=Type.ID)
        self.dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))
        self.limiter = RateLimiter()
        self.pre_sessions = {}
        self.lock = Lock()
        self.now = lambda: datetime.now(timezone.utc)

    @property
    def secure(self):
        return self.settings.auth_environment == "production"

    @property
    def pre_cookie(self):
        return "__Host-am_pre" if self.secure else "am_pre"

    def pre_session(self, raw, create=False):
        now = self.now().timestamp()
        with self.lock:
            self.pre_sessions = {key: expiry for key, expiry in self.pre_sessions.items() if expiry > now}
            if raw and TOKEN.fullmatch(raw) and digest(raw) in self.pre_sessions:
                return raw
            if not create:
                raise AuthError(403, "CSRF_INVALID", "Invalid CSRF token or pre-session.")
            if len(self.pre_sessions) >= 4096:
                raise AuthError(429, "RATE_LIMITED", "Too many pre-sessions.", PRE_TTL)
            raw = secrets.token_urlsafe(32)
            self.pre_sessions[digest(raw)] = now + PRE_TTL
            return raw

    def consume_pre(self, raw):
        with self.lock:
            if self.pre_sessions.pop(digest(raw), 0) <= self.now().timestamp():
                raise AuthError(403, "CSRF_INVALID", "Invalid CSRF token or pre-session.")

    def csrf(self, binding, nonce=None):
        nonce = nonce or secrets.token_urlsafe(32)
        mac = hmac.new(self.key, (binding + ":" + nonce).encode(), "sha256").hexdigest()
        return nonce + "." + mac

    def verify_csrf(self, token, binding):
        if not token or not re.fullmatch(r"[A-Za-z0-9_-]{43}\.[0-9a-f]{64}", token):
            raise AuthError(403, "CSRF_INVALID", "Invalid CSRF token.")
        if not hmac.compare_digest(token, self.csrf(binding, token[:43])):
            raise AuthError(403, "CSRF_INVALID", "Invalid CSRF token.")

    def verify_password(self, encoded, password):
        # Login never silently truncates; excessively large input is rejected before Argon2.
        if len(password) > 128:
            return False
        try:
            return self.hasher.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            return False


class AuthBoundaryMiddleware:
    """Cap auth bodies before parsing and rate-limit before expensive password work."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith(("/api/v1/auth/", "/api/v1/users/", "/api/v1/posts", "/api/v1/categories", "/api/v1/admin/categories", "/api/v1/media", "/api/v1/comments/")):
            return await self.app(scope, receive, send)
        runtime = scope["app"].state.auth
        try:
            if runtime.secure and scope["scheme"] != "https":
                raise AuthError(403, "FORBIDDEN", "Authentication requires HTTPS.")
            peer = scope.get("client", ("unknown",))[0]
            runtime.limiter.check("ip:" + peer, 120, 60)
            limit = {"register": 5, "login": 10}.get(scope["path"].rsplit("/", 1)[-1], 60)
            runtime.limiter.check(scope["path"] + ":" + peer, limit, 60)
            if scope["path"] == "/api/v1/media" and scope["method"] == "POST":
                from app.media import MAX_REQUEST_BYTES
                size = 0
                lengths = [value for name, value in scope["headers"] if name == b"content-length"]
                declared = None

                async def bounded_receive():
                    nonlocal size, declared
                    if size == 0 and lengths:
                        if len(lengths) != 1 or not lengths[0].isdigit() or len(lengths[0]) > 10:
                            raise AuthError(422, "VALIDATION_ERROR", "Invalid Content-Length.")
                        declared = int(lengths[0])
                        if declared > MAX_REQUEST_BYTES:
                            raise AuthError(422, "VALIDATION_ERROR", "Request body too large.")
                    event = await receive()
                    if event["type"] == "http.request":
                        size += len(event.get("body", b""))
                        if size > MAX_REQUEST_BYTES or (declared is not None and size > declared):
                            raise AuthError(422, "VALIDATION_ERROR", "Request body too large.")
                        if not event.get("more_body", False) and declared is not None and size != declared:
                            raise AuthError(422, "VALIDATION_ERROR", "Incomplete request body.")
                    return event

                # No body is read until the endpoint's authenticated, CSRF-checked dependency yields.
                return await self.app(scope, bounded_receive, send)
            if scope["method"] in {"POST", "PATCH", "PUT"}:
                body_limit = 262144 if scope["path"].startswith("/api/v1/posts") else 16384
                chunks, size = [], 0
                while True:
                    event = await receive()
                    if event["type"] == "http.disconnect":
                        return
                    body = event.get("body", b"")
                    size += len(body)
                    if size > body_limit:
                        raise AuthError(422, "VALIDATION_ERROR", "Request body too large.")
                    chunks.append(body)
                    if not event.get("more_body", False):
                        break
                consumed = False

                async def replay():
                    nonlocal consumed
                    if not consumed:
                        consumed = True
                        return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
                    return await receive()

                return await self.app(scope, replay, send)
        except AuthError as error:
            headers = {"Cache-Control": "no-store"}
            if error.retry_after:
                headers["Retry-After"] = str(error.retry_after)
            response = JSONResponse({"error": {"code": error.code, "message": error.message,
                                               "request_id": "req_" + uuid4().hex}},
                                    status_code=error.status, headers=headers)
            return await response(scope, receive, send)
        await self.app(scope, receive, send)
