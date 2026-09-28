"""Create the root .env for `docker compose up`, with freshly generated secrets.

    python scripts/setup_env.py

Copies .env.docker.example to .env and fills in every blank secret. Values already present in an
existing .env are kept, so it is safe to run again after adding API keys. Uses only the standard
library and works on Windows, macOS and Linux.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.docker.example"
TARGET = ROOT / ".env"

GENERATED = {
    "SECRET_KEY": lambda: secrets.token_urlsafe(48),
    "POSTGRES_SUPERUSER_PASSWORD": lambda: secrets.token_urlsafe(32),
    "DB_OWNER_PASSWORD": lambda: secrets.token_urlsafe(32),
    "DB_APP_PASSWORD": lambda: secrets.token_urlsafe(32),
    "REDIS_PASSWORD": lambda: secrets.token_urlsafe(32),
    "S3_SECRET_ACCESS_KEY": lambda: secrets.token_urlsafe(32),
    "S3_SSE_KEK": lambda: secrets.token_hex(32),
}


def parse(path: Path) -> dict[str, str]:
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value
    return values


def main() -> int:
    if not EXAMPLE.exists():
        print(f"Missing {EXAMPLE.name}; run this from a LOOKBOOK checkout.")
        return 1
    existing = parse(TARGET)
    out, generated = [], []
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            out.append(line)
            continue
        key, _, default = line.partition("=")
        key = key.strip()
        value = existing.get(key, "") or default
        if not value and key in GENERATED:
            value = GENERATED[key]()
            generated.append(key)
        out.append(f"{key}={value}")
    # Keep any extra keys the user added by hand.
    known = {line.partition("=")[0].strip() for line in out if "=" in line}
    extras = [f"{k}={v}" for k, v in existing.items() if k not in known]
    if extras:
        out += ["", "# Added by hand"] + extras
    TARGET.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")

    print(f"Wrote {TARGET}")
    if generated:
        print("Generated: " + ", ".join(generated))
    if "DB_OWNER_PASSWORD" in generated and existing:
        print("Note: database passwords only apply to a new database volume. If you changed them,")
        print("reset the volume with `docker compose down -v` (this deletes local data).")
    missing = [k for k in ("GEMINI_API_KEY", "REPLICATE_API_TOKEN", "DECART_API_KEY") if not parse(TARGET).get(k)]
    if missing:
        print("No key yet for: " + ", ".join(missing) + " (the app runs in demo mode without them).")
    print("Next: docker compose up --build   then open http://localhost:3000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
