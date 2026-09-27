"""Cost controls: daily caps on paid AI calls, with webhook alerts before the budget runs out.

Paid calls are counted in Redis per UTC day. At 80% of the global budget an alert fires once;
at 100% new generation jobs are refused until the next day. This limits the damage from abuse
or a runaway bug, and complements billing alerts configured in each provider's dashboard.
"""

import logging
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.redis import async_redis, sync_redis

log = logging.getLogger(__name__)
_DAY_SECONDS = 86400 + 3600


def _day() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


async def ensure_capacity(user_id: str) -> None:
    """Refuse a new job when the user's or the platform's daily allowance is used up."""
    s = get_settings()
    r = async_redis()
    day = _day()
    used_global = int(await r.get(f"spend:global:{day}") or 0)
    if used_global >= s.daily_paid_call_budget:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Daily generation capacity reached. Please try again tomorrow.",
        )
    user_key = f"spend:user:{user_id}:{day}"
    used_user = await r.incr(user_key)
    await r.expire(user_key, _DAY_SECONDS)
    if used_user > s.daily_tryons_per_user:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You've reached today's limit of {s.daily_tryons_per_user} try-ons.",
        )


def record_paid_call(provider: str, count: int = 1) -> None:
    """Called by pipeline adapters (in workers) for every billable provider request."""
    s = get_settings()
    r = sync_redis()
    day = _day()
    key = f"spend:global:{day}"
    total = r.incrby(key, count)
    r.expire(key, _DAY_SECONDS)
    r.hincrby(f"spend:providers:{day}", provider, count)
    r.expire(f"spend:providers:{day}", _DAY_SECONDS)
    for threshold, label in ((0.8, "80%"), (1.0, "100%")):
        if total >= s.daily_paid_call_budget * threshold and r.set(
            f"spend:alerted:{day}:{label}", "1", nx=True, ex=_DAY_SECONDS
        ):
            send_alert(
                f"LOOKBOOK spend alert: {total}/{s.daily_paid_call_budget} paid AI calls used "
                f"today ({label} of daily budget)."
            )


def send_alert(text: str) -> None:
    log.warning(text)
    url = get_settings().alert_webhook_url
    if not url:
        return
    try:
        httpx.post(url, json={"text": text, "content": text}, timeout=5)
    except httpx.HTTPError as exc:
        log.error("Alert webhook failed: %s", type(exc).__name__)
