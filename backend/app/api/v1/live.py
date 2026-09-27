"""Short-lived Decart client tokens for realtime (live camera) try-on.

The Decart API key never leaves the server. Tokens are scoped to the try-on model, the app's
origin, a 5-minute session and a 10-minute lifetime.

Two callers:
- signed-in LOOKBOOK users (session cookie + CSRF), rate limited per user;
- the embeddable store widget, identified by a merchant's publishable key. Publishable keys are
  public by design, so they're constrained by the merchant's origin allowlist (also enforced by the
  browser through CSP frame-ancestors on /embed), per-IP rate limits and a daily session cap.
"""

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB, CurrentUser, client_ip
from app.core.config import get_settings
from app.core.rate_limit import check_rate_limit
from app.core.redis import async_redis
from app.db.models import Merchant

router = APIRouter(prefix="/live", tags=["live"])
log = logging.getLogger(__name__)
DECART_TOKENS_URL = "https://api.decart.ai/v1/client/tokens"


class LiveTokenOut(BaseModel):
    mock: bool
    api_key: str | None = None
    expires_at: str | None = None
    model: str


class FramePolicyOut(BaseModel):
    allowed_origins: list[str]


async def _mint() -> LiveTokenOut:
    s = get_settings()
    if not s.decart_api_key:
        return LiveTokenOut(mock=True, model=s.live_model)
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.post(
                DECART_TOKENS_URL,
                headers={"X-API-KEY": s.decart_api_key, "content-type": "application/json"},
                json={
                    "expiresIn": 600,
                    "allowedModels": [s.live_model],
                    "allowedOrigins": [s.app_url.rstrip("/")],
                    "constraints": {"realtime": {"maxSessionDuration": 300}},
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Live try-on is unavailable right now.") from exc
    if resp.status_code >= 400:
        log.warning("Decart token request failed with status %s", resp.status_code)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Live try-on is unavailable right now.")
    data = resp.json()
    return LiveTokenOut(mock=False, api_key=data["apiKey"], expires_at=data.get("expiresAt"), model=s.live_model)


@router.post("/token", response_model=LiveTokenOut)
async def user_token(user: CurrentUser):
    await check_rate_limit(f"live:{user.id}", get_settings().rate_live_token_per_minute, 60)
    return await _mint()


async def _merchant(db, key: str) -> Merchant:
    merchant = await db.scalar(
        select(Merchant).where(Merchant.publishable_key == key, Merchant.is_active.is_(True))
    )
    if not merchant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown or disabled store key.")
    return merchant


@router.post("/widget-token", response_model=LiveTokenOut)
async def widget_token(
    request: Request,
    db: DB,
    x_lookbook_key: str = Header(max_length=64),
    x_lookbook_host: str = Header(default="", max_length=255),
):
    """Called by /embed (our origin) on behalf of a merchant page (X-Lookbook-Host)."""
    s = get_settings()
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin not in s.allowed_origins:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Widget tokens are only issued to the embed page.")
    merchant = await _merchant(db, x_lookbook_key)
    if x_lookbook_host.rstrip("/") not in merchant.allowed_origins:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This site isn't allowed to use this store key.")
    await check_rate_limit(f"widget:ip:{client_ip(request)}", s.rate_live_token_per_minute, 60)

    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    counter = f"widget:sessions:{merchant.id}:{day}"
    used = await async_redis().incr(counter)
    await async_redis().expire(counter, 90000)
    if used > merchant.daily_session_limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Live try-on is busy for this store today.")
    return await _mint()


@router.get("/frame-policy/{key}", response_model=FramePolicyOut)
async def frame_policy(key: str, db: DB):
    """Used by the frontend proxy to set CSP frame-ancestors on /embed for this merchant."""
    merchant = await _merchant(db, key)
    return FramePolicyOut(allowed_origins=merchant.allowed_origins)
