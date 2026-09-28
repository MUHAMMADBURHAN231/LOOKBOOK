"""Download the landing-page photos (generated with Higgsfield) into frontend/public/look/.

    pip install pillow
    python scripts/fetch_look_assets.py

Writes state-0..4.webp (the model dressing layer by layer) and garment-1..4.webp (flat-lay
cut-outs with transparency, trimmed to the garment). Existing files are overwritten.
"""

from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required: pip install pillow")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "look"
BASE = "https://d8j0ntlcm91z4.cloudfront.net/user_36JhwLmNUPMwPD50t2lUt7CHQRe/"

STATES = [
    "hf_20260928_130545_1d095306-f538-4620-90a1-cb38aa7c1531.png",  # white T-shirt and trousers
    "hf_20260928_131320_83eedc35-0d76-4f9d-8ff7-19d5fa46372c.png",  # + silk blouse
    "hf_20260928_131427_2d3a9d1c-a135-4051-a21c-75fac46d7019.png",  # + wide-leg trousers
    "hf_20260928_131506_ff5c2d37-2539-4abe-b48a-c2a48cdc274c.png",  # + blazer
    "hf_20260928_131541_67ab0ea4-fd5f-41b4-8647-66ac5adc8687.png",  # + overcoat
]
GARMENTS = [
    "hf_20260928_131318_3ae1c575-ef5e-4cac-b5fd-5d8c08ad4e78.png",  # blouse
    "hf_20260928_131321_427be629-25bb-46cc-a04d-cd4f8278f112.png",  # trousers
    "hf_20260928_131318_ef12d9de-0848-4eb1-995a-3b84de8d0932.png",  # blazer
    "hf_20260928_131318_fd7d4667-0be4-4b27-9056-d6afd5b27515.png",  # overcoat
]


def fetch(name: str) -> Image.Image:
    with urllib.request.urlopen(BASE + name, timeout=60) as r:
        return Image.open(io.BytesIO(r.read()))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(STATES):
        im = fetch(name).convert("RGB")
        im.thumbnail((1100, 1650), Image.LANCZOS)
        path = OUT / f"state-{i}.webp"
        im.save(path, "WEBP", quality=82, method=6)
        print(f"{path.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}  {path.stat().st_size // 1024} KB")
    for i, name in enumerate(GARMENTS, start=1):
        im = fetch(name).convert("RGBA")
        # Trim to the garment so the page can place it by its real outline.
        box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        if box:
            im = im.crop(box)
        im.thumbnail((900, 1300), Image.LANCZOS)
        path = OUT / f"garment-{i}.webp"
        im.save(path, "WEBP", quality=85, method=6)
        print(f"{path.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}  {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
