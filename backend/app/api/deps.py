"""Shared FastAPI dependencies: client IP, session authentication, cookie helpers."""

import ipaddress
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, WebSocket, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import new_token, token_hash
from app.db.models import AuthSession, User
from app.db.session import get_db

DB = Annotated[AsyncSession, Depends(get_db)]
_TOUCH_INTERVAL = timedelta(minutes=5)


def client_ip(request: Request | WebSocket) -> str:
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def ip_prefix(ip: str) -> str | None:
    """Store only the network part (/24 or /48) so sessions can be recognised without keeping
    users' full IP addresses."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    prefix = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_session(db: AsyncSession, user: User, request: Request, response: Response) -> None:
    s = get_settings()
    token = new_token()
    now = _now()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash(token),
            last_seen_at=now,
            idle_expires_at=now + timedelta(hours=s.session_idle_hours),
            absolute_expires_at=now + timedelta(days=s.session_absolute_days),
            user_agent=(request.headers.get("user-agent") or "")[:256],
            ip_prefix=ip_prefix(client_ip(request)),
        )
    )
    await db.commit()
    set_cookie(response, s.session_cookie_name, token, http_only=True, max_age=s.session_absolute_days * 86400)


def set_cookie(response: Response, name: str, value: str, *, http_only: bool, max_age: int) -> None:
    s = get_settings()
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=http_only,
        secure=s.secure_cookies,
        samesite="lax",
        domain=s.cookie_domain,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        s.session_cookie_name, domain=s.cookie_domain, path="/", secure=s.secure_cookies, httponly=True, samesite="lax"
    )


async def _session_user(db: AsyncSession, token: str | None) -> tuple[User, AuthSession] | None:
    if not token:
        return None
    now = _now()
    row = (
        await db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(
                AuthSession.token_hash == token_hash(token),
                AuthSession.revoked_at.is_(None),
                AuthSession.idle_expires_at > now,
                AuthSession.absolute_expires_at > now,
                User.is_active.is_(True),
            )
        )
    ).first()
    if not row:
        return None
    session, user = row
    if now - session.last_seen_at > _TOUCH_INTERVAL:
        # Sliding idle timeout, capped by the absolute expiry. Written at most every 5 minutes.
        idle = min(now + timedelta(hours=get_settings().session_idle_hours), session.absolute_expires_at)
        await db.execute(
            update(AuthSession)
            .where(AuthSession.id == session.id)
            .values(last_seen_at=now, idle_expires_at=idle)
        )
        await db.commit()
    return user, session


async def current_session(request: Request, db: DB) -> tuple[User, AuthSession]:
    found = await _session_user(db, request.cookies.get(get_settings().session_cookie_name))
    if not found:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    return found


async def current_user(found: Annotated[tuple[User, AuthSession], Depends(current_session)]) -> User:
    return found[0]


async def websocket_user(websocket: WebSocket, db: AsyncSession) -> User | None:
    """Cookie auth for WebSockets, plus an Origin check (browsers don't apply CORS to WS)."""
    origin = (websocket.headers.get("origin") or "").rstrip("/")
    if origin not in get_settings().allowed_origins:
        return None
    found = await _session_user(db, websocket.cookies.get(get_settings().session_cookie_name))
    return found[0] if found else None


CurrentUser = Annotated[User, Depends(current_user)]
CurrentSession = Annotated[tuple[User, AuthSession], Depends(current_session)]
