"""Input safety screening before any generation runs.

With a Gemini key, portraits are classified by a vision model; photos that are sexually explicit,
violent, or that appear to show a minor are refused (biometric processing of children is off
limits). Without a key the check is skipped and logged, which is only acceptable in development.
"""

import asyncio
import logging

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.spend import record_paid_call
from app.services import gemini

log = logging.getLogger(__name__)

_INSTRUCTIONS = (
    "You screen photos uploaded to a virtual clothing try-on service. Decide whether the photo is "
    "acceptable. Refuse it if it is sexually explicit or nude, graphically violent, or if the "
    "person appears to be under 18. A normal portrait or full-body photo of an adult is allowed."
)


class Verdict(BaseModel):
    allowed: bool
    reason: str


class ContentRefused(ValueError):
    pass


async def screen_portrait(photo: bytes) -> None:
    s = get_settings()
    if s.use_mock or not s.gemini_api_key:
        log.info("Safety screening skipped (no GEMINI_API_KEY)")
        return
    record_paid_call("gemini")
    try:
        verdict = await asyncio.to_thread(
            gemini.classify_image, s.gemini_text_model, photo, _INSTRUCTIONS, Verdict
        )
    except gemini.GeminiError as exc:
        # Fail closed in production, open in development so a flaky key doesn't block local work.
        if s.is_production:
            raise ContentRefused("We couldn't verify this photo right now. Please try again.") from exc
        log.warning("Safety screening unavailable: %s", exc)
        return
    if not verdict.allowed:
        raise ContentRefused("This photo can't be used. Please upload a clear photo of an adult.")
