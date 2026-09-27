"""HTTP middleware: request IDs + access logs, HTTPS enforcement, security headers, CSRF."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from app.core.config import get_settings
from app.core.logging import request_id_var
from app.core.security import constant_time_equal

log = logging.getLogger("lookbook.access")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "x-csrf-token"
# Endpoints authenticated by something other than cookies (so CSRF doesn't apply):
CSRF_EXEMPT_PREFIXES = (
    "/api/v1/live/widget-token",  # merchant publishable key + origin allowlist
    "/api/v1/media/local/",  # HMAC-signed, expiring upload/download URLs
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request ID (echoed as X-Request-ID) and writes one access-log line per request.
    Query strings are never logged: signed URLs carry credentials there."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if 8 <= len(incoming) <= 64 and incoming.isascii() else uuid.uuid4().hex
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            log.info(
                "%s %s %s",
                request.method,
                request.url.path,
                status,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)


class HttpsAndHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if settings.https_only and request.url.scheme != "https" and request.url.path not in (
            "/healthz",
            "/readyz",
        ):
            # Behind a TLS-terminating proxy, uvicorn's --proxy-headers sets the scheme.
            return RedirectResponse(request.url.replace(scheme="https"), status_code=308)

        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        h.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        if request.url.path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")
        if settings.https_only:
            h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response


class CsrfMiddleware(BaseHTTPMiddleware):
    """Double-submit CSRF protection plus an Origin allowlist for state-changing requests.

    The browser gets a random token in a readable cookie (GET /api/v1/auth/csrf) and must echo it
    in the X-CSRF-Token header. A cross-site attacker can make the browser send cookies but can't
    read them, so they can't produce the header. SameSite=Lax session cookies are a second layer.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in SAFE_METHODS or not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.url.path.startswith(CSRF_EXEMPT_PREFIXES):
            return await call_next(request)

        settings = get_settings()
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in settings.allowed_origins:
            return JSONResponse({"detail": "Cross-origin request blocked."}, status_code=403)

        cookie = request.cookies.get(settings.csrf_cookie_name, "")
        header = request.headers.get(CSRF_HEADER, "")
        if not cookie or not header or not constant_time_equal(cookie, header):
            return JSONResponse(
                {"detail": "Security token missing or expired. Refresh the page and try again."},
                status_code=403,
            )
        return await call_next(request)
