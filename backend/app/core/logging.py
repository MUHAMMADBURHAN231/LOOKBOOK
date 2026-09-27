"""Structured logging with request IDs and automatic secret redaction.

Every log record passes through `RedactingFilter`, which scrubs passwords, tokens, API keys,
cookies, bearer credentials, card numbers and email local-parts before anything is written.
"""

import contextvars
import json
import logging
import re
import sys
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_SENSITIVE_KEYS = (
    r"password|passwd|pwd|secret|token|api[_-]?key|authorization|cookie|session|csrf|"
    r"set-cookie|x-api-key|access[_-]?key|private[_-]?key|card|cvv|cvc"
)
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Credentials after an auth scheme first, so "Authorization: Bearer x" loses x, not "Bearer".
    (re.compile(r"(?i)\b(bearer|basic)\s+[a-z0-9._~+/=-]+"), r"\1 [REDACTED]"),
    # key=value, key: value, "key": "value"
    (
        re.compile(
            rf"(?i)([\"']?\b[\w-]*(?:{_SENSITIVE_KEYS})[\w-]*[\"']?\s*[:=]\s*[\"']?)([^\"'\s,;&}}]+)"
        ),
        r"\1[REDACTED]",
    ),
    # Provider-style keys: Google AIza..., AQ. auth keys, Replicate r8_, Decart, OpenAI-style sk-
    (re.compile(r"\b(AIza[0-9A-Za-z_-]{20,}|AQ\.[0-9A-Za-z_.-]{20,}|r8_[0-9A-Za-z]{20,}|sk-[0-9A-Za-z_-]{20,}|ek_[0-9A-Za-z_-]{16,})\b"), "[REDACTED_KEY]"),
    # JWTs
    (re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}\b"), "[REDACTED_JWT]"),
    # Email local part: jane.doe@example.com -> j***@example.com
    (re.compile(r"\b([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"), r"\1***@\2"),
]
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def redact(text: str) -> str:
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)

    def _card(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return "[REDACTED_CARD]" if 13 <= len(digits) <= 19 and _luhn_ok(digits) else m.group(0)

    return _CARD.sub(_card, text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if record.exc_info:
            message += "\n" + logging.Formatter().formatException(record.exc_info)
            record.exc_info = None
            record.exc_text = None
        record.msg = redact(message)
        record.args = ()
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key in ("method", "path", "status", "duration_ms", "user_id", "task_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(
        JsonFormatter()
        if json_logs
        else logging.Formatter("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Uvicorn's access log prints full URLs (which can carry signed-URL tokens); we log our own.
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("httpx", "botocore", "urllib3", "celery.app.trace"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
