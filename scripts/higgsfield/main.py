"""Generate a video with Seedance 2.5 through the Higgsfield API.

    pip install -r scripts/higgsfield/requirements.txt
    python scripts/higgsfield/main.py

Credentials: HF_KEY in "key-id:key-secret" form, read from the environment or from .env.local at
the repository root (git-ignored). The value is never printed. Each run is a billable generation.

Exit status is 0 only when the request completed and returned a video URL; failed, cancelled and
moderated requests, missing credentials and API errors all exit non-zero.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import higgsfield_client
from dotenv import load_dotenv

MODEL = "bytedance/seedance-2.5/text-to-video"
ARGUMENTS = {
    "prompt": "A cinematic scene at sunset",
    "duration": 5,
    "resolution": "720p",
    "aspect_ratio": "16:9",
}

ROOT = Path(__file__).resolve().parents[2]


def find_video_url(result: dict[str, Any]) -> str | None:
    """Return the first video URL in a completed result."""
    video = result.get("video")
    if isinstance(video, dict) and isinstance(video.get("url"), str):
        return video["url"]
    for key in ("videos", "outputs"):
        items = result.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("url"), str):
                    return item["url"]
    return None


def main() -> int:
    # An HF_KEY already in the environment (for example a deployment secret) takes precedence.
    load_dotenv(ROOT / ".env.local", override=False)

    def on_enqueue(request_id: str) -> None:
        print(f"Submitted request {request_id}")

    def on_update(status: higgsfield_client.Status) -> None:
        print(f"Status: {type(status).__name__}")

    try:
        result = higgsfield_client.subscribe(
            MODEL,
            arguments=ARGUMENTS,
            on_enqueue=on_enqueue,
            on_queue_update=on_update,
        )
    except higgsfield_client.CredentialsMissedError:
        print("HF_KEY is not set. Add it to .env.local (key-id:key-secret) or the environment.", file=sys.stderr)
        return 2
    except higgsfield_client.HiggsfieldClientError as exc:
        print(f"Higgsfield API error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # network failures, timeouts
        print(f"Request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    # subscribe() returns the final payload whatever the outcome, so check the status explicitly.
    status = result.get("status")
    if status != "completed":
        reasons = {"failed": "failed", "nsfw": "was blocked by content moderation", "canceled": "was cancelled"}
        print(f"Generation {reasons.get(status, f'ended with status {status!r}')}.", file=sys.stderr)
        return 1

    url = find_video_url(result)
    if not url:
        print(f"Completed, but no video URL in the response (keys: {sorted(result)}).", file=sys.stderr)
        return 1

    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
