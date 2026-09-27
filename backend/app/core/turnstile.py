"""Cloudflare Turnstile verification for signup, login and password-reset forms."""

import logging

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings

log = logging.getLogger(__name__)
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_human(token: str | None, remote_ip: str | None) -> None:
    settings = get_settings()
    if not settings.turnstile_secret_key:
        # Only reachable outside production: config validation requires the key in production.
        return
    if not token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please complete the human check.")
    try:
        async with httpx.AsyncClient(timeout=8) as http:
            resp = await http.post(
                VERIFY_URL,
                data={
                    "secret": settings.turnstile_secret_key,
                    "response": token,
                    **({"remoteip": remote_ip} if remote_ip else {}),
                },
            )
            result = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Turnstile verification unavailable: %s", type(exc).__name__)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Human check is unavailable, try again shortly."
        ) from exc
    if not result.get("success"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Human check failed. Please try again.")
